FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY jarvis-contracts /app/jarvis-contracts
COPY jarvis-core /app/jarvis-core
COPY jarvis-controller /app/jarvis-controller
COPY jarvis-gateway /app/jarvis-gateway
COPY jarvis-ai-workbench /app/jarvis-ai-workbench

FROM base AS core
RUN python -m pip install -r /app/jarvis-core/requirements.txt
WORKDIR /app
ENV PYTHONPATH=/app/jarvis-core/src:/app/jarvis-contracts/src
CMD ["python", "-m", "uvicorn", "app:app", "--app-dir", "/app/jarvis-core/src", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS controller
RUN python -m pip install -r /app/jarvis-controller/requirements.txt
WORKDIR /app
ENV PYTHONPATH=/app/jarvis-controller/src:/app/jarvis-contracts/src
CMD ["python", "-m", "uvicorn", "jarvis_controller.app:app", "--app-dir", "/app/jarvis-controller/src", "--host", "0.0.0.0", "--port", "8001"]

FROM base AS gateway
RUN python -m pip install -r /app/jarvis-gateway/requirements.txt
WORKDIR /app
ENV PYTHONPATH=/app/jarvis-gateway/src:/app/jarvis-contracts/src
CMD ["python", "-m", "uvicorn", "jarvis_gateway.app:app", "--app-dir", "/app/jarvis-gateway/src", "--host", "0.0.0.0", "--port", "8002"]

FROM base AS ai-workbench
RUN python -m pip install -r /app/jarvis-ai-workbench/requirements.txt
WORKDIR /app
ENV PYTHONPATH=/app/jarvis-ai-workbench/src
CMD ["python", "-m", "uvicorn", "jarvis_ai_workbench.app:app", "--app-dir", "/app/jarvis-ai-workbench/src", "--host", "0.0.0.0", "--port", "8010"]
