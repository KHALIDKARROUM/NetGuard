"""Load the shared saved artifact once per API worker; never fit during serving."""
from pathlib import Path

from netguard_workflow import PredictionService
from backend.config import settings


def get_prediction_service(app):
    if not hasattr(app.state, "cache"):
        app.state.cache = {}
    if "shared_prediction_service" not in app.state.cache:
        path = getattr(app.state, "prediction_artifact_path", settings.prediction_artifact)
        app.state.cache["shared_prediction_service"] = PredictionService(Path(path))
    return app.state.cache["shared_prediction_service"]
