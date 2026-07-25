#!/bin/zsh
# dev.sh — start / stop / status / restart the backend and frontend dev servers.
#
# Usage:
#   ./dev.sh start      Start both servers
#   ./dev.sh stop       Stop both servers
#   ./dev.sh status     Show whether each server is running
#   ./dev.sh restart    Stop then start

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend"
BACKEND_PID="$BACKEND_DIR/backend.pid"
FRONTEND_PID="$FRONTEND_DIR/frontend.pid"
BACKEND_LOG="$BACKEND_DIR/logs/backend.log"
FRONTEND_LOG="$FRONTEND_DIR/logs/frontend.log"
BACKEND_PORT=8000
FRONTEND_PORT=3000

# ── helpers ──────────────────────────────────────────────────────────

_ensure_dirs() {
  mkdir -p "$BACKEND_DIR/logs" "$FRONTEND_DIR/logs"
}

_pid_alive() {
  [ -n "$1" ] && kill -0 "$1" 2>/dev/null
}

_port_listening() {
  lsof -ti:"$1" >/dev/null 2>&1
}

_wait_for_port() {
  local port="$1" max="${2:-30}"
  for _ in $(seq 1 "$max"); do
    if _port_listening "$port"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

# ── start ─────────────────────────────────────────────────────────────

start_backend() {
  if _port_listening "$BACKEND_PORT"; then
    echo "  Backend already running on :$BACKEND_PORT"
    return 0
  fi

  _ensure_dirs
  echo "  Starting backend..."
  cd "$BACKEND_DIR"
  source ./venv/bin/activate
  nohup python -m src.web_server >> "$BACKEND_LOG" 2>&1 &
  echo $! > "$BACKEND_PID"
  disown

  if _wait_for_port "$BACKEND_PORT" 15; then
    echo "  Backend ready on http://127.0.0.1:$BACKEND_PORT"
  else
    echo "  Backend failed to start — check $BACKEND_LOG"
    return 1
  fi
}

start_frontend() {
  if _port_listening "$FRONTEND_PORT"; then
    echo "  Frontend already running on :$FRONTEND_PORT"
    return 0
  fi

  _ensure_dirs
  echo "  Starting frontend..."
  cd "$FRONTEND_DIR"
  nohup npm run dev >> "$FRONTEND_LOG" 2>&1 &
  echo $! > "$FRONTEND_PID"
  disown

  if _wait_for_port "$FRONTEND_PORT" 20; then
    echo "  Frontend ready on http://localhost:$FRONTEND_PORT"
  else
    echo "  Frontend failed to start — check $FRONTEND_LOG"
    return 1
  fi
}

# ── stop ──────────────────────────────────────────────────────────────

stop_backend() {
  if [ -f "$BACKEND_PID" ]; then
    local pid
    pid=$(cat "$BACKEND_PID")
    if _pid_alive "$pid"; then
      kill "$pid" 2>/dev/null
      echo "  Backend (pid $pid) stopped"
    fi
    rm -f "$BACKEND_PID"
  fi
  # Also kill anything still on the port
  lsof -ti:"$BACKEND_PORT" 2>/dev/null | xargs kill 2>/dev/null || true
}

stop_frontend() {
  if [ -f "$FRONTEND_PID" ]; then
    local pid
    pid=$(cat "$FRONTEND_PID")
    if _pid_alive "$pid"; then
      kill "$pid" 2>/dev/null
      echo "  Frontend (pid $pid) stopped"
    fi
    rm -f "$FRONTEND_PID"
  fi
  lsof -ti:"$FRONTEND_PORT" 2>/dev/null | xargs kill 2>/dev/null || true
}

# ── status ────────────────────────────────────────────────────────────

status_backend() {
  if _port_listening "$BACKEND_PORT"; then
    local pid
    pid=$(cat "$BACKEND_PID" 2>/dev/null || echo "?")
    echo "  Backend  :$BACKEND_PORT  ✓  (pid $pid)"
  else
    echo "  Backend  :$BACKEND_PORT  ✗  not running"
  fi
}

status_frontend() {
  if _port_listening "$FRONTEND_PORT"; then
    local pid
    pid=$(cat "$FRONTEND_PID" 2>/dev/null || echo "?")
    echo "  Frontend :$FRONTEND_PORT  ✓  (pid $pid)"
  else
    echo "  Frontend :$FRONTEND_PORT  ✗  not running"
  fi
}

# ── main ──────────────────────────────────────────────────────────────

case "${1:-}" in
  start)
    echo "Starting dev servers..."
    start_backend
    start_frontend
    echo "Done."
    ;;
  stop)
    echo "Stopping dev servers..."
    stop_backend
    stop_frontend
    echo "Done."
    ;;
  status)
    echo "Dev server status:"
    status_backend
    status_frontend
    ;;
  restart)
    echo "Restarting dev servers..."
    stop_backend
    stop_frontend
    sleep 1
    start_backend
    start_frontend
    echo "Done."
    ;;
  *)
    echo "Usage: $0 {start|stop|status|restart}"
    exit 1
    ;;
esac
