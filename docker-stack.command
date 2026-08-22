#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
COMPOSE=(docker compose --project-directory "$ROOT" -f "$ROOT/docker-compose.yml")
SIDECAR_PID="$ROOT/backend/.sidecar.pid"
SIDECAR_LOG="$ROOT/backend/logs/sidecar.log"
SIDECAR_URL="http://127.0.0.1:8000"
UI_URL="http://127.0.0.1:3002"

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

ensure_image() {
  local image="$1"
  local archive="$2"
  if docker image inspect "$image" >/dev/null 2>&1; then
    return 0
  fi
  if [ ! -f "$ROOT/$archive" ]; then
    echo "Required image archive is missing: $ROOT/$archive" >&2
    exit 1
  fi
  docker load --input "$ROOT/$archive" >/dev/null
}

ensure_sidecar_environment() {
  if [ ! -e "$ROOT/backend/.env" ]; then
    echo "Backend credentials are missing at $ROOT/backend/.env" >&2
    exit 1
  fi
  if [ ! -x "$ROOT/backend/.venv/bin/python" ]; then
    if ! command -v uv >/dev/null 2>&1; then
      echo "uv is required to install the sidecar environment." >&2
      exit 1
    fi
    uv sync --frozen --extra sidecar --project "$ROOT/backend"
  fi
}

start_sidecar() {
  if curl -fsS --connect-timeout 2 "$SIDECAR_URL/health" >/dev/null 2>&1; then
    return 0
  fi
  mkdir -p "$(dirname "$SIDECAR_LOG")"
  (
    cd "$ROOT/backend"
    SIDECAR_ALLOWED_ORIGINS="http://localhost:3002,http://127.0.0.1:3002" \
      TODOS_FILE="$ROOT/todos.json" \
      OCR_UPLOAD_DIR="$ROOT/data/ocr/uploads" \
      nohup ./.venv/bin/python -m src.web_server >> "$SIDECAR_LOG" 2>&1 &
    echo $! > "$SIDECAR_PID"
  )
  for _ in $(seq 1 60); do
    if curl -fsS --connect-timeout 2 "$SIDECAR_URL/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "Sidecar failed to start; check $SIDECAR_LOG" >&2
  exit 1
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
  echo "Sidecar model or voice endpoint failed readiness checks; check $SIDECAR_LOG" >&2
  exit 1
}

stop_sidecar() {
  if [ -f "$SIDECAR_PID" ]; then
    kill "$(cat "$SIDECAR_PID")" 2>/dev/null || true
    rm -f "$SIDECAR_PID"
  fi
  lsof -nP -tiTCP:8000 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
}

case "${1:-start}" in
  start)
    wait_for_docker
    ensure_sidecar_environment
    ensure_image "jasper-langgraph:current" "jasper-langgraph-current.tar"
    ensure_image "jasper-runtime-frontend:latest" "jasper-runtime-frontend-latest.tar"
    ensure_image "pgvector/pgvector:pg16" "pgvector-pg16.tar"
    ensure_image "redis:6" "redis-6.tar"
    "${COMPOSE[@]}" up -d --no-build
    start_sidecar
    wait_for_sidecar_endpoints
    open -a "Brave Browser" "$UI_URL"
    ;;
  stop)
    stop_sidecar
    "${COMPOSE[@]}" down
    ;;
  restart-frontend)
    "${COMPOSE[@]}" restart frontend
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
    if [ "${2:-frontend}" = "sidecar" ]; then
      tail -f "$SIDECAR_LOG"
    else
      "${COMPOSE[@]}" logs -f "${2:-frontend}"
    fi
    ;;
  *)
    echo "Usage: $0 [start|stop|restart-frontend|status|logs [service]]"
    exit 1
    ;;
esac
