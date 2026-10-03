"""Check uncertainty, metric definitions and independent calibration boundaries."""
import unittest
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, auc, precision_recall_curve
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from netguard_workflow.evaluation import (
    _weighted_metrics, evaluate_frame, metrics_with_uncertainty, seen_signatures, three_way_partition, partition_membership,
)
from netguard_workflow.workflow import input_signatures
from netguard_workflow.features import RawTrafficFeatures
from netguard_workflow.models import MeanProbabilityClassifier
from netguard_workflow.generalization import fit_frozen_design
from netguard_workflow.workflow import WorkflowConfig
from netguard_workflow.inference import predict_raw
from test_notebook_workflow import traffic


class GeneralizationEvaluationChecks(unittest.TestCase):
    def test_tied_weighted_pr_metrics_match_sklearn(self):
        labels = np.array([0, 1, 0, 1, 1, 0])
        scores = np.array([.2, .8, .8, .2, .9, .1])
        order = np.argsort(-scores, kind="stable")
        ends = np.flatnonzero(np.r_[scores[order][:-1] != scores[order][1:], True])
        for weights in (np.ones(6), np.array([1, 0, 3, 2, 4, 0])):
            values, _ = _weighted_metrics(labels, scores, .8, weights, order, ends)
            p, r, _ = precision_recall_curve(labels, scores, sample_weight=weights)
            self.assertAlmostEqual(values["pr_auc"], auc(r, p), places=14)
            self.assertAlmostEqual(values["average_precision"],
                                   average_precision_score(labels, scores, sample_weight=weights), places=14)

    def test_whole_signature_bootstrap_preserves_repeated_rows(self):
        # Two internally identical, opposite classes: whole-cluster draws can
        # lack a class; row resampling would incorrectly hide this dependence.
        labels = np.r_[np.zeros(50), np.ones(50)]
        scores = np.r_[np.full(50, .1), np.full(50, .9)]
        groups = np.r_[np.zeros(50), np.ones(50)]
        result = metrics_with_uncertainty(labels, scores, .5, groups, repeats=100, seed=7)
        self.assertEqual(result["unique_signatures"], 2)
        self.assertLess(result["average_precision_bootstrap_valid"], 80)
        self.assertIsNone(result["average_precision_ci_low"])
        self.assertEqual(result, metrics_with_uncertainty(labels, scores, .5, groups, repeats=100, seed=7))

    def test_undefined_denominators_and_sparse_uncertainty(self):
        result = metrics_with_uncertainty([1, 1], [.2, .3], .9, [4, 4], repeats=20)
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["false_positive_rate"])
        self.assertIsNone(result["pr_auc"])
        self.assertIsNone(result["recall_ci_low"])
        self.assertEqual(result["recall"], 0)
        self.assertIn("not estimable", result["uncertainty_flags"])

    def test_category_metrics_compare_only_family_and_normals(self):
        data = traffic().iloc[:8].copy()
        data["label"] = [0, 0, 0, 0, 1, 1, 1, 1]
        data["attack_cat"] = ["Normal"]*4+["A", "A", "B", "B"]
        scores = [.9, .1, .1, .1, .9, .1, .9, .9]
        _, categories = evaluate_frame(data, scores, .5, scope="test", repeats=20)
        a = next(row for row in categories if row["attack_category"] == "A")
        b = next(row for row in categories if row["attack_category"] == "B")
        self.assertEqual(a["rows"], 6)
        self.assertEqual(a["tp"], 1)
        self.assertEqual(a["fp"], 1)
        self.assertEqual(a["precision"], .5)
        self.assertEqual(a["false_positive_rate"], b["false_positive_rate"])

    def test_seen_signatures_ignore_targets_and_distinguish_fitting_from_validation(self):
        data = traffic()
        altered = data.iloc[:1].copy()
        altered["id"] = 900
        altered["label"] = 1-altered.label
        altered["attack_cat"] = "other"
        self.assertTrue(seen_signatures(altered, data.iloc[:1])[0])
        self.assertFalse(seen_signatures(altered, data.iloc[30:31])[0])

    def test_three_way_partitions_and_family_signature_exclusion(self):
        data = traffic()
        data.loc[data.label == 1, "attack_cat"] = "Known"
        held = data.index[(data.label == 1)][:5]
        data.loc[held, "attack_cat"] = "Held"
        signatures = input_signatures(data)
        for family in (None, "Held"):
            fit, calibration, evaluation, checks = three_way_partition(data, held_family=family)
            self.assertTrue(checks["pairwise_signature_disjoint"])
            for left, right in ((fit, calibration), (fit, evaluation), (calibration, evaluation)):
                self.assertFalse(np.intersect1d(signatures[left], signatures[right]).size)
            if family:
                forbidden = signatures[data.attack_cat.eq(family)]
                self.assertFalse(np.intersect1d(signatures[fit], forbidden).size)
                self.assertFalse(np.intersect1d(signatures[calibration], forbidden).size)
                self.assertTrue(set(held).issubset(evaluation))
                membership = partition_membership(data, fit, calibration, evaluation, held_family=family)
                self.assertEqual(len(membership), len(data))
                excluded = membership.partition.eq("excluded_family_signature").to_numpy()
                self.assertTrue(np.isin(signatures[excluded], forbidden).all())
                unused_known = membership.partition.eq("excluded_known_attack").to_numpy()
                self.assertFalse(np.isin(signatures[unused_known], forbidden).any())
                self.assertTrue(data.loc[unused_known, "label"].eq(1).all())

    def test_frozen_design_and_threshold_do_not_use_evaluation_rows(self):
        data = traffic()
        fit, calibration, evaluation, _ = three_way_partition(data)
        model = MeanProbabilityClassifier([
            ("linear", LogisticRegression(max_iter=2000)),
            ("forest", RandomForestClassifier(n_estimators=8, random_state=42)),
            ("boosting", HistGradientBoostingClassifier(max_iter=8, early_stopping=False, random_state=42)),
        ])
        template = {"pipeline": Pipeline([("raw_features", RawTrafficFeatures()),
                     ("scaler", StandardScaler()), ("model", model)]), "model_name": "fixed_test_vote"}
        config = WorkflowConfig(max_iter=8, forest_trees=8, latency_repeats=3)
        first, diagnostics = fit_frozen_design(template, data, fit, calibration, config)
        altered = data.copy()
        altered.loc[evaluation, "label"] = 1-altered.loc[evaluation, "label"]
        altered.loc[evaluation, "sbytes"] = 1000000
        second, _ = fit_frozen_design(template, altered, fit, calibration, config)
        np.testing.assert_array_equal(predict_raw(first, data).to_numpy(), predict_raw(second, data).to_numpy())
        self.assertEqual(first["threshold"], second["threshold"])
        self.assertLessEqual(diagnostics["calibration_metrics"]["false_positive_rate"], .01)
        expected = RawTrafficFeatures().transform(data.iloc[fit]).mean().to_numpy()
        np.testing.assert_allclose(first["pipeline"].named_steps["scaler"].mean_, expected, atol=1e-12, rtol=0)


if __name__ == "__main__":
    unittest.main()
