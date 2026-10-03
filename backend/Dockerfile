FROM python:3.13.9-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    API_HOST=0.0.0.0 \
    API_PORT=5000 \
    API_DEBUG=false \
    LOG_LEVEL=INFO

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r backend/requirements.txt

COPY backend/ backend/
COPY netguard_workflow/ netguard_workflow/
COPY models_saved/shared_pipeline.joblib models_saved/shared_pipeline.joblib
COPY models_saved/shared_pipeline.manifest.json models_saved/shared_pipeline.manifest.json
RUN mkdir -p backend/logs

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

CMD ["sh", "-c", "gunicorn backend.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind ${API_HOST}:${API_PORT} --timeout 180"]
