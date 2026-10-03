"""Independently check saved predictions, metrics and every experiment partition."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, auc, confusion_matrix, precision_recall_curve

from netguard_workflow.features import RAW_INPUTS
from netguard_workflow.inference import PredictionService
from netguard_workflow.workflow import WorkflowConfig, file_sha256, input_signatures, load_raw_data, split_development


def check_metrics(frame, record, repeats):
    scores = frame.attack_score.to_numpy()
    predictions = (scores >= record["threshold"]).astype(np.int8)
    np.testing.assert_array_equal(predictions, frame.predicted_label)
    tn, fp, fn, tp = confusion_matrix(frame.true_label, predictions, labels=[0, 1]).ravel()
    def ratio(a, b):
        return a/b if b else None
    values = {"rows": len(frame), "normal_rows": int((frame.true_label == 0).sum()),
              "attack_rows": int((frame.true_label == 1).sum()), "tn": tn, "fp": fp, "fn": fn, "tp": tp,
              "precision": ratio(tp, tp+fp), "recall": ratio(tp, tp+fn),
              "f1": ratio(2*tp, 2*tp+fp+fn), "false_positive_rate": ratio(fp, fp+tn),
              "pr_auc": None, "average_precision": None}
    if values["normal_rows"] and values["attack_rows"]:
        p, r, _ = precision_recall_curve(frame.true_label, scores)
        values["pr_auc"] = auc(r, p)
        values["average_precision"] = average_precision_score(frame.true_label, scores)
    for name, expected in values.items():
        if expected is None:
            assert record[name] is None, name
        else:
            np.testing.assert_allclose(record[name], expected, rtol=0, atol=1e-12, err_msg=name)
    for metric in ("precision", "recall", "f1", "pr_auc", "average_precision", "false_positive_rate"):
        low, high = record[f"{metric}_ci_low"], record[f"{metric}_ci_high"]
        if low is not None:
            assert 0 <= low <= high <= 1
            assert record[f"{metric}_bootstrap_valid"] >= max(20, int(.8*repeats))


def main():
    report = json.loads((ROOT/"data/reports/generalization.json").read_text(encoding="utf-8"))
    output = ROOT/"artifacts/generalization"
    manifest = json.loads((output/"manifest.json").read_text(encoding="utf-8"))
    for name, digest in manifest["output_sha256"].items():
        assert file_sha256(output/name) == digest, name
    for name, digest in report["input_sha256"].items():
        assert file_sha256(ROOT/"data"/name) == digest, name
    for name, digest in report["source_sha256"].items():
        assert file_sha256(ROOT/name) == digest, name
    service = PredictionService(ROOT/"models_saved/shared_pipeline.joblib")
    assert service.artifact_sha256 == report["serving_artifact_sha256"]
    assert service.bundle["threshold"] == report["serving_threshold"]
    development, benchmark = load_raw_data(ROOT)
    fit, _, _ = split_development(development, WorkflowConfig(**service.bundle["config"]))
    benchmark_predictions = pd.read_csv(output/"benchmark_predictions.csv", float_precision="round_trip")
    for name, reference in (("seen_in_fit", development.iloc[fit]), ("seen_in_any_development", development)):
        keys = pd.MultiIndex.from_frame(benchmark.loc[:, list(RAW_INPUTS)].astype(np.float64))
        reference_keys = pd.MultiIndex.from_frame(reference.loc[:, list(RAW_INPUTS)].astype(np.float64))
        np.testing.assert_array_equal(benchmark_predictions[name], keys.isin(reference_keys))
    scopes = {}
    for record in report["evaluation"]:
        scope = record["scope"]
        if scope.startswith("benchmark_"):
            frame = benchmark_predictions
            if scope == "benchmark_seen_in_fit":
                frame = frame.loc[frame.seen_in_fit]
            elif scope == "benchmark_unseen_in_fit":
                frame = frame.loc[~frame.seen_in_fit]
            elif scope == "benchmark_unseen_in_any_development":
                frame = frame.loc[~frame.seen_in_any_development]
            raw = benchmark.set_index("id").loc[frame.row_id]
        else:
            frame = pd.read_csv(output/f"{scope}_predictions.csv", float_precision="round_trip")
            raw = development.set_index("id").loc[frame.row_id]
        assert not frame.row_id.duplicated().any()
        np.testing.assert_array_equal(raw.label, frame.true_label)
        np.testing.assert_array_equal(raw.attack_cat, frame.attack_category)
        assert len(np.unique(input_signatures(raw))) == record["unique_signatures"]
        check_metrics(frame, record, report["uncertainty"]["repetitions"])
        scopes[scope] = frame
    for record in report["attack_categories"]:
        frame = scopes[record["scope"]]
        frame = frame.loc[(frame.true_label == 0) | ((frame.true_label == 1) & (frame.attack_category == record["attack_category"]))]
        check_metrics(frame, record, report["uncertainty"]["repetitions"])
    signatures = input_signatures(development)
    for run in report["experiments"]:
        split = pd.read_csv(output/f"{run['scope']}_membership.csv")
        np.testing.assert_array_equal(split.row_id, development.id)
        assert set(split.partition).issubset({"fit", "calibration", "evaluation", "excluded_family_signature", "excluded_known_attack"})
        groups = {}
        for phase in ("fit", "calibration", "evaluation"):
            mask = split.partition.eq(phase).to_numpy()
            assert int(mask.sum()) == run[f"{phase}_rows"]
            groups[phase] = signatures[mask]
        for left, right in (("fit", "calibration"), ("fit", "evaluation"), ("calibration", "evaluation")):
            assert not np.intersect1d(groups[left], groups[right]).size
        np.testing.assert_array_equal(np.sort(split.loc[split.partition == "evaluation", "row_id"]),
                                      np.sort(scopes[run["scope"]].row_id))
        calibration = development.loc[split.partition.eq("calibration").to_numpy()]
        metrics = run["calibration_metrics"]
        assert metrics["tn"]+metrics["fp"] == int((calibration.label == 0).sum())
        assert metrics["tp"]+metrics["fn"] == int((calibration.label == 1).sum())
        assert metrics["false_positive_rate"] <= run["configuration"]["max_false_positive_rate"]
        if run["held_out_family"]:
            held = (development.attack_cat == run["held_out_family"]) & (development.label == 1)
            forbidden = signatures[held]
            for phase in ("fit", "calibration"):
                assert not np.intersect1d(forbidden, groups[phase]).size
            assert set(development.loc[held, "id"]).issubset(scopes[run["scope"]].row_id)
            excluded = split.partition.eq("excluded_family_signature").to_numpy()
            assert np.isin(signatures[excluded], forbidden).all()
            unused = split.partition.eq("excluded_known_attack").to_numpy()
            assert not np.isin(signatures[unused], forbidden).any()
    evidence = {"status": "passed", "verified_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_scopes": len(report["evaluation"]), "category_comparisons": len(report["attack_categories"]),
        "experimental_partitions_checked": len(report["experiments"]), "output_files_hash_checked": len(manifest["output_sha256"]),
        "serving_artifact_sha256": service.artifact_sha256,
        "checks": ["input/source/output hashes", "original benchmark signature equality", "row identity and label/category alignment",
            "frozen decisions and confusion counts", "precision/recall/F1/FPR", "PR-AUC and AP against sklearn",
            "interval bounds and valid draws", "all split memberships and pairwise group isolation",
            "complete family-signature exclusion", "calibration class counts and false-positive budgets"]}
    # Older full runners also gain the same consistent publication when this
    # independent verifier runs after their completed end-to-end execution.
    from notebook_integrity import publish_full_generalization_execution
    publish_full_generalization_execution(ROOT)
    (ROOT/"data/reports/generalization_verification.json").write_text(
        json.dumps(evidence, indent=2)+"\n", encoding="utf-8", newline="\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
