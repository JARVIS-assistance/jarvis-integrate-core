#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REMOTE="${1:-${REMOTE_HOST:-}}"
REMOTE_DIR="${2:-${REMOTE_DIR:-jarvis-core}}"
ARCHIVE_NAME="jarvis-core-deploy.tgz"

log() {
  printf '[deploy-current] %s\n' "$1"
}

usage() {
  cat <<'USAGE'
Usage:
  ./deploy_current_remote.sh user@host [remote_dir]

Environment alternatives:
  REMOTE_HOST=user@host REMOTE_DIR=/opt/jarvis ./deploy_current_remote.sh

This sends the current local core/ workspace to the remote host, then runs:
  docker compose up -d --build
USAGE
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'required command not found: %s\n' "$1" >&2
    exit 1
  fi
}

shell_quote() {
  printf "%q" "$1"
}

if [[ -z "${REMOTE}" ]]; then
  usage >&2
  exit 2
fi

require_cmd tar
require_cmd ssh
require_cmd scp

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT
REMOTE_DIR_Q="$(shell_quote "${REMOTE_DIR}")"
ARCHIVE_NAME_Q="$(shell_quote "${ARCHIVE_NAME}")"

log "packing current workspace"
tar -C "${ROOT_DIR}" \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='.pytest_cache' \
  --exclude='.ruff_cache' \
  --exclude='data' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  -czf "${TMP_DIR}/${ARCHIVE_NAME}" .

log "preparing remote directory ${REMOTE_DIR}"
ssh "${REMOTE}" "mkdir -p ${REMOTE_DIR_Q}"

log "uploading archive to ${REMOTE}"
scp "${TMP_DIR}/${ARCHIVE_NAME}" "${REMOTE}:${ARCHIVE_NAME}"

log "extracting and starting services"
ssh "${REMOTE}" "set -eu
  log() { printf '[remote-deploy] %s\n' \"\$1\"; }
  export PATH=\"/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:\$PATH\"
  export DOCKER_CONFIG=\"${REMOTE_DIR_Q}/.docker-deploy-config\"
  mkdir -p \"\$DOCKER_CONFIG\"
  printf '{}\n' > \"\$DOCKER_CONFIG/config.json\"
  log 'checking docker'
  if ! command -v docker >/dev/null 2>&1; then
    log 'docker command not found in non-interactive SSH PATH'
    printf 'PATH=%s\n' \"\$PATH\" >&2
    exit 127
  fi
  if ! docker info >/dev/null 2>&1; then
    log 'docker daemon is not reachable; start Docker Desktop or the Docker service on the remote host'
    docker info >&2 || true
    exit 1
  fi
  docker compose version
  log 'extracting archive'
  rm -rf ${REMOTE_DIR_Q}/.deploy-new
  mkdir -p ${REMOTE_DIR_Q}/.deploy-new
  tar -xzf ${ARCHIVE_NAME_Q} -C ${REMOTE_DIR_Q}/.deploy-new
  log 'preserving existing .env.docker when present'
  if [ -f ${REMOTE_DIR_Q}/.env.docker ]; then
    cp ${REMOTE_DIR_Q}/.env.docker ${REMOTE_DIR_Q}/.deploy-new/.env.docker
  fi
  if [ -f ${REMOTE_DIR_Q}/current/.env.docker ] && [ ! -f ${REMOTE_DIR_Q}/.deploy-new/.env.docker ]; then
    cp ${REMOTE_DIR_Q}/current/.env.docker ${REMOTE_DIR_Q}/.deploy-new/.env.docker
  fi
  log 'rotating release directory'
  rm -rf ${REMOTE_DIR_Q}/.deploy-prev
  if [ -d ${REMOTE_DIR_Q}/current ]; then
    mv ${REMOTE_DIR_Q}/current ${REMOTE_DIR_Q}/.deploy-prev
  fi
  mv ${REMOTE_DIR_Q}/.deploy-new ${REMOTE_DIR_Q}/current
  cd ${REMOTE_DIR_Q}/current
  if [ ! -f .env.docker ]; then
    cp .env.docker.example .env.docker
  fi
  log 'validating compose file'
  docker compose config --quiet
  log 'building and starting containers'
  if ! docker compose up -d --build; then
    log 'compose failed; rolling back release directory'
    cd ${REMOTE_DIR_Q}
    rm -rf current
    if [ -d .deploy-prev ]; then
      mv .deploy-prev current
    fi
    exit 1
  fi
  log 'container status'
  docker compose ps
  rm -f ~/${ARCHIVE_NAME_Q}
"

log "done"
