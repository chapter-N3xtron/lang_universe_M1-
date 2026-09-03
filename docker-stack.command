#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
COMPOSE=(docker compose --project-directory "$ROOT" -f "$ROOT/docker-compose.yml")
SIDECAR_URL="http://127.0.0.1:8000"
UI_URL="http://127.0.0.1:3002"
KOPIA_URL="http://127.0.0.1:51515"

wait_for_docker() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  open -a Docker
  for _ in $(seq 1 120); do
    if docker info >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "Docker Desktop did not become ready." >&2
  exit 1
}

ensure_sidecar_environment() {
  if [ ! -e "$ROOT/backend/.env" ]; then
    echo "Backend environment is missing at $ROOT/backend/.env" >&2
    exit 1
  fi
  if [ ! -e "$ROOT/backend/.custodian_api_token" ]; then
    echo "Custodian authentication is missing; use bttm_lock_start.command." >&2
    exit 1
  fi
}

ensure_langgraph_image() {
  if [ ! -x "$ROOT/backend/.venv/bin/langgraph" ]; then
    echo "LangGraph builder is missing at $ROOT/backend/.venv/bin/langgraph" >&2
    exit 1
  fi
  (cd "$ROOT/backend" && ./.venv/bin/langgraph build --no-pull -t jasper-langgraph:current)
}

wait_for_sidecar_endpoints() {
  for _ in $(seq 1 60); do
    if curl -fsS --connect-timeout 2 --max-time 30 "$SIDECAR_URL/api/models" \
      | python3 -c 'import json,sys; raise SystemExit(0 if json.load(sys.stdin).get("models") else 1)' \
      && curl -fsS --connect-timeout 2 --max-time 60 "$SIDECAR_URL/api/tts/voices" \
      | python3 -c 'import json,sys; raise SystemExit(0 if json.load(sys.stdin).get("voices") else 1)'; then
      return 0
    fi
    sleep 1
  done
  echo "Sidecar model or voice endpoint failed readiness checks." >&2
  exit 1
}

case "${1:-start}" in
  start)
    wait_for_docker
    ensure_sidecar_environment
    ensure_langgraph_image
    "${COMPOSE[@]}" up -d --build
    wait_for_sidecar_endpoints
    open -a "Brave Browser" "$UI_URL"
    ;;
  stop)
    wait_for_docker
    "${COMPOSE[@]}" down
    ;;
  restart-frontend)
    wait_for_docker
    "${COMPOSE[@]}" up -d --build frontend
    ;;
  status)
    "${COMPOSE[@]}" ps
    if curl -fsS --connect-timeout 2 "$SIDECAR_URL/health" >/dev/null 2>&1; then
      echo "sidecar :8000 healthy"
    else
      echo "sidecar :8000 unavailable"
    fi
    ;;
  logs)
    wait_for_docker
    "${COMPOSE[@]}" logs -f "${2:-sidecar}"
    ;;
  *)
    echo "Usage: $0 [start|stop|restart-frontend|status|logs [service]]"
    exit 1
    ;;
esac
