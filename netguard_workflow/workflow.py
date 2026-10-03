"""Train and evaluate from raw CSVs without consulting historical models.

The existing test set is a previously inspected benchmark, not an untouched
holdout. All fitted state and threshold/model choices use development data only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
import json
import platform

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score, confusion_matrix, f1_score, precision_recall_curve,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler
from threadpoolctl import threadpool_limits

from .features import (
    FEATURE_SCHEMA_VERSION, RAW_INPUTS, FEATURE_NAMES, RawTrafficFeatures,
    feature_catalog, feature_quality_report,
)


@dataclass(frozen=True)
class WorkflowConfig:
    seed: int = 42
    validation_folds: int = 5
    max_iter: int = 150
    threads: int = 2

    def __post_init__(self):
        if self.validation_folds < 2 or self.max_iter < 1 or self.threads < 1:
            raise ValueError("Require at least two folds and positive iterations/threads.")


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


def _choose_threshold(labels, scores):
    precision, recall, thresholds = precision_recall_curve(labels, scores)
    f1 = np.divide(
        2 * precision[:-1] * recall[:-1], precision[:-1] + recall[:-1],
        out=np.zeros_like(thresholds), where=(precision[:-1] + recall[:-1]) > 0,
    )
    # For equal F1, choose the highest threshold (fewer alerts).
    best = np.flatnonzero(f1 == f1.max())[-1]
    return float(thresholds[best])


def score_metrics(labels, scores, threshold):
    predictions = (np.asarray(scores) >= threshold).astype(np.int8)
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    return {
        "rows": int(len(labels)), "threshold": float(threshold),
        "precision": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "roc_auc": float(roc_auc_score(labels, scores)) if len(np.unique(labels)) == 2 else None,
        "average_precision": float(average_precision_score(labels, scores)) if np.any(np.asarray(labels) == 1) else None,
        "false_positive_rate": float(fp / (fp + tn)) if fp + tn else None,
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def fit_baselines(train, fit_idx, val_idx, config):
    estimators = {
        "dummy_prior": DummyClassifier(strategy="prior"),
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            random_state=config.seed, max_iter=config.max_iter,
            max_leaf_nodes=31, l2_regularization=1.0, early_stopping=False,
        ),
    }
    fitted, rows = {}, []
    X_fit = train.iloc[fit_idx].loc[:, list(RAW_INPUTS)]
    X_val = train.iloc[val_idx].loc[:, list(RAW_INPUTS)]
    with threadpool_limits(limits=config.threads):
        for name, estimator in estimators.items():
            pipeline = Pipeline([
                ("raw_features", RawTrafficFeatures()),
                ("scaler", RobustScaler()), ("model", estimator),
            ])
            pipeline.fit(X_fit, train.iloc[fit_idx].label)
            scores = pipeline.predict_proba(X_val)[:, 1]
            threshold = _choose_threshold(train.iloc[val_idx].label, scores)
            fitted[name] = {"pipeline": pipeline, "threshold": threshold, "model_name": name}
            rows.append({"model": name, **score_metrics(train.iloc[val_idx].label, scores, threshold)})
    comparison = pd.DataFrame(rows).sort_values(
        ["f1", "average_precision", "model"], ascending=[False, False, True]
    ).reset_index(drop=True)
    winner = comparison.iloc[0].model
    bundle = {**fitted[winner], "config": asdict(config),
              "raw_inputs": list(RAW_INPUTS), "features": list(FEATURE_NAMES),
              "feature_schema_version": FEATURE_SCHEMA_VERSION,
              "feature_definitions": feature_catalog(),
              "threshold_policy": "maximum validation F1; equal F1 chooses higher threshold",
              "selection_policy": "validation F1, then average precision, then name",
              "evaluation_status": "previously inspected benchmark; not an untouched holdout"}
    return bundle, comparison


def predict_raw(bundle, frame):
    if bundle.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise ValueError("This model uses an earlier feature schema; rerun the corrected notebook to retrain.")
    config = bundle["config"]
    with threadpool_limits(limits=config["threads"]):
        scores = bundle["pipeline"].predict_proba(frame)[:, 1]
    return pd.DataFrame({
        "attack_score": scores,
        "predicted_label": (scores >= bundle["threshold"]).astype(np.int8),
    }, index=frame.index)


def evaluate_benchmark(bundle, benchmark, development):
    predictions = predict_raw(bundle, benchmark)
    seen = np.isin(input_signatures(benchmark), input_signatures(development))
    predictions.insert(0, "row_id", benchmark.id.to_numpy())
    predictions["true_label"] = benchmark.label.to_numpy()
    predictions["attack_category"] = benchmark.attack_cat.to_numpy()
    predictions["seen_in_development"] = seen
    metrics = score_metrics(benchmark.label, predictions.attack_score, bundle["threshold"])
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
    joblib.dump(bundle, output_dir / "model.joblib")
    # Verify persistence using the same raw measurements, including single-row inference.
    sample = train.loc[:, list(RAW_INPUTS)].iloc[:32]
    restored = joblib.load(output_dir / "model.joblib")
    expected = predict_raw(bundle, sample)
    actual = predict_raw(restored, sample)
    np.testing.assert_allclose(expected.attack_score, actual.attack_score, rtol=0, atol=1e-12)
    single = pd.concat([predict_raw(restored, sample.iloc[[i]]) for i in range(len(sample))])
    np.testing.assert_allclose(actual.attack_score, single.attack_score, rtol=0, atol=1e-12)
    np.testing.assert_array_equal(actual.predicted_label, single.predicted_label)
    predictions.to_csv(output_dir / "benchmark_predictions.csv", index=False, float_format="%.17g")
    validation.to_csv(output_dir / "validation_comparison.csv", index=False)
    slices.to_csv(output_dir / "benchmark_slices.csv", index=False)
    categories.to_csv(output_dir / "attack_category_metrics.csv", index=False)
    split = pd.DataFrame({"row_id": train.id, "partition": "fit"})
    split.iloc[val_idx, split.columns.get_loc("partition")] = "validation"
    split.to_csv(output_dir / "development_split.csv", index=False)
    summary = {"selected_model": bundle["model_name"], "benchmark": benchmark_metrics,
               "validation": validation.to_dict(orient="records"),
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
        "preprocessing_order": list(bundle["pipeline"].named_steps),
        "physical_feature_checks": quality,
        "threshold": bundle["threshold"], "threshold_policy": bundle["threshold_policy"],
        "model_selection": bundle["selection_policy"], "selected_model": bundle["model_name"],
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
        )},
        "output_sha256": {name: file_sha256(output_dir/name) for name in (
            "model.joblib", "benchmark_predictions.csv", "validation_comparison.csv",
            "benchmark_slices.csv", "attack_category_metrics.csv", "development_split.csv", "metrics.json",
            "feature_catalog.json", "feature_quality_report.json",
        )},
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    return manifest
