#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GITHUB_BASE="${GITHUB_BASE:-https://github.com/JARVIS-assistance}"

REPOS=(
  "jarvis-contracts"
  "jarvis-core"
  "jarvis-controller"
  "jarvis-gateway"
  "jarvis-ai-workbench"
)

log() {
  printf '[deploy] %s\n' "$1"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'required command not found: %s\n' "$1" >&2
    exit 1
  fi
}

sync_repo() {
  local name="$1"
  local repo_dir="${ROOT_DIR}/${name}"
  local repo_url="${GITHUB_BASE}/${name}.git"

  if [[ -d "${repo_dir}/.git" ]]; then
    log "updating ${name}"
    git -C "${repo_dir}" pull --ff-only
    return
  fi

  if [[ -e "${repo_dir}" ]]; then
    printf 'path exists but is not a git repo: %s\n' "${repo_dir}" >&2
    exit 1
  fi

  log "cloning ${name} from ${repo_url}"
  git clone "${repo_url}" "${repo_dir}"
}

main() {
  require_cmd git
  require_cmd docker

  for repo in "${REPOS[@]}"; do
    sync_repo "${repo}"
  done

  if [[ ! -f "${ROOT_DIR}/.env.docker" ]]; then
    if [[ -f "${ROOT_DIR}/.env.docker.example" ]]; then
      log "creating .env.docker from template"
      cp "${ROOT_DIR}/.env.docker.example" "${ROOT_DIR}/.env.docker"
    else
      printf '.env.docker and .env.docker.example are both missing\n' >&2
      exit 1
    fi
  fi

  log "starting docker services"
  docker compose -f "${ROOT_DIR}/docker-compose.yml" up -d --build

  log "done"
  docker compose -f "${ROOT_DIR}/docker-compose.yml" ps
}

main "$@"
