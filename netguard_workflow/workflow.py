"""Train and evaluate from raw CSVs without consulting historical models.

The existing test set is a previously inspected benchmark, not an untouched
holdout. All fitted state and threshold/model choices use development data only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
import json
import platform
import time
import warnings

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import (
    average_precision_score, confusion_matrix, f1_score, accuracy_score, balanced_accuracy_score,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .features import (
    FEATURE_SCHEMA_VERSION, RAW_INPUTS, FEATURE_NAMES, RawTrafficFeatures,
    feature_catalog, feature_quality_report,
)
from .inference import (
    ARTIFACT_SCHEMA_VERSION, predict_raw,
    save_prediction_artifact, load_prediction_artifact, PredictionService,
)
from .models import MeanProbabilityClassifier
from .comparison import candidate_bundle, measure_prediction_latency, ensemble_gate, latency_protocol


@dataclass(frozen=True)
class WorkflowConfig:
    seed: int = 42
    validation_folds: int = 5
    max_iter: int = 150
    threads: int = 2
    max_false_positive_rate: float = 0.01
    logistic_max_iter: int = 2000
    forest_trees: int = 200
    forest_max_depth: int = 20
    latency_batch_size: int = 256
    latency_repeats: int = 11
    ensemble_min_recall_gain: float = 0.02
    ensemble_max_latency_ratio: float = 2.0

    def __post_init__(self):
        if self.validation_folds < 2 or self.max_iter < 1 or self.threads < 1:
            raise ValueError("Require at least two folds and positive iterations/threads.")
        if not np.isfinite(self.max_false_positive_rate) or not 0 <= self.max_false_positive_rate < 1:
            raise ValueError("The false-positive budget must be finite and in [0, 1).")
        if min(self.logistic_max_iter, self.forest_trees, self.forest_max_depth, self.latency_batch_size) < 1 or self.latency_repeats < 3:
            raise ValueError("Require positive model/batch sizes and at least three latency repeats.")
        if not np.isfinite(self.ensemble_min_recall_gain) or not 0 <= self.ensemble_min_recall_gain <= 1:
            raise ValueError("Ensemble minimum recall gain must be in [0, 1].")
        if not np.isfinite(self.ensemble_max_latency_ratio) or self.ensemble_max_latency_ratio < 1:
            raise ValueError("Ensemble maximum latency ratio must be finite and at least one.")


def _read_raw(path):
    df = pd.read_csv(path, encoding="utf-8-sig")
    required = {*RAW_INPUTS, "id", "attack_cat", "label"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"{path.name} is missing columns: {missing}")
    if not df.label.isin([0, 1]).all():
        raise ValueError("Labels must be 0 (normal) or 1 (attack).")
    if df.label.nunique() != 2:
        raise ValueError("Both classes are required for evaluation.")
    if df.id.isna().any() or df.id.duplicated().any():
        raise ValueError("Row IDs must be present and unique within each CSV.")
    RawTrafficFeatures().transform(df)
    return df


def load_raw_data(root):
    root = Path(root)
    return (
        _read_raw(root / "data/UNSW_NB15_training-set.csv"),
        _read_raw(root / "data/UNSW_NB15_testing-set.csv"),
    )


def input_signatures(frame):
    """Hash only measured predictors, excluding labels, categories and IDs."""
    numeric = frame.loc[:, list(RAW_INPUTS)].astype(np.float64)
    return pd.util.hash_pandas_object(numeric, index=False).to_numpy()


def split_development(train, config):
    groups = input_signatures(train)
    splitter = StratifiedGroupKFold(
        n_splits=config.validation_folds, shuffle=True, random_state=config.seed
    )
    fit_idx, val_idx = next(splitter.split(train, train.label, groups))
    if np.intersect1d(groups[fit_idx], groups[val_idx]).size:
        raise AssertionError("Identical measured-input signatures crossed the split.")
    for idx in (fit_idx, val_idx):
        if train.iloc[idx].label.nunique() != 2:
            raise ValueError("This group split lacks a class; use more development data.")
    return fit_idx, val_idx, groups


def _choose_threshold(labels, scores, max_false_positive_rate=0.01):
    """Maximize held-out recall under an empirical FPR budget using score >= t.

    Move all tied scores together, rather than interpolating an unattainable ROC
    point. Equal recall prefers fewer false positives, then a higher threshold.
    A finite reject-all candidate makes even constant scores feasible.
    """
    labels, scores = np.asarray(labels), np.asarray(scores, dtype=np.float64)
    if labels.ndim != 1 or scores.ndim != 1 or len(labels) != len(scores) or not len(labels):
        raise ValueError("Supply equal-length, nonempty one-dimensional validation labels and scores.")
    if not np.isin(labels, [0, 1]).all() or len(np.unique(labels)) != 2:
        raise ValueError("Threshold selection needs both normal (0) and attack (1) validation rows.")
    if not np.isfinite(scores).all() or (scores < 0).any() or (scores > 1).any():
        raise ValueError("Validation classifier scores must be finite and between 0 and 1.")
    if not np.isfinite(max_false_positive_rate) or not 0 <= max_false_positive_rate < 1:
        raise ValueError("The false-positive budget must be finite and in [0, 1).")
    order = np.argsort(-scores, kind="stable")
    ordered_scores, ordered_labels = scores[order], labels[order]
    ends = np.flatnonzero(np.r_[ordered_scores[:-1] != ordered_scores[1:], True])
    thresholds = np.r_[np.nextafter(ordered_scores[0], np.inf), ordered_scores[ends]]
    tp = np.r_[0, np.cumsum(ordered_labels == 1)[ends]]
    fp = np.r_[0, np.cumsum(ordered_labels == 0)[ends]]
    eligible = np.flatnonzero(fp / np.count_nonzero(labels == 0) <= max_false_positive_rate)
    best = eligible[np.lexsort((-thresholds[eligible], fp[eligible], -tp[eligible]))[0]]
    return float(thresholds[best])


def score_metrics(labels, scores, threshold):
    predictions = (np.asarray(scores) >= threshold).astype(np.int8)
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    return {
        "rows": int(len(labels)), "threshold": float(threshold),
        "accuracy": float(accuracy_score(labels, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(labels, predictions)),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, scores)) if len(np.unique(labels)) == 2 else None,
        "average_precision": float(average_precision_score(labels, scores)) if np.any(np.asarray(labels) == 1) else None,
        "false_positive_rate": float(fp / (fp + tn)) if fp + tn else None,
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def fit_baselines(train, fit_idx, val_idx, config):
    if np.intersect1d(input_signatures(train.iloc[fit_idx]), input_signatures(train.iloc[val_idx])).size:
        raise ValueError("Fit and validation predictor signatures must be disjoint.")
    estimators = {
        "dummy_prior": DummyClassifier(strategy="prior"),
        "logistic_regression": LogisticRegression(
            solver="lbfgs", C=1.0, max_iter=config.logistic_max_iter, tol=1e-5, random_state=config.seed,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=config.forest_trees, max_depth=config.forest_max_depth,
            min_samples_leaf=2, max_features="sqrt", random_state=config.seed, n_jobs=config.threads,
        ),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            random_state=config.seed, max_iter=config.max_iter,
            max_leaf_nodes=31, l2_regularization=1.0, early_stopping=False,
        ),
    }
    fitted, rows = {}, []
    X_fit = train.iloc[fit_idx].loc[:, list(RAW_INPUTS)]
    X_val = train.iloc[val_idx].loc[:, list(RAW_INPUTS)]
    y_fit, y_val = train.iloc[fit_idx].label, train.iloc[val_idx].label
    started = time.perf_counter()
    raw_features = RawTrafficFeatures().fit(X_fit)
    physical_fit = raw_features.transform(X_fit)
    scaler = StandardScaler().fit(physical_fit)
    scaled_fit = scaler.transform(physical_fit)
    preprocessing_s = time.perf_counter()-started

    def evaluate(name, pipeline, fit_seconds, converged, iterations):
        with threadpool_limits(limits=config.threads):
            scores = pipeline.predict_proba(X_val)[:, 1]
        threshold = _choose_threshold(y_val, scores, config.max_false_positive_rate)
        metrics = score_metrics(y_val, scores, threshold)
        candidate = candidate_bundle(name, pipeline, threshold, config, metrics)
        timing = measure_prediction_latency(candidate, X_val, config)
        fitted[name] = candidate
        rows.append({"model": name, **metrics, **timing, "fit_seconds": fit_seconds,
                     "converged": converged, "optimization_iterations": iterations,
                     "eligible_for_selection": converged and metrics["false_positive_rate"] <= config.max_false_positive_rate,
                     "component_count": 3 if name == "supervised_soft_vote" else 1})

    for name, estimator in estimators.items():
        print(f"Fitting candidate: {name}", flush=True)
        started = time.perf_counter()
        with warnings.catch_warnings(record=True) as captured, threadpool_limits(limits=config.threads):
            warnings.simplefilter("always", ConvergenceWarning)
            estimator.fit(scaled_fit, y_fit)
        fit_seconds = time.perf_counter()-started+preprocessing_s
        if isinstance(estimator, RandomForestClassifier):
            # Fit trees in parallel, then sum tree probabilities in a fixed order
            # at inference to avoid threshold-boundary changes from scheduling.
            estimator.set_params(n_jobs=1)
        converged = not any(issubclass(item.category, ConvergenceWarning) for item in captured)
        for item in captured:
            if not issubclass(item.category, ConvergenceWarning):
                warnings.warn(item.message, item.category)
        pipeline = Pipeline([
            ("raw_features", raw_features), ("scaler", scaler), ("model", estimator),
        ])
        iterations = int(np.max(estimator.n_iter_)) if hasattr(estimator, "n_iter_") else 0
        evaluate(name, pipeline, fit_seconds, converged, iterations)
    members = [(name, estimators[name]) for name in ("logistic_regression", "random_forest", "hist_gradient_boosting")]
    print("Evaluating candidate: supervised_soft_vote (fixed equal weights)", flush=True)
    ensemble = MeanProbabilityClassifier.from_fitted(members)
    ensemble_pipeline = Pipeline([("raw_features", raw_features), ("scaler", scaler), ("model", ensemble)])
    ensemble_fit_s = sum(row["fit_seconds"]-preprocessing_s for row in rows if row["model"] != "dummy_prior")+preprocessing_s
    evaluate("supervised_soft_vote", ensemble_pipeline, ensemble_fit_s,
             all(row["converged"] for row in rows if row["model"] != "dummy_prior"), 0)
    comparison = pd.DataFrame(rows).sort_values(
        ["recall", "false_positive_rate", "average_precision", "model"], ascending=[False, True, False, True]
    ).reset_index(drop=True)
    singles = comparison.loc[(comparison.model != "supervised_soft_vote") & comparison.eligible_for_selection]
    best_single = singles.iloc[0].to_dict()
    decision = ensemble_gate(best_single, comparison.loc[comparison.model == "supervised_soft_vote"].iloc[0].to_dict(), config)
    winner = "supervised_soft_vote" if decision["retained"] else best_single["model"]
    comparison["selected"] = comparison.model == winner
    bundle = {**fitted[winner]}
    bundle.update({"ensemble_decision": decision, "validation_comparison": comparison.to_dict(orient="records"),
                   "latency_protocol": latency_protocol(config),
                   "preprocessing": "raw physical features -> fit-only StandardScaler -> classifier",
                   "component_names": ensemble.member_names_ if decision["retained"] else [winner],
                   "model_parameters": {name: estimator.get_params(deep=False) for name, estimator in estimators.items()},
                   "_comparison_candidates": fitted})
    return bundle, comparison


def evaluate_benchmark(bundle, benchmark, development):
    predictions = predict_raw(bundle, benchmark)
    seen = np.isin(input_signatures(benchmark), input_signatures(development))
    predictions.insert(0, "row_id", benchmark.id.to_numpy())
    predictions["true_label"] = benchmark.label.to_numpy()
    predictions["attack_category"] = benchmark.attack_cat.to_numpy()
    predictions["seen_in_development"] = seen
    metrics = score_metrics(benchmark.label, predictions.attack_score, bundle["threshold"])
    comparison_rows = []
    for name, candidate in bundle.get("_comparison_candidates", {}).items():
        candidate_predictions = predictions if name == bundle["model_name"] else predict_raw(candidate, benchmark)
        comparison_rows.append({"model": name, **score_metrics(benchmark.label, candidate_predictions.attack_score, candidate["threshold"]),
                                "selected": name == bundle["model_name"],
                                "evaluation_status": bundle["evaluation_status"]})
    bundle["benchmark_comparison"] = comparison_rows
    slices = []
    for name, mask in (("seen_input_signature", seen), ("unseen_input_signature", ~seen)):
        if mask.any():
            slices.append({"slice": name, **score_metrics(
                benchmark.loc[mask, "label"], predictions.loc[mask, "attack_score"], bundle["threshold"]
            )})
    categories = []
    for name, part in predictions.groupby("attack_category", sort=True):
        attacks = part.true_label == 1
        categories.append({"attack_category": str(name), "rows": len(part),
            "attack_rows": int(attacks.sum()),
            "attack_recall": float(part.loc[attacks, "predicted_label"].mean()) if attacks.any() else None,
            "alert_rate": float(part.predicted_label.mean())})
    return predictions, metrics, pd.DataFrame(slices), pd.DataFrame(categories)


def file_sha256(path):
    digest = sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_run(root, output_dir, bundle, train, fit_idx, val_idx, predictions,
             validation, benchmark_metrics, slices, categories):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    # Comparison candidates are offline experiments, not part of the serving artifact.
    candidates = bundle.pop("_comparison_candidates", {})
    candidate_dir = output_dir/"candidates"
    candidate_dir.mkdir(exist_ok=True)
    for name, candidate in candidates.items():
        save_prediction_artifact(candidate, candidate_dir/f"{name}.joblib")
    bundle["benchmark_metrics"] = benchmark_metrics
    save_prediction_artifact(bundle, output_dir / "model.joblib")
    # Verify persistence using the same raw measurements, including single-row inference.
    sample = train.loc[:, list(RAW_INPUTS)].iloc[:32]
    restored = load_prediction_artifact(output_dir / "model.joblib")
    expected = predict_raw(bundle, sample)
    actual = predict_raw(restored, sample)
    np.testing.assert_allclose(expected.attack_score, actual.attack_score, rtol=0, atol=1e-12)
    single = pd.concat([predict_raw(restored, sample.iloc[[i]]) for i in range(len(sample))])
    np.testing.assert_allclose(actual.attack_score, single.attack_score, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(actual.predicted_label, single.predicted_label)
    predictions.to_csv(output_dir / "benchmark_predictions.csv", index=False, float_format="%.17g")
    validation.to_csv(output_dir / "validation_comparison.csv", index=False)
    benchmark_comparison = pd.DataFrame(bundle["benchmark_comparison"])
    benchmark_comparison.to_csv(output_dir/"benchmark_comparison.csv", index=False)
    slices.to_csv(output_dir / "benchmark_slices.csv", index=False)
    categories.to_csv(output_dir / "attack_category_metrics.csv", index=False)
    split = pd.DataFrame({"row_id": train.id, "partition": "fit"})
    split.iloc[val_idx, split.columns.get_loc("partition")] = "validation"
    split.to_csv(output_dir / "development_split.csv", index=False)
    summary = {"selected_model": bundle["model_name"], "benchmark": benchmark_metrics,
               "score_calibration": bundle["score_calibration"],
               "threshold_selection": bundle["threshold_selection"],
               "benchmark_meets_false_positive_budget": benchmark_metrics["false_positive_rate"] <= bundle["config"]["max_false_positive_rate"],
               "validation": validation.to_dict(orient="records"),
               "benchmark_comparison": bundle["benchmark_comparison"],
               "ensemble_decision": bundle["ensemble_decision"],
               "latency_protocol": bundle["latency_protocol"],
               "model_parameters": bundle["model_parameters"],
               "evaluation_status": bundle["evaluation_status"]}
    (output_dir / "metrics.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    catalog = {"schema_version": FEATURE_SCHEMA_VERSION, "stage": "raw features before scaling",
               "features": feature_catalog()}
    (output_dir / "feature_catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    raw_benchmark = _read_raw(Path(root)/"data/UNSW_NB15_testing-set.csv")
    quality = {"status": "passed", "stage": "raw features before scaling",
               "development": feature_quality_report(train),
               "benchmark": feature_quality_report(raw_benchmark)}
    (output_dir / "feature_quality_report.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")
    packages = {p: version(p) for p in (
        "numpy", "pandas", "scipy", "scikit-learn", "joblib", "threadpoolctl", "nbformat", "nbclient", "ipykernel"
    )}
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "packages": packages,
        "configuration": bundle["config"], "raw_inputs": bundle["raw_inputs"],
        "feature_names": bundle["features"], "feature_precision": "float64",
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "preprocessing_order": list(bundle["pipeline"].named_steps),
        "physical_feature_checks": quality,
        "threshold": bundle["threshold"], "threshold_policy": bundle["threshold_policy"],
        "score_calibration": bundle["score_calibration"], "threshold_selection": bundle["threshold_selection"],
        "model_selection": bundle["selection_policy"], "selected_model": bundle["model_name"],
        "ensemble_decision": bundle["ensemble_decision"], "latency_protocol": bundle["latency_protocol"],
        "preprocessing": bundle["preprocessing"], "model_parameters": bundle["model_parameters"],
        "fit_rows": len(fit_idx), "validation_rows": len(val_idx),
        "benchmark_rows": len(predictions),
        "evaluation_status": bundle["evaluation_status"],
        "checks": {"artifact_reload_matches": True, "single_and_batch_match": True},
        "input_sha256": {p.name: file_sha256(p) for p in (
            Path(root)/"data/UNSW_NB15_training-set.csv", Path(root)/"data/UNSW_NB15_testing-set.csv"
        )},
        "source_sha256": {p.relative_to(root).as_posix(): file_sha256(p) for p in (
            Path(root)/"netguard_workflow/workflow.py", Path(root)/"requirements-notebooks.txt",
            Path(root)/"netguard_workflow/features.py",
            Path(root)/"netguard_workflow/inference.py", Path(root)/"requirements-model.in",
            Path(root)/"netguard_workflow/models.py", Path(root)/"netguard_workflow/comparison.py",
        )},
        "output_sha256": {name: file_sha256(output_dir/name) for name in (
            "model.joblib", "benchmark_predictions.csv", "validation_comparison.csv",
            "benchmark_slices.csv", "attack_category_metrics.csv", "development_split.csv", "metrics.json",
            "feature_catalog.json", "feature_quality_report.json",
            "model.manifest.json",
            "benchmark_comparison.csv",
        )},
    }
    # Serve exactly the same selected fitted pipeline; do not train in the API.
    deployment_path = Path(root)/"models_saved/shared_pipeline.joblib"
    deployed_manifest = save_prediction_artifact(bundle, deployment_path)
    deployed = PredictionService(deployment_path)
    np.testing.assert_allclose(deployed.predict(sample).attack_score, expected.attack_score, rtol=0, atol=1e-12)
    manifest["shared_prediction_artifact"] = {
        "path": deployment_path.relative_to(root).as_posix(),
        "sha256": deployed_manifest["artifact_sha256"],
        "same_bytes_as_notebook_artifact": deployed_manifest["artifact_sha256"] == manifest["output_sha256"]["model.joblib"],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    # Commit compact comparison evidence while large regenerable candidate files stay ignored.
    reports = Path(root)/"data/reports"
    validation.to_csv(reports/"supervised_validation_comparison.csv", index=False)
    benchmark_comparison.to_csv(reports/"supervised_benchmark_comparison.csv", index=False)
    (reports/"supervised_comparison.json").write_text(json.dumps({
        "status": "passed", "selected_model": bundle["model_name"],
        "validation": bundle["validation_comparison"], "benchmark": bundle["benchmark_comparison"],
        "ensemble_decision": bundle["ensemble_decision"], "latency_protocol": bundle["latency_protocol"],
        "configuration": bundle["config"], "model_parameters": bundle["model_parameters"],
        "fit_rows": len(fit_idx), "validation_rows": len(val_idx),
        "evaluation_status": bundle["evaluation_status"],
        "artifact_sha256": deployed_manifest["artifact_sha256"],
    }, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")
    return manifest
