"""Bounded CSV parsing and spreadsheet-safe exports."""
from __future__ import annotations
import csv
import io
import pandas as pd

MAX_UPLOAD_BYTES = 2 * 1024 * 1024

def read_connection_csv(raw: bytes) -> pd.DataFrame:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("The CSV is too large. Keep uploads below 2 MB.")
    if not raw or b"\x00" in raw:
        raise ValueError("Upload a nonempty UTF-8 CSV without binary data.")
    # Measurement headers do not need embedded newlines or enormous column lists.
    newline = raw.find(b"\n", 0, 4097)
    if newline < 0 and len(raw) > 4096:
        raise ValueError("The CSV header is too large. Use the template's measurement columns.")
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text), strict=True)
        header = next(reader, [])
        if len(header) > 64 or any(len(name) > 128 for name in header):
            raise ValueError("The CSV header is too large. Keep at most 64 short column names.")
        if len(header) != len(set(header)):
            raise ValueError("CSV headers must be unique.")
        rows = []
        for row in reader:
            if not row:
                continue
            if len(row) != len(header):
                raise ValueError(f"CSV row {len(rows) + 1} must have the same number of fields as the header.")
            rows.append(row)
            if len(rows) == 1001:
                break
        return pd.DataFrame(rows, columns=header, dtype=str)
    except (UnicodeDecodeError, csv.Error):
        raise ValueError("The file is not a valid UTF-8 CSV. Check its format against the template.") from None

def safe_csv(frame: pd.DataFrame) -> bytes:
    """Quote fields and neutralize formula-like text without altering numeric values."""
    def protect(value):
        if isinstance(value, str) and (value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@", "＝", "＋", "－", "＠"))):
            return "'" + value
        return value
    output = frame.copy()
    for name in output:
        output[name] = output[name].map(protect)
    output.columns = [protect(str(name)) for name in output.columns]
    return output.to_csv(index=False, quoting=csv.QUOTE_ALL).encode("utf-8")
