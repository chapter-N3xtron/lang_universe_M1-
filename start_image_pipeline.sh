#!/bin/zsh
# start_image_pipeline.sh — launch / stop / status / restart the full multi-agent stack.
#
# Services:
#   Ollama     :11434   local LLM host (required for Magic Coder)
#   ComfyUI    :8188    image renderer (optional)
#   Element    GUI      VST/AU plugin host (Rare → LALA → reverb/delay)
#   Backend    :8000    FastAPI LangGraph agent server
#   Frontend   :3000    Next.js chat UI
#
# Audio chain (macOS only):
#   System output → BlackHole 2ch → Element → Built-in speakers
#   TTS audio from the browser flows through the VST effects chain automatically.
#
# Usage:
#   ./start_image_pipeline.sh start      Launch everything
#   ./start_image_pipeline.sh stop       Shut everything down
#   ./start_image_pipeline.sh status     Show what's running
#   ./start_image_pipeline.sh restart    Stop then start

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOGDIR="$ROOT/logs"
PIDDIR="$ROOT/.pids"

# ── config ────────────────────────────────────────────────────────────

OLLAMA_PORT=11434
COMFYUI_PORT=8188
BACKEND_PORT=8000
FRONTEND_PORT=3000

COMFYUI_DIR="$HOME/fun-multi-character-chats/ComfyUI"
COMFYUI_PYTHON="$HOME/fun-multi-character-chats/.venv/bin/python"

ELEMENT_ELS="$HOME/Documents/EQ_COMP_VERB_RACK.els"

AUDIO_OUTPUT_DEVICE="BlackHole 2ch"
AUDIO_RESTORE_DEVICE="MacBook Pro Speakers"

# ── helpers ────────────────────────────────────────────────────────────

_ensure_dirs() {
  mkdir -p "$LOGDIR" "$PIDDIR"
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

_ensure_switchaudio() {
  if ! command -v SwitchAudioSource >/dev/null 2>&1; then
    echo "  Installing SwitchAudioSource..."
    brew install switchaudio-osx >/dev/null 2>&1
  fi
}

# ── audio chain ────────────────────────────────────────────────────────

_set_audio_output() {
  local device="$1"
  _ensure_switchaudio
  local current
  current=$(SwitchAudioSource -t output -c 2>/dev/null || echo "unknown")
  if [ "$current" != "$device" ]; then
    echo "  Audio output: $current → $device"
    SwitchAudioSource -t output -s "$device" >/dev/null 2>&1
  else
    echo "  Audio output already set to $device"
  fi
}

# ── ollama ─────────────────────────────────────────────────────────────

start_ollama() {
  if _port_listening "$OLLAMA_PORT"; then
    echo "  Ollama already running on :$OLLAMA_PORT"
    return 0
  fi

  _ensure_dirs
  echo "  Starting Ollama..."
  ollama serve >> "$LOGDIR/ollama.log" 2>&1 &
  echo $! > "$PIDDIR/ollama.pid"
  disown

  if _wait_for_port "$OLLAMA_PORT" 15; then
    echo "  Ollama ready on http://127.0.0.1:$OLLAMA_PORT"
  else
    echo "  Ollama failed to start — check $LOGDIR/ollama.log"
    return 1
  fi
}

stop_ollama() {
  if [ -f "$PIDDIR/ollama.pid" ]; then
    local pid
    pid=$(cat "$PIDDIR/ollama.pid")
    if _pid_alive "$pid"; then
      kill "$pid" 2>/dev/null
      echo "  Ollama (pid $pid) stopped"
    fi
    rm -f "$PIDDIR/ollama.pid"
  fi
  lsof -ti:"$OLLAMA_PORT" 2>/dev/null | xargs kill 2>/dev/null || true
}

status_ollama() {
  if _port_listening "$OLLAMA_PORT"; then
    local pid
    pid=$(cat "$PIDDIR/ollama.pid" 2>/dev/null || echo "?")
    echo "  Ollama    :$OLLAMA_PORT  ✓  (pid $pid)"
  else
    echo "  Ollama    :$OLLAMA_PORT  ✗  not running"
  fi
}

# ── comfyui ────────────────────────────────────────────────────────────

start_comfyui() {
  if _port_listening "$COMFYUI_PORT"; then
    echo "  ComfyUI already running on :$COMFYUI_PORT"
    return 0
  fi

  if [ ! -d "$COMFYUI_DIR" ]; then
    echo "  ComfyUI not found at $COMFYUI_DIR — skipping (optional)"
    return 0
  fi

  _ensure_dirs
  echo "  Starting ComfyUI..."
  cd "$COMFYUI_DIR"
  if [ -f "$COMFYUI_PYTHON" ]; then
    nohup "$COMFYUI_PYTHON" main.py --listen 127.0.0.1 --port "$COMFYUI_PORT" --disable-xformers >> "$LOGDIR/comfyui.log" 2>&1 &
  else
    nohup python3 main.py --listen 127.0.0.1 --port "$COMFYUI_PORT" --disable-xformers >> "$LOGDIR/comfyui.log" 2>&1 &
  fi
  echo $! > "$PIDDIR/comfyui.pid"
  disown

  if _wait_for_port "$COMFYUI_PORT" 30; then
    echo "  ComfyUI ready on http://127.0.0.1:$COMFYUI_PORT"
  else
    echo "  ComfyUI failed to start — check $LOGDIR/comfyui.log"
    return 1
  fi
}

stop_comfyui() {
  if [ -f "$PIDDIR/comfyui.pid" ]; then
    local pid
    pid=$(cat "$PIDDIR/comfyui.pid")
    if _pid_alive "$pid"; then
      kill "$pid" 2>/dev/null
      echo "  ComfyUI (pid $pid) stopped"
    fi
    rm -f "$PIDDIR/comfyui.pid"
  fi
  lsof -ti:"$COMFYUI_PORT" 2>/dev/null | xargs kill 2>/dev/null || true
}

status_comfyui() {
  if _port_listening "$COMFYUI_PORT"; then
    local pid
    pid=$(cat "$PIDDIR/comfyui.pid" 2>/dev/null || echo "?")
    echo "  ComfyUI   :$COMFYUI_PORT  ✓  (pid $pid)"
  else
    echo "  ComfyUI   :$COMFYUI_PORT  ✗  not running"
  fi
}

# ── element ────────────────────────────────────────────────────────────

start_element() {
  if pgrep -q -f "Element.app"; then
    echo "  Element already running"
    return 0
  fi

  if [ ! -f "$ELEMENT_ELS" ]; then
    echo "  Element session not found at $ELEMENT_ELS — skipping"
    return 0
  fi

  echo "  Launching Element with EQ_COMP_VERB_RACK.els..."
  open -a Element "$ELEMENT_ELS" >> "$LOGDIR/element.log" 2>&1
  sleep 3

  if pgrep -q -f "Element.app"; then
    echo "  Element ready (Rare → LALA → reverb/delay chain)"
  else
    echo "  Element failed to launch — check $LOGDIR/element.log"
    return 1
  fi
}

stop_element() {
  if pgrep -q -f "Element.app"; then
    pkill -f "Element.app" 2>/dev/null || true
    echo "  Element stopped"
  fi
}

status_element() {
  if pgrep -q -f "Element.app"; then
    echo "  Element   GUI  ✓  running"
  else
    echo "  Element   GUI  ✗  not running"
  fi
}

# ── backend ────────────────────────────────────────────────────────────

start_backend() {
  if _port_listening "$BACKEND_PORT"; then
    echo "  Backend already running on :$BACKEND_PORT"
    return 0
  fi

  _ensure_dirs
  echo "  Starting backend..."
  cd "$ROOT/backend"
  source ./venv/bin/activate
  nohup python -m src.web_server >> "$LOGDIR/backend.log" 2>&1 &
  echo $! > "$PIDDIR/backend.pid"
  disown

  if _wait_for_port "$BACKEND_PORT" 15; then
    echo "  Backend ready on http://127.0.0.1:$BACKEND_PORT"
  else
    echo "  Backend failed to start — check $LOGDIR/backend.log"
    return 1
  fi
}

stop_backend() {
  if [ -f "$PIDDIR/backend.pid" ]; then
    local pid
    pid=$(cat "$PIDDIR/backend.pid")
    if _pid_alive "$pid"; then
      kill "$pid" 2>/dev/null
      echo "  Backend (pid $pid) stopped"
    fi
    rm -f "$PIDDIR/backend.pid"
  fi
  lsof -ti:"$BACKEND_PORT" 2>/dev/null | xargs kill 2>/dev/null || true
}

status_backend() {
  if _port_listening "$BACKEND_PORT"; then
    local pid
    pid=$(cat "$PIDDIR/backend.pid" 2>/dev/null || echo "?")
    echo "  Backend   :$BACKEND_PORT  ✓  (pid $pid)"
  else
    echo "  Backend   :$BACKEND_PORT  ✗  not running"
  fi
}

# ── frontend ───────────────────────────────────────────────────────────

start_frontend() {
  if _port_listening "$FRONTEND_PORT"; then
    echo "  Frontend already running on :$FRONTEND_PORT"
    return 0
  fi

  _ensure_dirs
  echo "  Starting frontend..."
  cd "$ROOT/frontend"
  nohup npm run dev >> "$LOGDIR/frontend.log" 2>&1 &
  echo $! > "$PIDDIR/frontend.pid"
  disown

  if _wait_for_port "$FRONTEND_PORT" 20; then
    echo "  Frontend ready on http://localhost:$FRONTEND_PORT"
  else
    echo "  Frontend failed to start — check $LOGDIR/frontend.log"
    return 1
  fi
}

stop_frontend() {
  if [ -f "$PIDDIR/frontend.pid" ]; then
    local pid
    pid=$(cat "$PIDDIR/frontend.pid")
    if _pid_alive "$pid"; then
      kill "$pid" 2>/dev/null
      echo "  Frontend (pid $pid) stopped"
    fi
    rm -f "$PIDDIR/frontend.pid"
  fi
  lsof -ti:"$FRONTEND_PORT" 2>/dev/null | xargs kill 2>/dev/null || true
}

status_frontend() {
  if _port_listening "$FRONTEND_PORT"; then
    local pid
    pid=$(cat "$PIDDIR/frontend.pid" 2>/dev/null || echo "?")
    echo "  Frontend  :$FRONTEND_PORT  ✓  (pid $pid)"
  else
    echo "  Frontend  :$FRONTEND_PORT  ✗  not running"
  fi
}

# ── main ──────────────────────────────────────────────────────────────

case "${1:-}" in
  start)
    echo "Starting multi-agent system..."
    echo ""

    # 1. Audio routing — must happen before Element so it picks up the correct device
    echo "── Audio chain ──"
    _set_audio_output "$AUDIO_OUTPUT_DEVICE"
    echo ""

    # 2. Ollama — needed for Magic Coder local models
    echo "── Ollama ──"
    start_ollama
    echo ""

    # 3. ComfyUI — optional image renderer
    echo "── ComfyUI ──"
    start_comfyui
    echo ""

    # 4. Element — VST plugin host (loads after audio routing is set)
    echo "── Element ──"
    start_element
    echo ""

    # 5. Backend
    echo "── Backend ──"
    start_backend
    echo ""

    # 6. Frontend
    echo "── Frontend ──"
    start_frontend
    echo ""

    echo "────────────────────────────────────────"
    echo "Multi-agent system ready."
    echo "  Frontend: http://localhost:$FRONTEND_PORT"
    echo "  Backend:  http://127.0.0.1:$BACKEND_PORT"
    echo "  ComfyUI:  http://127.0.0.1:$COMFYUI_PORT"
    echo "  Ollama:   http://127.0.0.1:$OLLAMA_PORT"
    echo "  Audio:    System output → BlackHole 2ch → Element → Speakers"
    echo "────────────────────────────────────────"
    ;;

  stop)
    echo "Stopping multi-agent system..."
    echo ""

    echo "── Frontend ──"
    stop_frontend

    echo "── Backend ──"
    stop_backend

    echo "── Element ──"
    stop_element

    echo "── ComfyUI ──"
    stop_comfyui

    echo "── Ollama ──"
    stop_ollama

    # Restore audio output after Element is closed
    echo ""
    echo "── Audio chain ──"
    _set_audio_output "$AUDIO_RESTORE_DEVICE"

    echo ""
    echo "All services stopped."
    ;;

  status)
    echo "Multi-agent system status:"
    echo ""
    echo "── Audio ──"
    echo "  Output: $(SwitchAudioSource -t output -c 2>/dev/null || echo 'unknown')"
    echo ""
    echo "── Services ──"
    status_ollama
    status_comfyui
    status_element
    status_backend
    status_frontend
    ;;

  restart)
    echo "Restarting multi-agent system..."
    "$0" stop
    sleep 2
    "$0" start
    ;;

  *)
    echo "Usage: $0 {start|stop|status|restart}"
    exit 1
    ;;
esac
