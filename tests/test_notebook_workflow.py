"""Behaviour checks for the corrected workflow, using synthetic traffic only."""
import tempfile
import unittest
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from netguard_workflow.workflow import (
    RAW_INPUTS, RawTrafficFeatures, WorkflowConfig, fit_baselines,
    input_signatures, predict_raw, split_development,
)


def traffic():
    rng = np.random.default_rng(7)
    n = 200
    frame = pd.DataFrame({
        "sbytes": rng.integers(0, 10000, n), "dbytes": rng.integers(0, 5000, n),
        "spkts": rng.integers(0, 100, n), "dpkts": rng.integers(0, 100, n),
        "dur": rng.uniform(0, 10, n), "rate": rng.uniform(0, 100, n),
        "sload": rng.uniform(0, 10000, n), "dload": rng.uniform(0, 10000, n),
        "sttl": rng.integers(0, 255, n), "dttl": rng.integers(0, 255, n),
    })
    frame["label"] = (frame.sbytes > 5000).astype(int)
    frame["attack_cat"] = np.where(frame.label, "ExampleAttack", "Normal")
    # Duplicate measurements, including inconsistent labels, must stay together.
    duplicate = frame.iloc[:30].copy()
    duplicate["label"] = 1 - duplicate.label
    frame = pd.concat([frame, duplicate], ignore_index=True)
    frame["id"] = np.arange(1, len(frame) + 1)
    return frame


class WorkflowChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = traffic()
        cls.config = WorkflowConfig(max_iter=12)
        cls.fit, cls.validation, cls.groups = split_development(cls.data, cls.config)
        cls.bundle, cls.comparison = fit_baselines(cls.data, cls.fit, cls.validation, cls.config)

    def test_domain_features_use_raw_values_and_safe_zero_denominators(self):
        row = self.data.iloc[[0]].copy()
        row.loc[:, "sbytes"] = 100
        row.loc[:, "dbytes"] = 50
        row.loc[:, "spkts"] = 0
        row.loc[:, "dpkts"] = 5
        features = RawTrafficFeatures().transform(row).iloc[0]
        self.assertEqual(features.bytes_total, 150)
        self.assertEqual(features.pkts_total, 5)
        self.assertEqual(features.bytes_per_pkt_src, 0)
        self.assertEqual(features.src_zero_pkts, 1)
        self.assertEqual(features.bytes_per_pkt_dst, 10)

    def test_missing_and_nonfinite_measurements_fail_explicitly(self):
        with self.assertRaises(ValueError):
            RawTrafficFeatures().transform(self.data.drop(columns="dur"))
        broken = self.data.iloc[[0]].copy()
        broken.loc[:, "dur"] = np.inf
        with self.assertRaises(ValueError):
            predict_raw(self.bundle, broken)

    def test_duplicate_signatures_never_cross_development_split(self):
        self.assertEqual(len(np.intersect1d(self.groups[self.fit], self.groups[self.validation])), 0)
        again = split_development(self.data, self.config)
        np.testing.assert_array_equal(self.fit, again[0])
        np.testing.assert_array_equal(self.validation, again[1])

    def test_preprocessing_fitted_on_fit_rows_and_targets_excluded(self):
        scaler = self.bundle["pipeline"].named_steps["scaler"]
        expected = RawTrafficFeatures().transform(self.data.iloc[self.fit]).median().to_numpy()
        np.testing.assert_allclose(scaler.center_, expected, rtol=0, atol=0)
        altered = self.data.copy()
        altered["label"] = 1 - altered.label
        altered["attack_cat"] = "changed benchmark labels"
        np.testing.assert_array_equal(input_signatures(self.data), input_signatures(altered))
        np.testing.assert_array_equal(
            predict_raw(self.bundle, self.data).to_numpy(), predict_raw(self.bundle, altered).to_numpy()
        )

    def test_saved_predictions_are_independent_of_batch_composition(self):
        sample = self.data.iloc[:8].loc[:, list(RAW_INPUTS)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"model.joblib"
            joblib.dump(self.bundle, path)
            loaded = joblib.load(path)
            expected = predict_raw(self.bundle, sample)
            batch = predict_raw(loaded, sample)
            singles = pd.concat([predict_raw(loaded, sample.iloc[[i]]) for i in range(len(sample))])
        np.testing.assert_allclose(expected.attack_score, batch.attack_score, rtol=0, atol=1e-12)
        np.testing.assert_allclose(batch.attack_score, singles.attack_score, rtol=0, atol=1e-12)
        np.testing.assert_array_equal(batch.predicted_label, singles.predicted_label)


if __name__ == "__main__":
    unittest.main()
