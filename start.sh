#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PYTHON="${ROOT_DIR}/.venv/bin/python"
if [[ -x "${DEFAULT_PYTHON}" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-${DEFAULT_PYTHON}}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3.12}"
fi

# Allow jarvis-core to import shared contracts without editable install.
export PYTHONPATH="${ROOT_DIR}/jarvis-core/src:${ROOT_DIR}/jarvis-contracts/src:${PYTHONPATH:-}"

ARGS=(
  --app-dir "${ROOT_DIR}/jarvis-core/src"
  "${APP_MODULE:-app:app}"
  --host 0.0.0.0
  --port "${PORT:-8000}"
  --env-file "${ROOT_DIR}/jarvis-core/.env"
)

if [[ "${RELOAD:-0}" == "1" ]]; then
  ARGS+=(--reload --reload-dir "${ROOT_DIR}/jarvis-core/src")
fi

exec "${PYTHON_BIN}" -m uvicorn "${ARGS[@]}"
