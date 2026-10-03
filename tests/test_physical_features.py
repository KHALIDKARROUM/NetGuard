"""Physical invariants, boundary cases and undefined-ratio behaviour."""
import unittest

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

from netguard_workflow.features import (
    FEATURE_NAMES, MAX_EXACT_COUNT, RawTrafficFeatures, feature_catalog, feature_quality_report,
)


def measurements(**changes):
    row = {"sbytes": 100, "dbytes": 50, "spkts": 4, "dpkts": 2,
           "dur": 2.0, "rate": 3.0, "sload": 100.0, "dload": 50.0,
           "sttl": 64, "dttl": 64}
    row.update(changes)
    return pd.DataFrame([row])


class PhysicalFeatureChecks(unittest.TestCase):
    def test_counts_have_physical_units_before_scaling(self):
        raw = pd.concat([measurements(), measurements(sbytes=0, spkts=0),
                         measurements(sbytes=0, dbytes=0, spkts=0, dpkts=0)], ignore_index=True)
        f = RawTrafficFeatures().transform(raw)
        np.testing.assert_array_equal(f.bytes_total, [150, 50, 0])
        np.testing.assert_array_equal(f.pkts_total, [6, 2, 0])
        np.testing.assert_array_equal(f.bytes_per_pkt_src, [25, 0, 0])
        np.testing.assert_array_equal(f.bytes_per_pkt_dst, [25, 25, 0])
        self.assertTrue(all(feature_quality_report(raw, f)["checks"].values()))

    def test_exact_ratios_and_signed_balance_have_defined_boundaries(self):
        raw = pd.concat([measurements(), measurements(sbytes=0), measurements(dbytes=0),
                         measurements(sbytes=0, dbytes=0)], ignore_index=True)
        f = RawTrafficFeatures().transform(raw)
        np.testing.assert_array_equal(f.bytes_ratio, [2, 0, 0, 0])
        np.testing.assert_array_equal(f.dst_zero_bytes, [0, 0, 1, 1])
        np.testing.assert_allclose(f.bytes_diff_normalized, [1/3, -1, 1, 0])
        np.testing.assert_array_equal(f.zero_total_bytes, [0, 0, 0, 1])
        np.testing.assert_allclose(f.bytes_ratio_smoothed, [101/51, 1/51, 101, 1])
        self.assertTrue(np.isfinite(f.to_numpy()).all())

    def test_zero_packet_sentinels_do_not_hide_positive_byte_inputs(self):
        raw = measurements(spkts=0, dpkts=0)
        f = RawTrafficFeatures().transform(raw).iloc[0]
        self.assertEqual(f.bytes_per_pkt_src, 0)
        self.assertEqual(f.bytes_per_pkt_dst, 0)
        self.assertEqual(f.src_zero_pkts, 1)
        self.assertEqual(f.dst_zero_pkts, 1)
        quality = feature_quality_report(raw)
        self.assertEqual(quality["positive_bytes_with_zero_packets"], {"source": 1, "destination": 1})

    def test_logs_recover_raw_values_and_do_not_clip_negative_inputs(self):
        raw = pd.concat([measurements(), measurements(sbytes=0, dbytes=0, dur=0, rate=0, sload=0, dload=0)], ignore_index=True)
        f = RawTrafficFeatures().transform(raw)
        for name in ("sbytes", "dbytes", "dur", "rate", "sload", "dload"):
            np.testing.assert_allclose(np.expm1(f[f"log1p_{name}"]), raw[name], rtol=1e-12, atol=1e-12)
            self.assertEqual(f.iloc[1][f"log1p_{name}"], 0)
        with self.assertRaises(ValueError):
            RawTrafficFeatures().transform(measurements(dbytes=-1))

    def test_ttl_rules_handle_zero_and_threshold_boundaries(self):
        raw = pd.concat([measurements(sttl=t, dttl=t) for t in [0, 1, 9, 10, 255]], ignore_index=True)
        f = RawTrafficFeatures().transform(raw)
        np.testing.assert_array_equal(f.src_low_ttl, [0, 1, 1, 0, 0])
        np.testing.assert_array_equal(f.dst_low_ttl, [0, 1, 1, 0, 0])
        for value in [-1, 1.5, 256]:
            with self.subTest(ttl=value), self.assertRaises(ValueError):
                RawTrafficFeatures().transform(measurements(sttl=value))

    def test_byte_and_packet_counts_are_integral_and_exactly_representable(self):
        for field in ["sbytes", "dbytes", "spkts", "dpkts"]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                RawTrafficFeatures().transform(measurements(**{field: 1.5}))
        with self.assertRaises(ValueError):
            RawTrafficFeatures().transform(measurements(sbytes=MAX_EXACT_COUNT, dbytes=1))

    def test_scaled_values_cannot_pass_the_raw_feature_completion_check(self):
        raw = pd.concat([measurements(), measurements(sbytes=500, spkts=10)], ignore_index=True)
        pipeline = Pipeline([("raw_features", RawTrafficFeatures()), ("scaler", RobustScaler())])
        transformed = pipeline.fit_transform(raw)
        unscaled = pipeline.named_steps["raw_features"].transform(raw)
        np.testing.assert_array_equal(unscaled.pkts_total, [6, 12])
        scaled = pd.DataFrame(transformed, columns=FEATURE_NAMES, index=raw.index)
        with self.assertRaises(AssertionError):
            feature_quality_report(raw, scaled)
        np.testing.assert_allclose(pipeline.named_steps["scaler"].center_, unscaled.median())

    def test_catalog_covers_every_predictor_in_the_model_order(self):
        catalog = feature_catalog()
        self.assertEqual([row["feature"] for row in catalog], list(FEATURE_NAMES))
        self.assertTrue(all(row["formula"] and row["meaning"] and row["unit"] and row["zero_policy"] for row in catalog))


if __name__ == "__main__":
    unittest.main()
