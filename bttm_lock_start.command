#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOCAL_COMPOSE=(docker compose --project-directory "$ROOT/local-deployment-sandbox" -f "$ROOT/local-deployment-sandbox/compose.yaml")
KOPIA_URL="http://127.0.0.1:51515"

CUSTODIAN_WORKER_PID="$ROOT/backend/.custodian_worker.pid"
CUSTODIAN_ORCHESTRATOR_PID="$ROOT/backend/.custodian_orchestrator.pid"
CUSTODIAN_WORKER_LOG="$ROOT/backend/logs/custodian_worker.log"
CUSTODIAN_ORCHESTRATOR_LOG="$ROOT/backend/logs/custodian_orchestrator.log"
CUSTODIAN_API_TOKEN_FILE="$ROOT/backend/.custodian_api_token"

ensure_custodian_token() {
  if [ ! -e "$CUSTODIAN_API_TOKEN_FILE" ]; then
    umask 077
    /usr/bin/openssl rand -hex 32 > "$CUSTODIAN_API_TOKEN_FILE"
  fi
  chmod 600 "$CUSTODIAN_API_TOKEN_FILE"
  if [ "$(wc -c < "$CUSTODIAN_API_TOKEN_FILE" | tr -d ' ')" -lt 32 ]; then
    echo "Custodian authentication token is invalid." >&2
    exit 1
  fi
  export CUSTODIAN_API_TOKEN_FILE
}

wait_for_host_service() {
  local port="$1"
  local label="$2"
  for _ in $(seq 1 15); do
    if curl -fsS --connect-timeout 2 --max-time 3 "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "${label} failed health check on :${port}." >&2
  return 1
}

start_host_custodian() {
  if curl -fsS --connect-timeout 2 "http://127.0.0.1:8765/health" >/dev/null 2>&1; then
    echo "Custodian worker already running at :8765"
  else
    mkdir -p "$(dirname "$CUSTODIAN_WORKER_LOG")"
    if [ -x "$ROOT/backend/.venv/bin/python" ]; then
      (
        cd "$ROOT/backend"
        nohup ./.venv/bin/python custodian_worker.py >> "$CUSTODIAN_WORKER_LOG" 2>&1 &
        echo $! > "$CUSTODIAN_WORKER_PID"
      )
      echo "Started custodian worker (pid $(cat "$CUSTODIAN_WORKER_PID"))"
    else
      echo "Warning: virtualenv python not found at backend/.venv/bin/python; attempting system python"
      (
        cd "$ROOT/backend"
        nohup python3 custodian_worker.py >> "$CUSTODIAN_WORKER_LOG" 2>&1 &
        echo $! > "$CUSTODIAN_WORKER_PID"
      )
      echo "Started custodian worker with system python (pid $(cat "$CUSTODIAN_WORKER_PID"))"
    fi
  fi

  if curl -fsS --connect-timeout 2 "http://127.0.0.1:8767/health" >/dev/null 2>&1; then
    echo "Custodian orchestrator already running at :8767"
  else
    mkdir -p "$(dirname "$CUSTODIAN_ORCHESTRATOR_LOG")"
    if [ -x "$ROOT/backend/.venv/bin/python" ]; then
      (
        cd "$ROOT/backend"
        nohup ./.venv/bin/python custodian_orchestrator.py >> "$CUSTODIAN_ORCHESTRATOR_LOG" 2>&1 &
        echo $! > "$CUSTODIAN_ORCHESTRATOR_PID"
      )
      echo "Started custodian orchestrator (pid $(cat "$CUSTODIAN_ORCHESTRATOR_PID"))"
    else
      (
        cd "$ROOT/backend"
        nohup python3 custodian_orchestrator.py >> "$CUSTODIAN_ORCHESTRATOR_LOG" 2>&1 &
        echo $! > "$CUSTODIAN_ORCHESTRATOR_PID"
      )
      echo "Started custodian orchestrator with system python (pid $(cat "$CUSTODIAN_ORCHESTRATOR_PID"))"
    fi
  fi
  wait_for_host_service 8765 "Custodian worker"
  wait_for_host_service 8767 "Custodian orchestrator"
}

stop_host_custodian() {
  if [ -f "$CUSTODIAN_WORKER_PID" ]; then
    kill "$(cat "$CUSTODIAN_WORKER_PID")" 2>/dev/null || true
    rm -f "$CUSTODIAN_WORKER_PID"
  fi
  if [ -f "$CUSTODIAN_ORCHESTRATOR_PID" ]; then
    kill "$(cat "$CUSTODIAN_ORCHESTRATOR_PID")" 2>/dev/null || true
    rm -f "$CUSTODIAN_ORCHESTRATOR_PID"
  fi
  lsof -nP -tiTCP:8765 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
  lsof -nP -tiTCP:8767 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true
}

start_local_topology() {
  "${LOCAL_COMPOSE[@]}" up -d
}

stop_local_topology() {
  "${LOCAL_COMPOSE[@]}" down
}

open_kopia() {
  open -a KopiaUI
  open -a "Brave Browser" "$KOPIA_URL"
}

case "${1:-start}" in
  start)
    ensure_custodian_token
    start_host_custodian
    "$ROOT/docker-stack.command" start
    start_local_topology
    open_kopia
    ;;
  stop)
    stop_local_topology
    stop_host_custodian
    exec "$ROOT/docker-stack.command" "$@"
    ;;
  restart)
    stop_local_topology
    stop_host_custodian
    ensure_custodian_token
    start_host_custodian
    "$ROOT/docker-stack.command" start
    start_local_topology
    open_kopia
    ;;
  *)
    exec "$ROOT/docker-stack.command" "$@"
    ;;
esac
