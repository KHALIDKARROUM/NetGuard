"""Audit a frozen serving model and refit its fixed design on stronger splits.

All new models are offline experiments. Never overwrite the deployed artifact,
alter benchmark rows, select models, or tune on evaluation outcomes.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import warnings

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.exceptions import ConvergenceWarning
from sklearn.ensemble import RandomForestClassifier
from threadpoolctl import threadpool_limits

from .comparison import candidate_bundle
from .evaluation import evaluate_frame, seen_signatures, three_way_partition, partition_membership
from .features import RAW_INPUTS
from .inference import PredictionService, predict_raw, runtime_versions
from .workflow import WorkflowConfig, _choose_threshold, file_sha256, load_raw_data, score_metrics, split_development


def fit_frozen_design(template, development, fit, calibration, config):
    """Clone the already declared architecture; refit only on this run's fit rows.

    Fit forest trees in parallel and restore deterministic one-worker scoring.
    Threshold uses calibration only. There is no latency gate or model selection.
    """
    pipeline = clone(template["pipeline"])
    estimator = pipeline.named_steps["model"]
    members = [member for _, member in estimator.estimators] if hasattr(estimator, "estimators") else [estimator]
    for member in members:
        if isinstance(member, RandomForestClassifier):
            member.set_params(n_jobs=config.threads)
    started = time.perf_counter()
    with warnings.catch_warnings(record=True) as captured, threadpool_limits(limits=config.threads):
        warnings.simplefilter("always", ConvergenceWarning)
        pipeline.fit(development.iloc[fit].loc[:, list(RAW_INPUTS)], development.iloc[fit].label)
    fitted_members = estimator.estimators_ if hasattr(estimator, "estimators_") else [estimator]
    for member in fitted_members:
        if isinstance(member, RandomForestClassifier):
            member.set_params(n_jobs=1)
    converged = not any(issubclass(item.category, ConvergenceWarning) for item in captured)
    with threadpool_limits(limits=config.threads):
        scores = pipeline.predict_proba(development.iloc[calibration].loc[:, list(RAW_INPUTS)])[:, 1]
    threshold = _choose_threshold(development.iloc[calibration].label, scores, config.max_false_positive_rate)
    metrics = score_metrics(development.iloc[calibration].label, scores, threshold)
    bundle = candidate_bundle(template["model_name"], pipeline, threshold, config, metrics)
    bundle["selection_policy"] = "fixed previously selected design; no model/weight/parameter selection in this experiment"
    return bundle, {"fit_seconds": time.perf_counter()-started, "converged": converged,
                    "warnings": [str(item.message) for item in captured], "calibration_metrics": metrics}


def _save_predictions(output, name, frame, scores, threshold, **columns):
    result = pd.DataFrame({"row_id": frame.id.to_numpy(), "true_label": frame.label.to_numpy(),
                          "attack_category": frame.attack_cat.to_numpy(), "attack_score": scores,
                          "predicted_label": (np.asarray(scores) >= threshold).astype(np.int8), **columns})
    result.to_csv(output/f"{name}_predictions.csv", index=False, float_format="%.17g")


def run_generalization(root, output_dir=None, *, repeats=400, seeds=(42, 43, 44), families=None, baseline_manifest=None):
    root = Path(root).resolve()
    output = Path(output_dir or root/"artifacts/generalization").resolve()
    output.mkdir(parents=True, exist_ok=True)
    service = PredictionService(root/"models_saved/shared_pipeline.joblib")
    config = WorkflowConfig(**service.bundle["config"])
    original_inputs = {name: file_sha256(root/"data"/name) for name in
                       ("UNSW_NB15_training-set.csv", "UNSW_NB15_testing-set.csv")}
    development, benchmark = load_raw_data(root)
    # During a full notebook run, save_run has already written its fresh manifest,
    # while the outer runner publishes the tracked verification only at the end.
    # Independent evaluation instead uses the previous completed run's evidence.
    if baseline_manifest is not None:
        previous = json.loads(Path(baseline_manifest).read_text(encoding="utf-8"))
    else:
        evidence = json.loads((root/"data/reports/notebook_workflow_verification.json").read_text(encoding="utf-8"))
        previous = evidence["manifest"]
    if previous["input_sha256"] != original_inputs or previous["shared_prediction_artifact"]["sha256"] != service.artifact_sha256:
        raise ValueError("Data/artifact do not match recorded fitting provenance; rerun the corrected workflow.")
    fit, validation, _ = split_development(development, config)
    if len(fit) != previous["fit_rows"] or len(validation) != previous["validation_rows"]:
        raise ValueError("Reconstructed fitting membership differs from the recorded run.")
    selected_families = sorted(development.loc[development.label == 1, "attack_cat"].unique()) if families is None else list(families)
    results, category_rows, runs = [], [], []
    print("Evaluating the unchanged benchmark with the frozen serving artifact", flush=True)
    scores = service.predict(benchmark).attack_score.to_numpy()
    seen_fit = seen_signatures(benchmark, development.iloc[fit])
    seen_development = seen_signatures(benchmark, development)
    # Full benchmark confusion counts must reproduce the original evidence.
    original_metrics = score_metrics(benchmark.label, scores, service.bundle["threshold"])
    for name in ("rows", "tp", "fp", "fn", "tn", "precision", "recall", "f1", "average_precision", "false_positive_rate"):
        recorded = service.bundle["benchmark_metrics"][name]
        if not np.isclose(original_metrics[name], recorded, rtol=0, atol=1e-12):
            raise AssertionError(f"Original benchmark result changed: {name}")
    masks = {"benchmark_all": np.ones(len(benchmark), dtype=bool),
             "benchmark_seen_in_fit": seen_fit, "benchmark_unseen_in_fit": ~seen_fit,
             "benchmark_unseen_in_any_development": ~seen_development}
    for index, (scope, mask) in enumerate(masks.items()):
        print(f"Uncertainty and attack categories: {scope} ({mask.sum()} rows)", flush=True)
        point, categories = evaluate_frame(benchmark.loc[mask], scores[mask], service.bundle["threshold"],
                                          scope=scope, repeats=repeats, seed=1000+index)
        results.append(point)
        category_rows.extend(categories)
    _save_predictions(output, "benchmark", benchmark, scores, service.bundle["threshold"],
                      seen_in_fit=seen_fit, seen_in_any_development=seen_development)
    audit = json.loads((root/"data/reports/project_audit_evidence.json").read_text(encoding="utf-8"))
    legacy_overlap = audit["overlap"]["featured"]["test_rows_with_features_seen_in_train"]
    overlap = {"historical_selected_feature_overlap_rows": legacy_overlap,
               "historical_selected_feature_overlap_fraction": legacy_overlap/len(benchmark),
               "historical_definition": "matches in the earlier selected/engineered predictor representation",
               "current_definition": "exact float64 equality across the ten raw serving measurements; hash membership verified by equality join",
               "benchmark_rows": len(benchmark), "seen_in_actual_fit_rows": int(seen_fit.sum()),
               "seen_in_any_development_rows": int(seen_development.sum()),
               "unseen_in_actual_fit_rows": int((~seen_fit).sum()),
               "unseen_in_any_development_rows": int((~seen_development).sum()),
               "identity_interpretation": "feature equality alone does not establish identical physical connections"}
    for seed in seeds:
        scope = f"three_way_grouped_seed_{seed}"
        print(f"Refitting frozen design: {scope}", flush=True)
        train_idx, calibration, evaluation, checks = three_way_partition(development, seed=seed)
        experimental, diagnostics = fit_frozen_design(service.bundle, development, train_idx, calibration, config)
        part = development.iloc[evaluation]
        evaluation_scores = predict_raw(experimental, part).attack_score.to_numpy()
        point, categories = evaluate_frame(part, evaluation_scores, experimental["threshold"], scope=scope,
                                          repeats=repeats, seed=2000+seed)
        results.append(point)
        category_rows.extend(categories)
        runs.append({"scope": scope, **checks, **diagnostics, "configuration": asdict(config)})
        _save_predictions(output, scope, part, evaluation_scores, experimental["threshold"])
        split = partition_membership(development, train_idx, calibration, evaluation)
        split.to_csv(output/f"{scope}_membership.csv", index=False)
        del experimental
    for index, family in enumerate(selected_families):
        scope = f"withheld_family_{family}"
        print(f"Refitting frozen design: {scope}", flush=True)
        train_idx, calibration, evaluation, checks = three_way_partition(development, seed=config.seed, held_family=family)
        experimental, diagnostics = fit_frozen_design(service.bundle, development, train_idx, calibration, config)
        part = development.iloc[evaluation]
        evaluation_scores = predict_raw(experimental, part).attack_score.to_numpy()
        point, categories = evaluate_frame(part, evaluation_scores, experimental["threshold"], scope=scope,
                                          repeats=repeats, seed=3000+index)
        results.append(point)
        category_rows.extend(categories)
        runs.append({"scope": scope, **checks, **diagnostics, "configuration": asdict(config)})
        _save_predictions(output, scope, part, evaluation_scores, experimental["threshold"])
        split = partition_membership(development, train_idx, calibration, evaluation, held_family=family)
        split.to_csv(output/f"{scope}_membership.csv", index=False)
        del experimental
    present = set(development.columns)
    provenance = {"available_columns": list(development.columns),
        "missing_capture_time_columns": sorted({"stime", "ltime", "timestamp", "capture_time"}-present),
        "missing_host_identity_columns": sorted({"srcip", "dstip", "source_ip", "destination_ip"}-present),
        "connection_identity": "CSV-local id is a row identifier; no verified physical-connection key",
        "supported_splits": ["signature-grouped fitting/calibration/evaluation", "attack-family withholding with complete signature exclusion"],
        "unsupported_claims": ["future-time generalization", "unseen-host generalization", "independent capture/domain generalization"],
        "stronger_source": "UNSW publishes original PCAP/Argus/Bro files, event/ground-truth records and full CSVs; acquire verified mapping before time/host/capture splits",
        "source": "https://research.unsw.edu.au/projects/unsw-nb15-dataset"}
    unchanged = original_inputs == {name: file_sha256(root/"data"/name) for name in original_inputs}
    unchanged_artifact = file_sha256(service.artifact_path) == service.artifact_sha256
    if not unchanged or not unchanged_artifact:
        raise AssertionError("Evaluation changed raw benchmark/development or serving artifact")
    report = {"status": "passed", "created_utc": datetime.now(timezone.utc).isoformat(),
        "serving_artifact_sha256": service.artifact_sha256, "serving_model": service.bundle["model_name"],
        "serving_threshold": service.bundle["threshold"], "runtime": runtime_versions(),
        "input_sha256": original_inputs, "overlap": overlap, "provenance": provenance,
        "uncertainty": {"method": "95% percentile bootstrap resampling entire measured-input signatures with replacement; row-weighted estimates",
            "repetitions": repeats, "seeds": "benchmark 1000+scope index, grouped 2000+split seed, family 3000+family index; categories add category index+1",
            "conditional_on": "fixed fitted pipeline, fixed validation/calibration threshold, observed traffic and signature definition",
            "limitations": "does not include refitting/model-selection/threshold-selection uncertainty or latent capture/host dependence; small groups and boundary rates may be degenerate; no population or deployment guarantee"},
        "metric_definitions": {"precision_recall_f1_fpr": "binary attack detection at each frozen threshold",
            "pr_auc": "trapezoidal area of precision-recall curve, initial recall=0 precision=1, tied scores move together",
            "average_precision": "non-interpolated precision weighted by recall increments; reported separately from trapezoidal PR-AUC",
            "category_comparison": "one attack category versus normal rows in the same scope; other attacks excluded; FPR uses shared normal rows; precision/PR-AUC depend on this constructed prevalence",
            "undefined": "null for metrics without required classes/denominators; intervals null with insufficient valid bootstrap draws"},
        "evaluation": results, "attack_categories": category_rows, "experiments": runs,
        "protocol": {"grouped_seeds_declared": list(seeds), "held_families_declared": selected_families,
            "design": "clone fixed previously selected serving architecture and all parameters; fit only on fitting rows; tune threshold only on separate calibration; no outcome-driven model changes",
            "fold_assignment": "5 stratified signature folds; fold0 evaluates, fold1 calibrates, folds2-4 fit; family runs additionally exclude all family signatures from fit/calibration",
            "interpretation": "additional internal robustness evidence on previously inspected data; not a newly untouched external final test"},
        "checks": {"original_raw_files_unchanged": unchanged, "serving_artifact_unchanged": unchanged_artifact,
            "original_benchmark_confusion_and_metrics_reproduced": True, "signature_hash_matches_exact_equality": True,
            "all_new_partitions_pairwise_signature_disjoint": all(run["pairwise_signature_disjoint"] for run in runs)},
        "source_sha256": {name: file_sha256(root/name) for name in
            ("netguard_workflow/evaluation.py", "netguard_workflow/generalization.py", "netguard_workflow/generalization_report.py")}}
    reports = root/"data/reports"
    pd.DataFrame(results).to_csv(reports/"generalization_metrics.csv", index=False)
    pd.DataFrame(category_rows).to_csv(reports/"generalization_attack_categories.csv", index=False)
    (reports/"generalization.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")
    from .generalization_report import render_report
    (root/"notebooks/GENERALIZATION.md").write_text(render_report(report), encoding="utf-8", newline="\n")
    report["output_sha256"] = {path.name: file_sha256(path) for path in output.glob("*.csv")}
    (output/"manifest.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")
    print("Generalization evidence saved; raw files, serving artifact and threshold remain unchanged", flush=True)
    return report
