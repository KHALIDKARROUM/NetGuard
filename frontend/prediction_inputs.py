"""Input definitions and CSV validation for the existing raw prediction contract."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
import pandas as pd

MAX_EXACT_COUNT = 2**53 - 1
DEFAULTS = dict(sbytes=1800, dbytes=6200, spkts=12, dpkts=18, dur=.5, rate=24., sload=0., dload=0., sttl=64, dttl=64)
INTEGER_FIELDS = {"sbytes", "dbytes", "spkts", "dpkts", "sttl", "dttl"}
PRESETS = {
    "Web traffic example": DEFAULTS,
    "Scan-like example": {**DEFAULTS, "dur":.001, "rate":1200., "sbytes":60, "dbytes":0, "spkts":1, "dpkts":0, "sload":14000., "sttl":255, "dttl":0},
    "Burst traffic example": {**DEFAULTS, "dur":4.2, "rate":10000., "sbytes":500000, "dbytes":0, "spkts":6000, "dpkts":0, "sload":4000000., "sttl":255, "dttl":0},
}

def validate_connections(frame: pd.DataFrame) -> list[dict]:
    """Preserve exact integer counts and report the first offending CSV row/field."""
    if not 1 <= len(frame) <= 1000:
        raise ValueError("Provide between 1 and 1,000 connections per batch.")
    if frame.columns.duplicated().any():
        raise ValueError("CSV headers must be unique.")
    missing = [name for name in DEFAULTS if name not in frame]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    connections = []
    for index, record in enumerate(frame[list(DEFAULTS)].to_dict("records"), start=1):
        connection = {}
        for field, value in record.items():
            try:
                number = Decimal(str(value))
            except (InvalidOperation, ValueError):
                raise ValueError(f"Row {index} · {field}: enter a numeric measurement.") from None
            if not number.is_finite() or number < 0:
                raise ValueError(f"Row {index} · {field}: measurement must be finite and nonnegative.")
            if field in INTEGER_FIELDS:
                maximum = 255 if field in {"sttl", "dttl"} else MAX_EXACT_COUNT
                if number != number.to_integral_value() or number > maximum:
                    raise ValueError(f"Row {index} · {field}: enter a whole number from 0 to {maximum:,}.")
                connection[field] = int(number)
            else:
                converted = float(number)
                if converted == float("inf"):
                    raise ValueError(f"Row {index} · {field}: measurement is too large.")
                connection[field] = converted
        if connection["sbytes"] + connection["dbytes"] > MAX_EXACT_COUNT or connection["spkts"] + connection["dpkts"] > MAX_EXACT_COUNT:
            raise ValueError(f"Row {index}: combined byte and packet totals must each be at most {MAX_EXACT_COUNT:,}.")
        connections.append(connection)
    return connections
