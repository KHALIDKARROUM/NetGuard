"""Separate normal-only anomaly experiments with one attack family withheld."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from netguard_workflow.features import RawTrafficFeatures, RAW_INPUTS
from netguard_workflow.inference import runtime_versions
from netguard_workflow.workflow import WorkflowConfig, _read_raw, file_sha256, input_signatures, split_development


def novelty_partitions(development, family, config):
    """Exclude every held-out family signature from fitting and calibration."""
    held = development.loc[development.attack_cat == family].copy()
    if not len(held) or not held.label.eq(1).all():
        raise ValueError("Choose an attack family present in the development CSV.")
    fit, validation, signatures = split_development(development, config)
    forbidden = input_signatures(held)
    allowed = ~np.isin(signatures, forbidden)
    fit = fit[allowed[fit]]
    validation = validation[allowed[validation]]
    normal_fit = development.iloc[fit].loc[lambda frame: frame.label == 0].copy()
    known_validation = development.iloc[validation].copy()
    if not len(normal_fit) or not (known_validation.label == 0).any():
        raise ValueError("The family exclusion leaves insufficient normal development data.")
    assert not np.intersect1d(input_signatures(normal_fit), forbidden).size
    assert not np.intersect1d(input_signatures(known_validation), forbidden).size
    return normal_fit, known_validation, held


def normal_validation_threshold(scores, budget):
    scores = np.asarray(scores, dtype=np.float64)
    if scores.ndim != 1 or not len(scores) or not np.isfinite(scores).all():
        raise ValueError("Supply finite normal-only validation anomaly scores.")
    if not np.isfinite(budget) or not 0 <= budget < 1:
        raise ValueError("The false-positive budget must be in [0, 1).")
    allowed = int(np.flatnonzero(np.arange(len(scores)+1)/len(scores) <= budget)[-1])
    boundary = np.sort(scores)[::-1][allowed]
    threshold = float(np.nextafter(boundary, np.inf))
    if (scores >= threshold).mean() > budget:
        raise AssertionError("Normal validation threshold exceeds its false-positive budget")
    return threshold


def experiment(development, family, config, normal_fit_cap):
    normal_fit, known, held = novelty_partitions(development, family, config)
    fit = normal_fit.sample(min(len(normal_fit), normal_fit_cap), random_state=config.seed)
    features = RawTrafficFeatures().fit(fit)
    scaler = StandardScaler().fit(features.transform(fit))
    scaled_fit = scaler.transform(features.transform(fit))
    models = {
        "isolation_forest_novelty": IsolationForest(n_estimators=200, max_samples=256,
                                                    contamination="auto", random_state=config.seed, n_jobs=config.threads),
        "local_outlier_factor_novelty": LocalOutlierFactor(n_neighbors=35, novelty=True,
                                                         contamination="auto", n_jobs=config.threads),
    }
    rows, artifacts = [], {}
    normals = known.label.to_numpy() == 0
    attacks = ~normals
    for name, model in models.items():
        print(f"Normal-only unfamiliar-attack experiment: {name}", flush=True)
        with threadpool_limits(limits=config.threads):
            model.fit(scaled_fit)
            pipeline = Pipeline([("raw_features", features), ("scaler", scaler), ("model", model)])
            # Novelty LOF is scored only on groups absent from its fitting data.
            known_scores = -pipeline.score_samples(known.loc[:, list(RAW_INPUTS)])
            threshold = normal_validation_threshold(known_scores[normals], config.max_false_positive_rate)
            started = time.perf_counter()
            held_scores = -pipeline.score_samples(held.loc[:, list(RAW_INPUTS)])
            known_alerts, held_alerts = known_scores >= threshold, held_scores >= threshold
            held_prediction_s = time.perf_counter()-started
        rows.append({
            "model": name, "held_out_family": family, "normal_fit_rows": len(fit),
            "normal_validation_rows": int(normals.sum()), "known_attack_validation_rows": int(attacks.sum()),
            "held_out_attack_rows": len(held), "threshold": threshold,
            "false_positive_rate": float(known_alerts[normals].mean()),
            "false_positives": int(known_alerts[normals].sum()),
            "known_attack_recall": float(known_alerts[attacks].mean()) if attacks.any() else None,
            "held_out_attack_recall": float(held_alerts.mean()),
            "held_out_complete_prediction_seconds": held_prediction_s,
            "score_type": "negative native score_samples; higher means more anomalous",
        })
        artifacts[name] = {"pipeline": pipeline, "threshold": threshold,
                           "held_out_family": family, "runtime": runtime_versions(),
                           "threshold_partition": "normal-only grouped development validation",
                           "score_calibration": "none; native anomaly scores",
                           "purpose": "offline unfamiliar-attack experiment; not a serving artifact"}
    return rows, artifacts, {"normal_fit_rows_available": len(normal_fit), "normal_fit_cap": normal_fit_cap,
                             "held_out_signatures_excluded_from_fit_and_validation": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", default="Backdoor")
    parser.add_argument("--normal-fit-cap", type=int, default=5000)
    parser.add_argument("--output-dir", type=Path, default=ROOT/"artifacts/novelty_experiments")
    args = parser.parse_args()
    if args.normal_fit_cap < 36:
        raise ValueError("Supply at least 36 normal fitting rows for the declared LOF neighborhood")
    config = WorkflowConfig()
    path = ROOT/"data/UNSW_NB15_training-set.csv"
    development = _read_raw(path)
    rows, artifacts, partition_checks = experiment(development, args.family, config, args.normal_fit_cap)
    output = args.output_dir.resolve()/args.family.lower()
    output.mkdir(parents=True, exist_ok=True)
    for name, artifact in artifacts.items():
        joblib.dump(artifact, output/f"{name}.joblib")
    report = {"status": "passed", "created_utc": datetime.now(timezone.utc).isoformat(),
              "family": args.family, "runtime": runtime_versions(), "input_sha256": file_sha256(path),
              "max_validation_false_positive_rate": config.max_false_positive_rate,
              "results": rows, "partition_checks": partition_checks,
              "data_used": "development CSV only; no benchmark CSV read",
              "scope": "one prespecified withheld family, normal-only fitted models and normal-only validation threshold; no supervised selection or deployment changes",
              "limitations": "familiar dataset, capped normal fit sample, no capture/host isolation, no uncertainty estimate; repeat across families before drawing a general conclusion"}
    report_path = ROOT/"data/reports"/f"unfamiliar_attack_{args.family.lower()}.json"
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n", encoding="utf-8", newline="\n")
    pd.DataFrame(rows).to_csv(output/"comparison.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False), flush=True)
    print(f"Saved experiment evidence: {report_path}", flush=True)


if __name__ == "__main__":
    main()
