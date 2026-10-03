"""Check fair comparisons, actual serving-path timing and ensemble eligibility."""
import unittest
from unittest.mock import patch

import numpy as np
from sklearn.preprocessing import StandardScaler

from netguard_workflow.comparison import ensemble_gate, measure_prediction_latency
from netguard_workflow.models import MeanProbabilityClassifier
from netguard_workflow.workflow import WorkflowConfig, fit_baselines, split_development
from netguard_workflow.inference import predict_raw
from test_notebook_workflow import traffic


class SupervisedComparisonChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = traffic()
        cls.config = WorkflowConfig(max_iter=12, forest_trees=12, latency_repeats=3)
        cls.fit, cls.validation, _ = split_development(cls.data, cls.config)
        cls.bundle, cls.table = fit_baselines(cls.data, cls.fit, cls.validation, cls.config)

    def test_every_required_candidate_has_metrics_false_alarms_and_complete_latency(self):
        expected = {"dummy_prior", "logistic_regression", "random_forest", "hist_gradient_boosting", "supervised_soft_vote"}
        self.assertEqual(set(self.table.model), expected)
        required = ["accuracy", "balanced_accuracy", "precision", "recall", "f1", "roc_auc", "average_precision",
                    "false_positive_rate", "fp", "fn", "single_latency_median_ms", "single_latency_p95_ms",
                    "batch_latency_median_ms", "batch_latency_p95_ms", "batch_rows", "artifact_bytes", "converged"]
        self.assertTrue(self.table[required].notna().all().all())
        self.assertTrue((self.table.false_positive_rate <= self.config.max_false_positive_rate).all())
        self.assertTrue((self.table.single_latency_median_ms > 0).all())
        self.assertTrue((self.table.artifact_bytes > 0).all())
        self.assertEqual(int(self.table.selected.sum()), 1)
        self.assertEqual(self.table.loc[self.table.selected, "model"].iloc[0], self.bundle["model_name"])

    def test_models_share_fit_only_preprocessing_and_validation_membership(self):
        candidates = self.bundle["_comparison_candidates"]
        scalers = [candidate["pipeline"].named_steps["scaler"] for candidate in candidates.values()]
        self.assertTrue(all(scaler is scalers[0] for scaler in scalers))
        self.assertIsInstance(scalers[0], StandardScaler)
        for candidate in candidates.values():
            metrics = candidate["threshold_selection"]["validation_metrics"]
            self.assertEqual(metrics["rows"], len(self.validation))
            self.assertEqual(metrics["tn"]+metrics["fp"], int((self.data.iloc[self.validation].label == 0).sum()))

    def test_soft_vote_uses_fixed_equal_weights_without_refitting(self):
        candidates = self.bundle["_comparison_candidates"]
        ensemble = candidates["supervised_soft_vote"]["pipeline"]
        self.assertIsInstance(ensemble.named_steps["model"], MeanProbabilityClassifier)
        raw = self.data.iloc[self.validation[:5]]
        member_scores = [candidates[name]["pipeline"].predict_proba(raw) for name in
                         ("logistic_regression", "random_forest", "hist_gradient_boosting")]
        np.testing.assert_allclose(ensemble.predict_proba(raw), np.mean(member_scores, axis=0), rtol=0, atol=1e-12)
        with patch("sklearn.linear_model.LogisticRegression.fit", side_effect=AssertionError("No refitting")):
            ensemble.predict_proba(raw)

    def test_latency_exercises_raw_feature_creation_and_fixed_decisions(self):
        calls = []
        def observed(bundle, raw):
            calls.append(raw.shape)
            self.assertTrue(set(bundle["raw_inputs"]).issubset(raw.columns))
            result = predict_raw(bundle, raw)
            np.testing.assert_array_equal(result.predicted_label, result.attack_score >= bundle["threshold"])
            return result
        with patch("netguard_workflow.comparison.predict_raw", side_effect=observed):
            timing = measure_prediction_latency(self.bundle, self.data.iloc[self.validation], self.config)
        self.assertEqual(len(calls), 2+2*self.config.latency_repeats)
        self.assertEqual(timing["batch_rows"], min(len(self.validation), self.config.latency_batch_size))

    def test_ensemble_requires_both_recall_gain_and_latency_gates(self):
        individual = {"model": "individual", "recall": 0.5, "batch_latency_median_ms": 10}
        ensemble = {"model": "ensemble", "recall": 0.53, "batch_latency_median_ms": 15,
                    "eligible_for_selection": True}
        self.assertTrue(ensemble_gate(individual, ensemble, self.config)["retained"])
        self.assertFalse(ensemble_gate(individual, {**ensemble, "recall": 0.51}, self.config)["retained"])
        self.assertFalse(ensemble_gate(individual, {**ensemble, "batch_latency_median_ms": 21}, self.config)["retained"])
        self.assertFalse(ensemble_gate(individual, {**ensemble, "eligible_for_selection": False}, self.config)["retained"])


if __name__ == "__main__":
    unittest.main()
