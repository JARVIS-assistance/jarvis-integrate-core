#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PYTHON="${ROOT_DIR}/.venv/bin/python"
if [[ -x "${DEFAULT_PYTHON}" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-${DEFAULT_PYTHON}}"
else
  PYTHON_BIN="${PYTHON_BIN:-python3.12}"
fi

export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

RELOAD_FLAG=""
if [[ "${RELOAD:-1}" == "1" ]]; then
  RELOAD_FLAG="--reload"
fi

SERVICE="${1:-all}"

require_service_source() {
  local service_dir="$1"
  local app_entry="$2"

  if [[ ! -f "${service_dir}/${app_entry}" ]]; then
    echo "ERROR: Missing service sources in ${service_dir}."
    echo "This repository expects ${service_dir} to be populated as a git submodule or checked-out service directory."
    echo "Recovery:"
    echo "  1. Use a checkout/branch that still tracks the service submodules, then run:"
    echo "     git submodule update --init --recursive"
    echo "  2. Or clone/check out the service repositories into the expected directories manually."
    exit 1
  fi
}

start_core() {
  require_service_source "${ROOT_DIR}/jarvis_core/src" "app.py"
  echo "▶ Starting jarvis-core on :${JARVIS_CORE_PORT:-8000}"
  PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/jarvis_core/src:${PYTHONPATH:-}" \
  "${PYTHON_BIN}" -m uvicorn app:app \
    --app-dir "${ROOT_DIR}/jarvis_core/src" \
    --host 0.0.0.0 \
    --port "${JARVIS_CORE_PORT:-8000}" \
    ${RELOAD_FLAG:+$RELOAD_FLAG} &
}

start_gateway() {
  require_service_source "${ROOT_DIR}/jarvis_gateway/src/jarvis_gateway" "app.py"
  echo "▶ Starting jarvis-gateway on :${JARVIS_GATEWAY_PORT:-8002}"
  PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/jarvis_gateway/src:${PYTHONPATH:-}" \
  "${PYTHON_BIN}" -m uvicorn jarvis_gateway.app:app \
    --app-dir "${ROOT_DIR}/jarvis_gateway/src" \
    --host 0.0.0.0 \
    --port "${JARVIS_GATEWAY_PORT:-8002}" \
    ${RELOAD_FLAG:+$RELOAD_FLAG} &
}

start_controller() {
  require_service_source "${ROOT_DIR}/jarvis_controller/src" "app.py"
  echo "▶ Starting jarvis-controller on :${JARVIS_CONTROLLER_PORT:-8001}"
  PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/jarvis_controller/src:${PYTHONPATH:-}" \
  JARVIS_CORE_URL="http://localhost:${JARVIS_CORE_PORT:-8000}" \
  JARVIS_GATEWAY_URL="http://localhost:${JARVIS_GATEWAY_PORT:-8002}" \
  "${PYTHON_BIN}" -m uvicorn app:app \
    --app-dir "${ROOT_DIR}/jarvis_controller/src" \
    --host 0.0.0.0 \
    --port "${JARVIS_CONTROLLER_PORT:-8001}" \
    ${RELOAD_FLAG:+$RELOAD_FLAG} &
}

start_workbench() {
  require_service_source "${ROOT_DIR}/jarvis_ai_workbench/src/jarvis_ai_workbench" "app.py"
  echo "▶ Starting jarvis-ai-workbench on :${JARVIS_WORKBENCH_PORT:-8010}"
  PYTHONPATH="${ROOT_DIR}:${ROOT_DIR}/jarvis_ai_workbench/src:${PYTHONPATH:-}" \
  "${PYTHON_BIN}" -m uvicorn jarvis_ai_workbench.app:app \
    --app-dir "${ROOT_DIR}/jarvis_ai_workbench/src" \
    --host 0.0.0.0 \
    --port "${JARVIS_WORKBENCH_PORT:-8010}" \
    ${RELOAD_FLAG:+$RELOAD_FLAG} &
}

cleanup() {
  echo ""
  echo "Stopping all services..."
  kill $(jobs -p) 2>/dev/null
  wait
}
trap cleanup EXIT INT TERM

case "${SERVICE}" in
  core)       start_core ;;
  gateway)    start_gateway ;;
  controller) start_controller ;;
  workbench)  start_workbench ;;
  all)
    start_core
    start_gateway
    sleep 1
    start_controller
    start_workbench
    ;;
  *)
    echo "Usage: $0 [core|gateway|controller|workbench|all]"
    exit 1
    ;;
esac

echo ""
echo "Services running. Press Ctrl+C to stop."
wait
