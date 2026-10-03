"""Keep unfamiliar-family signatures out of fitting and threshold calibration."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from run_unfamiliar_attack_experiment import novelty_partitions, normal_validation_threshold
from netguard_workflow.workflow import WorkflowConfig, input_signatures
from test_notebook_workflow import traffic


class UnfamiliarAttackChecks(unittest.TestCase):
    def test_withheld_family_and_shared_signatures_never_enter_fit_or_calibration(self):
        data = traffic()
        data.loc[(data.label == 1) & (data.index < 50), "attack_cat"] = "Withheld"
        fitting, validation, held = novelty_partitions(data, "Withheld", WorkflowConfig())
        forbidden = input_signatures(held)
        self.assertFalse(np.intersect1d(input_signatures(fitting), forbidden).size)
        self.assertFalse(np.intersect1d(input_signatures(validation), forbidden).size)
        self.assertTrue(fitting.label.eq(0).all())
        self.assertTrue(held.label.eq(1).all())

    def test_native_score_threshold_obeys_budget_without_attack_labels(self):
        scores = np.r_[np.repeat(10.0, 99), 100.0]
        threshold = normal_validation_threshold(scores, 0.01)
        self.assertEqual(int((scores >= threshold).sum()), 1)
        self.assertFalse((scores >= normal_validation_threshold(scores, 0.0)).any())
        self.assertFalse((np.ones(100) >= normal_validation_threshold(np.ones(100), 0.01)).any())


if __name__ == "__main__":
    unittest.main()
