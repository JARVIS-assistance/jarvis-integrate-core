FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip setuptools wheel

COPY jarvis_contracts /app/jarvis_contracts
COPY jarvis_core /app/jarvis_core
COPY jarvis_controller /app/jarvis_controller
COPY jarvis_gateway /app/jarvis_gateway
COPY jarvis-ai-workbench /app/jarvis-ai-workbench

RUN ln -s /app/jarvis_contracts /app/jarvis-contracts \
    && ln -s /app/jarvis_core /app/jarvis-core \
    && ln -s /app/jarvis_controller /app/jarvis-controller \
    && ln -s /app/jarvis_gateway /app/jarvis-gateway

FROM base AS core
WORKDIR /app/jarvis_core
RUN grep -Ev '^[[:space:]]*\.\./jarvis[-_]contracts[[:space:]]*$' requirements.txt > /tmp/req.txt \
    && python -m pip install --no-build-isolation -r /tmp/req.txt
WORKDIR /app
ENV PYTHONPATH=/app:/app/jarvis_contracts:/app/jarvis_core/src
CMD ["python", "-m", "uvicorn", "app:app", "--app-dir", "/app/jarvis_core/src", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS controller
WORKDIR /app/jarvis_controller
RUN grep -Ev '^[[:space:]]*\.\./jarvis[-_]contracts[[:space:]]*$' requirements.txt > /tmp/req.txt \
    && python -m pip install --no-build-isolation -r /tmp/req.txt
WORKDIR /app
ENV PYTHONPATH=/app:/app/jarvis_contracts:/app/jarvis_controller/src
CMD ["python", "-m", "uvicorn", "app:app", "--app-dir", "/app/jarvis_controller/src", "--host", "0.0.0.0", "--port", "8001"]

FROM base AS gateway
WORKDIR /app/jarvis_gateway
RUN grep -Ev '^[[:space:]]*\.\./jarvis[-_]contracts[[:space:]]*$' requirements.txt > /tmp/req.txt \
    && python -m pip install --no-build-isolation -r /tmp/req.txt
WORKDIR /app
ENV PYTHONPATH=/app:/app/jarvis_contracts:/app/jarvis_gateway/src
CMD ["python", "-m", "uvicorn", "jarvis_gateway.app:app", "--app-dir", "/app/jarvis_gateway/src", "--host", "0.0.0.0", "--port", "8002"]

FROM base AS ai-workbench
WORKDIR /app/jarvis-ai-workbench
RUN python -m pip install --no-build-isolation -r requirements.txt
WORKDIR /app
ENV PYTHONPATH=/app/jarvis-ai-workbench/src
CMD ["python", "-m", "uvicorn", "jarvis_ai_workbench.app:app", "--app-dir", "/app/jarvis-ai-workbench/src", "--host", "0.0.0.0", "--port", "8010"]
