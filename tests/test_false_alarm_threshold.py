"""Validation-only operating points must obey an empirical false-alarm budget."""
import unittest

import numpy as np
import pandas as pd

from netguard_workflow.workflow import WorkflowConfig, _choose_threshold


def brute_force_threshold(labels, scores, budget):
    """Independent small-data oracle: enumerate every achievable alert set."""
    labels = np.asarray(labels)
    scores = np.asarray(scores, dtype=np.float64)
    candidates = np.append(np.unique(scores), np.nextafter(scores.max(), np.inf))
    normal_count = np.count_nonzero(labels == 0)
    eligible = []
    for threshold in candidates:
        alerts = scores >= threshold
        false_positives = np.count_nonzero(alerts & (labels == 0))
        true_positives = np.count_nonzero(alerts & (labels == 1))
        if false_positives / normal_count <= budget:
            eligible.append((true_positives, -false_positives, threshold))
    return float(max(eligible)[2])


class FalseAlarmThresholdChecks(unittest.TestCase):
    def test_one_percent_budget_includes_ties_as_a_whole(self):
        # The 0.7 tie admits a second false alarm; interpolation cannot split it.
        labels = np.array([0] * 100 + [1] * 5)
        scores = np.array([0.1] * 98 + [0.7, 0.9] + [0.95, 0.9, 0.8, 0.7, 0.6])
        threshold = _choose_threshold(labels, scores)
        self.assertEqual(threshold, 0.8)
        alerts = scores >= threshold
        self.assertEqual(np.count_nonzero(alerts & (labels == 0)), 1)
        self.assertEqual(np.count_nonzero(alerts & (labels == 1)), 3)

    def test_budget_below_one_possible_false_alarm_requires_zero(self):
        labels = np.array([0] * 80 + [1, 1])
        scores = np.array([0.1] * 79 + [0.9, 0.95, 0.9])
        self.assertEqual(_choose_threshold(labels, scores, 0.01), 0.95)
        self.assertEqual(_choose_threshold(labels, scores, 0.0), 0.95)

    def test_exact_budget_boundary_is_admissible(self):
        # floor(0.29 * 100) is 28 in binary floating point; 29/100 is admissible.
        normals = np.linspace(0.001, 0.5, 100)
        labels = np.array([0] * 100 + [1, 1])
        scores = np.append(normals, [0.99, normals[71]])
        self.assertEqual(_choose_threshold(labels, scores, 0.29), normals[71])

    def test_no_useful_feasible_alerts_returns_a_finite_reject_all_threshold(self):
        for scores in ([0.4, 0.4], [1.0, 1.0], [1.0, 0.1]):
            with self.subTest(scores=scores):
                threshold = _choose_threshold([0, 1], scores, 0.0)
                self.assertEqual(threshold, np.nextafter(max(scores), np.inf))
                self.assertTrue(np.isfinite(threshold))
                self.assertFalse(np.any(np.asarray(scores) >= threshold))

    def test_tied_recall_prefers_fewer_false_alarms_then_highest_threshold(self):
        # Threshold 0.1 has the same recall but more false alarms than 0.8.
        labels = np.array([0, 0, 0, 1, 1])
        scores = np.array([0.1, 0.1, 0.9, 0.8, 0.8])
        self.assertEqual(_choose_threshold(labels, scores, 0.5), 0.8)

    def test_matches_brute_force_and_is_invariant_to_input_order(self):
        rng = np.random.default_rng(71)
        for size in (4, 13, 40):
            for _ in range(25):
                labels = rng.integers(0, 2, size)
                labels[:2] = [0, 1]
                # Deliberate ties exercise only actually achievable alert sets.
                scores = rng.integers(0, 11, size).astype(np.float64) / 10
                original_labels, original_scores = labels.copy(), scores.copy()
                for budget in (0.0, 0.01, 0.29, 0.5, 0.99):
                    with self.subTest(size=size, budget=budget):
                        expected = brute_force_threshold(labels, scores, budget)
                        self.assertEqual(_choose_threshold(labels, scores, budget), expected)
                        order = rng.permutation(size)
                        self.assertEqual(
                            _choose_threshold(
                                pd.Series(labels[order], index=order + 100),
                                pd.Series(scores[order], index=order + 100), budget,
                            ), expected,
                        )
                np.testing.assert_array_equal(labels, original_labels)
                np.testing.assert_array_equal(scores, original_scores)

    def test_invalid_validation_data_fails_explicitly(self):
        invalid_cases = (
            ([], []), ([0], [0.1]), ([1, 1], [0.1, 0.2]),
            ([0, 2], [0.1, 0.2]), ([0, np.nan], [0.1, 0.2]),
            ([0, 1], [0.1]), ([0, 1], [0.1, np.nan]),
            ([0, 1], [0.1, np.inf]), ([0, 1], [-0.01, 0.5]),
            ([0, 1], [0.1, 1.01]), ([[0], [1]], [0.1, 0.2]),
            ([0, 1], [[0.1], [0.2]]),
        )
        for labels, scores in invalid_cases:
            with self.subTest(labels=labels, scores=scores):
                with self.assertRaises(ValueError):
                    _choose_threshold(labels, scores, 0.01)

    def test_invalid_budget_is_rejected_by_selector_and_configuration(self):
        self.assertEqual(WorkflowConfig().max_false_positive_rate, 0.01)
        self.assertEqual(WorkflowConfig(max_false_positive_rate=0).max_false_positive_rate, 0)
        for budget in (-0.01, 1.0, 1.01, np.nan, np.inf):
            with self.subTest(budget=budget):
                with self.assertRaises(ValueError):
                    _choose_threshold([0, 1], [0.1, 0.9], budget)
                with self.assertRaises(ValueError):
                    WorkflowConfig(max_false_positive_rate=budget)


if __name__ == "__main__":
    unittest.main()
