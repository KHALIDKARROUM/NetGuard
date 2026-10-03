"""Complete raw-input prediction timing and the prespecified ensemble gate."""
from __future__ import annotations

from dataclasses import asdict
import io
import platform
import time

import joblib
import numpy as np

from .inference import (
    ARTIFACT_SCHEMA_VERSION, SCORE_CALIBRATION, feature_implementation_hash,
    model_implementation_hash, predict_raw, runtime_versions,
)
from .features import FEATURE_SCHEMA_VERSION, RAW_INPUTS, FEATURE_NAMES, feature_catalog


def candidate_bundle(name, pipeline, threshold, config, validation_metrics):
    return {
        "pipeline": pipeline, "threshold": threshold, "model_name": name,
        "config": asdict(config), "raw_inputs": list(RAW_INPUTS), "features": list(FEATURE_NAMES),
        "feature_schema_version": FEATURE_SCHEMA_VERSION, "feature_definitions": feature_catalog(),
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION, "precision": "float64",
        "runtime": runtime_versions(), "feature_implementation_sha256": feature_implementation_hash(),
        "model_implementation_sha256": model_implementation_hash(),
        "score_calibration": {**SCORE_CALIBRATION, "parameters": {}},
        "threshold_policy": "maximum validation recall under the configured false-positive budget; ties prefer fewer false positives, then higher threshold",
        "selection_policy": "best eligible individual by constrained validation recall, lower false-positive rate, average precision and name; ensemble requires prespecified recall gain and latency gates",
        "threshold_selection": {
            "partition": "grouped development validation; disjoint from model fitting",
            "max_false_positive_rate": config.max_false_positive_rate,
            "normal_rows": validation_metrics["tn"] + validation_metrics["fp"],
            "attack_rows": validation_metrics["tp"] + validation_metrics["fn"],
            "validation_metrics": validation_metrics,
            "interpretation": "empirical validation constraint; not a guarantee on other traffic",
        },
        "evaluation_status": "previously inspected benchmark; not an untouched holdout",
    }


def measure_prediction_latency(bundle, raw_validation, config):
    """Time actual predict_raw: features + fitted scaling + scores + threshold.

    Artifact loading and HTTP/network overhead are excluded. Inputs and the
    candidate remain loaded, as in a warm API worker. Include contract checks,
    result construction, and the serving thread limits in every timed call.
    """
    size = min(config.latency_batch_size, len(raw_validation))
    positions = np.linspace(0, len(raw_validation)-1, size, dtype=int)
    batch = raw_validation.iloc[positions].copy()
    predict_raw(bundle, batch.iloc[[0]])
    predict_raw(bundle, batch)
    singles, batches = [], []
    for i in range(config.latency_repeats):
        single = batch.iloc[[i % size]]
        started = time.perf_counter_ns()
        predict_raw(bundle, single)
        singles.append((time.perf_counter_ns()-started)/1e6)
        started = time.perf_counter_ns()
        predict_raw(bundle, batch)
        batches.append((time.perf_counter_ns()-started)/1e6)
    buffer = io.BytesIO()
    joblib.dump(bundle, buffer)
    return {
        "single_latency_median_ms": float(np.median(singles)),
        "single_latency_p95_ms": float(np.percentile(singles, 95)),
        "batch_latency_median_ms": float(np.median(batches)),
        "batch_latency_p95_ms": float(np.percentile(batches, 95)),
        "batch_rows": size, "batch_ms_per_row": float(np.median(batches)/size),
        "latency_repeats": config.latency_repeats, "artifact_bytes": buffer.tell(),
    }


def ensemble_gate(best_individual, ensemble, config):
    gain = float(ensemble["recall"]-best_individual["recall"])
    ratio = float(ensemble["batch_latency_median_ms"]/best_individual["batch_latency_median_ms"])
    gain_pass = gain >= config.ensemble_min_recall_gain
    latency_pass = ratio <= config.ensemble_max_latency_ratio
    eligible = bool(ensemble["eligible_for_selection"])
    return {
        "candidate": ensemble["model"], "best_individual": best_individual["model"],
        "retained": bool(eligible and gain_pass and latency_pass),
        "validation_recall_gain": gain, "minimum_recall_gain": config.ensemble_min_recall_gain,
        "batch_latency_ratio": ratio, "maximum_batch_latency_ratio": config.ensemble_max_latency_ratio,
        "gates": {"eligible": eligible, "recall_gain": gain_pass, "latency": latency_pass},
        "policy_declared_before_benchmark": True,
        "interpretation": "one grouped validation comparison; not proof of independent generalization",
    }


def latency_protocol(config):
    return {
        "scope": "complete warm predict_raw: raw feature creation, fitted scaling, model scoring, fixed threshold, contract checks and result construction",
        "excluded": ["artifact loading", "HTTP and network transport"],
        "batch_rows_requested": config.latency_batch_size, "repeats": config.latency_repeats,
        "warmups": {"single": 1, "batch": 1}, "threads": config.threads,
        "timer": "perf_counter_ns", "summaries": ["median", "p95"],
        "platform": platform.platform(), "processor": platform.processor(),
        "interpretation": "hardware-dependent sample timings; p95 is descriptive with a small sample count",
    }
