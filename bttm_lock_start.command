#!/bin/zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

CUSTODIAN_WORKER_PID="$ROOT/backend/.custodian_worker.pid"
CUSTODIAN_ORCHESTRATOR_PID="$ROOT/backend/.custodian_orchestrator.pid"
CUSTODIAN_WORKER_LOG="$ROOT/backend/logs/custodian_worker.log"
CUSTODIAN_ORCHESTRATOR_LOG="$ROOT/backend/logs/custodian_orchestrator.log"

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

case "${1:-start}" in
  start)
    start_host_custodian
    exec "$ROOT/docker-stack.command" "$@"
    ;;
  stop)
    stop_host_custodian
    exec "$ROOT/docker-stack.command" "$@"
    ;;
  restart)
    stop_host_custodian
    start_host_custodian
    exec "$ROOT/docker-stack.command" start
    ;;
  *)
    exec "$ROOT/docker-stack.command" "$@"
    ;;
esac
