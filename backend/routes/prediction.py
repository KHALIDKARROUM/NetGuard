"""Raw single/batch HTTP adapters for the notebook's shared saved pipeline."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from netguard_workflow import ArtifactError
from netguard_workflow.features import MAX_EXACT_COUNT
from backend.utils.prediction_pipeline import get_prediction_service

router = APIRouter(prefix="/api/predict", tags=["Prediction"])


class ConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    sbytes: int = Field(ge=0, le=MAX_EXACT_COUNT, description="Measured source bytes")
    dbytes: int = Field(ge=0, le=MAX_EXACT_COUNT, description="Measured destination bytes")
    spkts: int = Field(ge=0, le=MAX_EXACT_COUNT, description="Measured source packets")
    dpkts: int = Field(ge=0, le=MAX_EXACT_COUNT, description="Measured destination packets")
    dur: float = Field(ge=0, description="Recorded duration in seconds")
    rate: float = Field(ge=0, description="Recorded connection rate")
    sload: float = Field(ge=0, description="Recorded source load")
    dload: float = Field(ge=0, description="Recorded destination load")
    sttl: int = Field(ge=0, le=255, description="Measured source TTL")
    dttl: int = Field(ge=0, le=255, description="Measured destination TTL")


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connections: list[ConnectionRequest] = Field(min_length=1, max_length=1000)


EDITABLE_INPUTS = [
    {"name": name, "label": label, "type": kind}
    for name, label, kind in (
        ("sbytes", "Bytes sent", "int"), ("dbytes", "Bytes received", "int"),
        ("spkts", "Packets sent", "int"), ("dpkts", "Packets received", "int"),
        ("dur", "Duration", "float"), ("rate", "Rate", "float"),
        ("sload", "Source load", "float"), ("dload", "Destination load", "float"),
        ("sttl", "Source TTL", "int"), ("dttl", "Destination TTL", "int"),
    )
]
DEFAULT_INPUT = {"sbytes": 1500, "dbytes": 5000, "spkts": 10, "dpkts": 15,
                 "dur": 0.5, "rate": 20.0, "sload": 0.0, "dload": 0.0, "sttl": 64, "dttl": 64}


def _service(request, model=None):
    try:
        return get_prediction_service(request.app, model)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail="Select an available deployed model.") from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/best_model", summary="Information about the validation-selected shared model")
def get_best_model(request: Request):
    service = _service(request)
    registry = request.app.state.cache.get("prediction_registry")
    return {"status": 200, "best_model": {**service.metadata, "threshold_value": service.bundle["threshold"]},
            "available_models": registry.metadata if registry else [{"id": service.bundle["model_name"], "default": True, **service.metadata}],
            "editable_inputs": EDITABLE_INPUTS, "defaults": DEFAULT_INPUT}


@router.get("/info", summary="Compatibility alias for shared-model metadata")
def get_model_info(request: Request):
    return get_best_model(request)


def _predict(connections, service):
    frame = pd.DataFrame([connection.model_dump() for connection in connections])
    try:
        predictions = service.predict(frame)
    except ArtifactError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    results = []
    for i, row in enumerate(predictions.itertuples(index=False)):
        label = int(row.predicted_label)
        score = float(row.attack_score)
        results.append({"status": 200, "model": service.bundle["model_name"],
            "prediction": {"label": label, "class_name": "Anomaly" if label else "Normal"},
            "score": score, "threshold": float(service.bundle["threshold"]),
            "components": {"model_score": score}, "input": connections[i].model_dump(),
            "artifact_sha256": service.artifact_sha256, "precision": "float64"})
    return results


@router.post("/single", summary="Predict one measured raw connection")
def predict_single(payload: ConnectionRequest, request: Request,
                   model: str | None = Query(default=None, max_length=64)):
    return _predict([payload], _service(request, model))[0]


@router.post("/batch", summary="Predict up to 1,000 raw connections using the same fixed threshold")
def predict_batch(payload: BatchRequest, request: Request,
                  model: str | None = Query(default=None, max_length=64)):
    service = _service(request, model)
    results = _predict(payload.connections, service)
    return {"status": 200, "n": len(results), "predictions": results,
            "model": service.bundle["model_name"], "threshold": float(service.bundle["threshold"]),
            "artifact_sha256": service.artifact_sha256}
