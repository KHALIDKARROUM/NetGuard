"""Small smoke test for the NetGuard FastAPI backend.

Run this while the backend is up:

    python test_api.py --host http://localhost:5000
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import requests


DEFAULT_HOST = "http://localhost:5000"


def check(name: str, response: requests.Response, expected: int = 200) -> dict[str, Any]:
    try:
        payload = response.json()
    except Exception:
        payload = {"raw": response.text[:300]}

    if response.status_code != expected:
        print(f"[FAIL] {name}: expected {expected}, got {response.status_code}")
        print(payload)
        raise SystemExit(1)

    print(f"[ OK ] {name}: {response.status_code}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    args = parser.parse_args()
    host = args.host.rstrip("/")

    check("health", requests.get(f"{host}/health", timeout=10))
    check("dataset", requests.get(f"{host}/api/dataset/info", timeout=20))
    check("compare", requests.get(f"{host}/api/models/compare", timeout=30))
    check("best model", requests.get(f"{host}/api/predict/best_model", timeout=30))

    sample = {
        "sbytes": 1500,
        "dbytes": 5000,
        "spkts": 10,
        "dpkts": 15,
        "dur": 0.5,
        "rate": 20.0,
        "sload": 0.0,
        "dload": 0.0,
        "sttl": 64,
        "dttl": 64,
    }
    prediction = check(
        "single prediction",
        requests.post(f"{host}/api/predict/single", json=sample, timeout=120),
    )
    print("Prediction:", prediction.get("prediction"), "score=", prediction.get("score"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
