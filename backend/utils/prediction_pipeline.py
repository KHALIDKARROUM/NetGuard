"""Load the shared saved artifact once per API worker; never fit during serving."""
from pathlib import Path

from netguard_workflow import ArtifactError, PredictionService
from netguard_workflow.deployment import NotebookPredictionService, PredictionRegistry
from backend.config import settings


def get_prediction_service(app, model=None):
    if not hasattr(app.state, "cache"):
        app.state.cache = {}
    if "shared_prediction_service" not in app.state.cache:
        path = getattr(app.state, "prediction_artifact_path", settings.prediction_artifact)
        registry_path = getattr(app.state, "prediction_registry_path", None)
        if registry_path:
            registry = PredictionRegistry(registry_path)
            configured_name = Path(path).stem
            if configured_name not in registry.services:
                raise ArtifactError("The configured default artifact is not in the deployed registry.")
            registry.default = configured_name
            app.state.cache["prediction_registry"] = registry
            app.state.cache["shared_prediction_service"] = registry.get()
        else:
            loader = NotebookPredictionService if Path(path).suffix == ".pkl" else PredictionService
            app.state.cache["shared_prediction_service"] = loader(Path(path))
    if model:
        registry = app.state.cache.get("prediction_registry")
        if registry:
            return registry.get(model)
        service = app.state.cache["shared_prediction_service"]
        if model != service.bundle["model_name"]:
            raise KeyError(model)
    return app.state.cache["shared_prediction_service"]
