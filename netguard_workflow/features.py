"""Physical traffic features calculated before any learned preprocessing."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

FEATURE_SCHEMA_VERSION = 2
# Integer counts stored as float64 must remain exactly representable, including totals.
MAX_EXACT_COUNT = 2**53 - 1
RAW_INPUTS = (
    "sbytes", "dbytes", "spkts", "dpkts", "dur", "rate",
    "sload", "dload", "sttl", "dttl",
)
DERIVED_INPUTS = (
    "bytes_total", "pkts_total", "bytes_per_pkt_src", "bytes_per_pkt_dst",
    "bytes_ratio", "bytes_ratio_smoothed", "bytes_diff_normalized",
    "src_zero_pkts", "dst_zero_pkts", "dst_zero_bytes", "zero_total_bytes",
    "src_low_ttl", "dst_low_ttl", "log1p_sbytes", "log1p_dbytes",
    "log1p_dur", "log1p_rate", "log1p_sload", "log1p_dload",
)
FEATURE_NAMES = RAW_INPUTS + DERIVED_INPUTS
COUNT_INPUTS = ("sbytes", "dbytes", "spkts", "dpkts")
LOG_INPUTS = ("sbytes", "dbytes", "dur", "rate", "sload", "dload")
INDICATORS = (
    "src_zero_pkts", "dst_zero_pkts", "dst_zero_bytes", "zero_total_bytes",
    "src_low_ttl", "dst_low_ttl",
)


def _safe_divide(numerator, denominator):
    """Return zero for an undefined zero denominator; companion flags retain it."""
    return np.divide(
        numerator, denominator, out=np.zeros(len(numerator), dtype=np.float64),
        where=np.asarray(denominator) > 0,
    )


class RawTrafficFeatures(TransformerMixin, BaseEstimator):
    """A stateless float64 transformation of ten measured raw input fields.

    Exact totals keep byte/packet units. Undefined ratios have a zero sentinel
    plus an explicit flag; they are not interpreted as observed zero ratios.
    The smoothed byte ratio uses one byte as a declared pseudocount. TTL flags
    are candidate predictors and do not independently classify an attack.
    """

    def fit(self, X, y=None):
        self.feature_schema_version_ = FEATURE_SCHEMA_VERSION
        self.transform(X)
        self.n_features_in_ = len(RAW_INPUTS)
        self.feature_names_in_ = np.asarray(RAW_INPUTS, dtype=object)
        return self

    def transform(self, X):
        if hasattr(self, "n_features_in_") and getattr(self, "feature_schema_version_", None) != FEATURE_SCHEMA_VERSION:
            raise ValueError("This model uses an earlier feature schema; retrain from raw data.")
        if not isinstance(X, pd.DataFrame):
            raise TypeError("Supply raw measurements as a pandas DataFrame.")
        if not X.columns.is_unique:
            raise ValueError("Raw measurement column names must be unique.")
        missing = sorted(set(RAW_INPUTS) - set(X.columns))
        if missing:
            raise ValueError(f"Missing required raw measurements: {missing}")
        f = X.loc[:, list(RAW_INPUTS)].astype(np.float64).copy()
        values = f.to_numpy()
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError("Raw measurements must be finite and nonnegative.")
        for col in (*COUNT_INPUTS, "sttl", "dttl"):
            if (f[col] != np.floor(f[col])).any():
                raise ValueError(f"{col} must contain integer measurements.")
        if (f.loc[:, ["sttl", "dttl"]] > 255).any().any():
            raise ValueError("TTL measurements must be between 0 and 255.")
        if (f.loc[:, list(COUNT_INPUTS)] > MAX_EXACT_COUNT).any().any():
            raise ValueError("Byte/packet counts exceed exact float64 integer precision.")
        f["bytes_total"] = f.sbytes + f.dbytes
        f["pkts_total"] = f.spkts + f.dpkts
        if (f.loc[:, ["bytes_total", "pkts_total"]] > MAX_EXACT_COUNT).any().any():
            raise ValueError("Byte/packet totals exceed exact float64 integer precision.")
        for direction, byte_col, packet_col in (
            ("src", "sbytes", "spkts"), ("dst", "dbytes", "dpkts")
        ):
            f[f"bytes_per_pkt_{direction}"] = _safe_divide(f[byte_col], f[packet_col])
            f[f"{direction}_zero_pkts"] = (f[packet_col] == 0).astype(np.float64)
        f["bytes_ratio"] = _safe_divide(f.sbytes, f.dbytes)
        f["dst_zero_bytes"] = (f.dbytes == 0).astype(np.float64)
        f["bytes_ratio_smoothed"] = (f.sbytes + 1.0) / (f.dbytes + 1.0)
        f["bytes_diff_normalized"] = _safe_divide(f.sbytes - f.dbytes, f.bytes_total)
        f["zero_total_bytes"] = (f.bytes_total == 0).astype(np.float64)
        f["src_low_ttl"] = ((f.sttl > 0) & (f.sttl < 10)).astype(np.float64)
        f["dst_low_ttl"] = ((f.dttl > 0) & (f.dttl < 10)).astype(np.float64)
        for col in LOG_INPUTS:
            # One reference unit (byte, second, or the supplied rate/load unit).
            f[f"log1p_{col}"] = np.log1p(f[col])
        result = f.loc[:, list(FEATURE_NAMES)]
        if not np.isfinite(result.to_numpy()).all():
            raise ValueError("Feature calculations overflowed; check raw measurements.")
        return result

    def get_feature_names_out(self, input_features=None):
        return np.asarray(FEATURE_NAMES, dtype=object)


def feature_catalog():
    """Return the definition of every unscaled model input, in fitted feature order."""
    raw = {
        "sbytes": ("Source-to-destination byte count", "bytes"),
        "dbytes": ("Destination-to-source byte count", "bytes"),
        "spkts": ("Source-to-destination packet count", "packets"),
        "dpkts": ("Destination-to-source packet count", "packets"),
        "dur": ("Recorded connection duration", "seconds"),
        "rate": ("Connection rate supplied by the dataset; not recomputed", "original dataset rate units"),
        "sload": ("Recorded source load; not recomputed", "original dataset load units"),
        "dload": ("Recorded destination load; not recomputed", "original dataset load units"),
        "sttl": ("Recorded source packet time-to-live value", "TTL value"),
        "dttl": ("Recorded destination packet time-to-live value", "TTL value"),
    }
    rows = {}
    for name, (meaning, unit) in raw.items():
        rows[name] = {"feature": name, "meaning": meaning, "unit": unit,
                      "formula": "measured raw input", "zero_policy": "Retain recorded zero; never substitute a median."}
    definitions = {
        "bytes_total": ("Total recorded bytes in both directions", "bytes", "sbytes + dbytes", "0 when both byte counts are 0."),
        "pkts_total": ("Total recorded packets in both directions", "packets", "spkts + dpkts", "0 when both packet counts are 0."),
        "bytes_per_pkt_src": ("Source bytes per recorded source packet", "bytes/packet", "sbytes / spkts", "If spkts=0, use 0 sentinel and src_zero_pkts=1."),
        "bytes_per_pkt_dst": ("Destination bytes per recorded destination packet", "bytes/packet", "dbytes / dpkts", "If dpkts=0, use 0 sentinel and dst_zero_pkts=1."),
        "bytes_ratio": ("Exact source/destination byte ratio when defined", "dimensionless", "sbytes / dbytes", "If dbytes=0, use 0 sentinel and dst_zero_bytes=1."),
        "bytes_ratio_smoothed": ("Source/destination byte ratio with a one-byte pseudocount", "dimensionless", "(sbytes + 1 byte) / (dbytes + 1 byte)", "Always defined; both zero gives 1. This is a smoothed ratio, not an exact measured ratio."),
        "bytes_diff_normalized": ("Signed directional byte balance: -1 destination-only, +1 source-only", "dimensionless [-1, 1]", "(sbytes - dbytes) / bytes_total", "If bytes_total=0, use 0 sentinel and zero_total_bytes=1."),
        "src_zero_pkts": ("Source bytes-per-packet denominator is zero", "binary 0/1", "1 if spkts == 0 else 0", "1 includes both all-zero and inconsistent positive-byte/zero-packet inputs."),
        "dst_zero_pkts": ("Destination bytes-per-packet denominator is zero", "binary 0/1", "1 if dpkts == 0 else 0", "1 includes both all-zero and inconsistent positive-byte/zero-packet inputs."),
        "dst_zero_bytes": ("Exact byte-ratio denominator is zero", "binary 0/1", "1 if dbytes == 0 else 0", "Disambiguates the undefined-ratio sentinel from a measured zero ratio."),
        "zero_total_bytes": ("No recorded bytes in either direction", "binary 0/1", "1 if bytes_total == 0 else 0", "Disambiguates undefined byte balance from equal nonzero byte counts."),
        "src_low_ttl": ("Candidate low source TTL indicator; does not prove an attack", "binary 0/1", "1 if 0 < sttl < 10 else 0", "TTL=0 is not marked low. No missing TTL is inferred."),
        "dst_low_ttl": ("Candidate low destination TTL indicator; does not prove an attack", "binary 0/1", "1 if 0 < dttl < 10 else 0", "TTL=0 is not marked low. No missing TTL is inferred."),
    }
    for name, (meaning, unit, formula, zero_policy) in definitions.items():
        rows[name] = {"feature": name, "meaning": meaning, "unit": unit,
                      "formula": formula, "zero_policy": zero_policy}
    for name in LOG_INPUTS:
        key = f"log1p_{name}"
        rows[key] = {
            "feature": key, "meaning": f"Natural-log compression of raw {name}; no clipping of scaled values",
            "unit": "dimensionless log value",
            "formula": f"ln(1 + {name} / 1 reference unit [{raw[name][1]}])",
            "zero_policy": "Raw zero maps to zero. Negative/nonfinite raw measurements are rejected.",
        }
    return [rows[name] for name in FEATURE_NAMES]


def feature_quality_report(raw, features=None):
    """Assert raw physical invariants and return compact full-dataset evidence."""
    f = RawTrafficFeatures().transform(raw) if features is None else features
    if list(f.columns) != list(FEATURE_NAMES) or not f.index.equals(raw.index):
        raise AssertionError("Feature order and row index must match the raw input contract.")
    checks = {
        "all_values_finite": bool(np.isfinite(f.to_numpy()).all()),
        "raw_measurements_unchanged": bool(np.array_equal(
            f.loc[:, list(RAW_INPUTS)].to_numpy(), raw.loc[:, list(RAW_INPUTS)].to_numpy(dtype=np.float64)
        )),
        "byte_total_matches_raw": bool(np.array_equal(f.bytes_total, raw.sbytes + raw.dbytes)),
        "packet_total_matches_raw": bool(np.array_equal(f.pkts_total, raw.spkts + raw.dpkts)),
        "nonnegative_integer_counts": bool(all(
            ((f[col] >= 0) & (f[col] == np.floor(f[col]))).all()
            for col in (*COUNT_INPUTS, "bytes_total", "pkts_total")
        )),
        "nonnegative_features_except_signed_byte_balance": bool(
            (f.drop(columns="bytes_diff_normalized") >= 0).all().all()
        ),
        "signed_byte_balance_in_bounds": bool(f.bytes_diff_normalized.between(-1, 1).all()),
        "indicators_binary": bool(f.loc[:, list(INDICATORS)].isin([0, 1]).all().all()),
        "ttl_values_in_range": bool(f.loc[:, ["sttl", "dttl"]].ge(0).all().all() and
                                    f.loc[:, ["sttl", "dttl"]].le(255).all().all()),
    }
    for direction, byte_col, packet_col in (("src", "sbytes", "spkts"), ("dst", "dbytes", "dpkts")):
        defined = raw[packet_col] > 0
        checks[f"{direction}_bytes_per_packet_defined_values"] = bool(np.allclose(
            f.loc[defined, f"bytes_per_pkt_{direction}"] * raw.loc[defined, packet_col],
            raw.loc[defined, byte_col], rtol=1e-12, atol=1e-12,
        ))
        checks[f"{direction}_zero_packet_policy"] = bool(
            (f.loc[~defined, f"bytes_per_pkt_{direction}"] == 0).all() and
            np.array_equal(f[f"{direction}_zero_pkts"], (~defined).astype(float))
        )
    defined = raw.dbytes > 0
    checks["exact_byte_ratio_defined_values"] = bool(np.allclose(
        f.loc[defined, "bytes_ratio"] * raw.loc[defined, "dbytes"], raw.loc[defined, "sbytes"],
        rtol=1e-12, atol=1e-12,
    ))
    checks["zero_byte_ratio_policy"] = bool(
        (f.loc[~defined, "bytes_ratio"] == 0).all() and
        np.array_equal(f.dst_zero_bytes, (~defined).astype(float))
    )
    checks["smoothed_byte_ratio_matches_raw"] = bool(np.allclose(
        f.bytes_ratio_smoothed, (raw.sbytes + 1.0) / (raw.dbytes + 1.0), rtol=1e-12, atol=1e-12,
    ))
    no_bytes = (raw.sbytes + raw.dbytes) == 0
    checks["zero_total_byte_policy"] = bool(
        (f.loc[no_bytes, "bytes_diff_normalized"] == 0).all() and
        np.array_equal(f.zero_total_bytes, no_bytes.astype(float))
    )
    checks["signed_byte_balance_matches_raw"] = bool(np.allclose(
        f.loc[~no_bytes, "bytes_diff_normalized"] * (raw.loc[~no_bytes, "sbytes"] + raw.loc[~no_bytes, "dbytes"]),
        raw.loc[~no_bytes, "sbytes"] - raw.loc[~no_bytes, "dbytes"], rtol=1e-12, atol=1e-12,
    ))
    checks["logarithms_recover_raw_measurements"] = bool(all(np.allclose(
        np.expm1(f[f"log1p_{col}"]), raw[col], rtol=1e-12, atol=1e-12,
    ) for col in LOG_INPUTS))
    checks["ttl_rules_use_raw_measurements"] = bool(all(np.array_equal(
        f[f"{direction}_low_ttl"], ((raw[col] > 0) & (raw[col] < 10)).astype(float),
    ) for direction, col in (("src", "sttl"), ("dst", "dttl"))))
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise AssertionError(f"Physical feature checks failed: {failed}")
    return {
        "rows": len(raw), "feature_count": len(FEATURE_NAMES), "schema_version": FEATURE_SCHEMA_VERSION,
        "precision": "float64; byte/packet counts remain integer-valued",
        "checks": checks,
        "zero_denominator_rows": {
            "source_packets": int((raw.spkts == 0).sum()),
            "destination_packets": int((raw.dpkts == 0).sum()),
            "destination_bytes": int((raw.dbytes == 0).sum()),
            "total_bytes": int(no_bytes.sum()),
        },
        "positive_bytes_with_zero_packets": {
            "source": int(((raw.sbytes > 0) & (raw.spkts == 0)).sum()),
            "destination": int(((raw.dbytes > 0) & (raw.dpkts == 0)).sum()),
        },
    }
