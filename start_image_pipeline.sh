#!/bin/zsh
# start_image_pipeline.sh — launch / stop / status / restart the full multi-agent stack.
#
# Services:
#   Ollama     :11434   local LLM host (required for Magic Coder)
#   ComfyUI    :8188    image renderer (optional)
#   Element    GUI      VST/AU plugin host (Rare → LALA → reverb/delay)
#   LangGraph  :8123    supervisor graph server (core — UI talks to this)
#   Backend    :8000    FastAPI sidecar (TTS/STT/models list)
#   Frontend   :3001    Next.js chat UI (production build, served by next start)
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
#   ./start_image_pipeline.sh restart-core  Restart LangGraph, sidecar, and UI only

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
LOGDIR="$ROOT/logs"
PIDDIR="$ROOT/.pids"

# Make sure Docker Desktop CLI is on PATH (Docker.app is not always linked into /usr/local/bin)
export PATH="/Applications/Docker.app/Contents/Resources/bin:${PATH}"

# ── config ────────────────────────────────────────────────────────────

OLLAMA_PORT=11434
COMFYUI_PORT=8188
LANGGRAPH_PORT=8123
BACKEND_PORT=8000
FRONTEND_PORT=3001

COMFYUI_DIR="$HOME/fun-multi-character-chats/ComfyUI"
COMFYUI_PYTHON="$HOME/fun-multi-character-chats/.venv/bin/python"

# Set COMFYUI_AUTO_START=1 to launch ComfyUI on startup.
# It is intentionally OFF by default so checkpoint/model loading
# does not slow down the core chat startup.
COMFYUI_AUTO_START="${COMFYUI_AUTO_START:-0}"

ELEMENT_ELS="$HOME/Documents/EQ_COMP_VERB_RACK.els"
ELEMENT_BIN="/Applications/Element.app/Contents/MacOS/Element"

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
  "$ELEMENT_BIN" "$ELEMENT_ELS" >> "$LOGDIR/element.log" 2>&1 &
  sleep 4

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

# ── langgraph ──────────────────────────────────────────────────────────

start_langgraph() {
  if _port_listening "$LANGGRAPH_PORT"; then
    echo "  LangGraph already running on :$LANGGRAPH_PORT"
    return 0
  fi

  _ensure_dirs
  echo "  Starting LangGraph (graph server)..."
  cd "$ROOT/backend"
  nohup ./.venv/bin/langgraph up --port "$LANGGRAPH_PORT" --wait \
    --docker-compose "$ROOT/backend/docker-compose.override.yml" \
    >> "$LOGDIR/langgraph.log" 2>&1 &
  echo $! > "$PIDDIR/langgraph.pid"
  disown

  if _wait_for_port "$LANGGRAPH_PORT" 180; then
    echo "  LangGraph ready on http://127.0.0.1:$LANGGRAPH_PORT"
  else
    echo "  LangGraph failed to start — check $LOGDIR/langgraph.log"
    return 1
  fi
}

stop_langgraph() {
  local project_name="backend"
  local container_ids

  # Stop the supervising CLI before removing its containers. Otherwise the
  # still-running `langgraph up` process can keep :8123 alive long enough for
  # restart-core to mistake the old server for the replacement.
  if [ -f "$PIDDIR/langgraph.pid" ]; then
    local supervisor_pid
    supervisor_pid=$(cat "$PIDDIR/langgraph.pid")
    if _pid_alive "$supervisor_pid"; then
      kill "$supervisor_pid" 2>/dev/null || true
      local attempt
      for attempt in {1..50}; do
        _pid_alive "$supervisor_pid" || break
        sleep 0.1
      done
    fi
  fi

  container_ids=$(docker ps -aq \
    --filter "label=com.docker.compose.project=$project_name" 2>/dev/null)

  if [ -n "$container_ids" ]; then
    echo "$container_ids" | xargs docker rm -f >/dev/null
    docker network rm "${project_name}_default" >/dev/null 2>&1 || true
    echo "  LangGraph stopped and removed"
  else
    echo "  LangGraph not running"
  fi

  rm -f "$PIDDIR/langgraph.pid" 2>/dev/null || true

  local attempt
  for attempt in {1..50}; do
    _port_listening "$LANGGRAPH_PORT" || break
    sleep 0.1
  done
  if _port_listening "$LANGGRAPH_PORT"; then
    echo "  LangGraph port :$LANGGRAPH_PORT is still in use; refusing a false restart"
    return 1
  fi
}

status_langgraph() {
  if _port_listening "$LANGGRAPH_PORT"; then
    local pid
    pid=$(cat "$PIDDIR/langgraph.pid" 2>/dev/null || echo "?")
    echo "  LangGraph :$LANGGRAPH_PORT  ✓  (pid $pid)"
  else
    echo "  LangGraph :$LANGGRAPH_PORT  ✗  not running"
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
  source ./.venv/bin/activate
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
  cd "$ROOT/agent-chat-ui"

  # Auto-rebuild: rebuild the production bundle if .next/BUILD_ID is missing
  # or any UI source/config file is newer than the last build. This lets the
  # user (or their coding agent) edit UI code and have the next launch pick up
  # the changes automatically — no manual `pnpm build` step required.
  local needs_build=0
  if [ ! -f ".next/BUILD_ID" ]; then
    needs_build=1
  else
    local build_mtime newest_src input_mtime
    build_mtime=$(stat -f %m .next/BUILD_ID 2>/dev/null || echo 0)
    newest_src=$(find src public scripts -type f -exec stat -f %m {} + 2>/dev/null | sort -rn | head -1)
    for build_input in package.json pnpm-lock.yaml next.config.* postcss.config.*; do
      if [ -e "$build_input" ]; then
        input_mtime=$(stat -f %m "$build_input" 2>/dev/null || echo 0)
        if [ "$input_mtime" -gt "$newest_src" ]; then
          newest_src="$input_mtime"
        fi
      fi
    done
    newest_src=${newest_src:-0}
    if [ "$newest_src" -gt "$build_mtime" ]; then
      needs_build=1
    fi
  fi

  if [ "$needs_build" = "1" ]; then
    echo "  Building frontend (production)..."
    ./node_modules/.bin/next build >> "$LOGDIR/frontend-build.log" 2>&1 || {
      echo "  Frontend build failed — check $LOGDIR/frontend-build.log"
      return 1
    }
  else
    echo "  Using cached build (.next/BUILD_ID up to date)"
  fi

  echo "  Starting frontend (production server)..."
  nohup ./node_modules/.bin/next start -p "$FRONTEND_PORT" >> "$LOGDIR/frontend.log" 2>&1 &
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

    # ── Core services (blocking) — chat is unusable without these ──
    # Start langgraph + sidecar + frontend first; the user gets a working
    # chat in ~5-15s instead of waiting on Ollama/ComfyUI/Element.

    echo "── LangGraph (graph server, port $LANGGRAPH_PORT) ──"
    start_langgraph
    echo ""

    echo "── Backend (sidecar, port $BACKEND_PORT) ──"
    start_backend
    echo ""

    echo "── Frontend (UI, port $FRONTEND_PORT) ──"
    start_frontend
    echo ""

    # ── Heavy services (parallel, non-blocking) — chat works without these ──
    # Ollama is needed for Magic Coder, ComfyUI for image rendering, Element
    # for the audio chain. If they fail, the core chat still works. Use
    # `set +e` so a failing start_* doesn't kill the script.
    set +e
    (
      echo "── Ollama (background) ──"
      start_ollama
      echo ""

      if [ "$COMFYUI_AUTO_START" = "1" ]; then
        echo "── ComfyUI (background) ──"
        start_comfyui
        echo ""
      fi

      # Audio routing must happen before Element so it picks up the correct device
      echo "── Audio chain ──"
      _set_audio_output "$AUDIO_OUTPUT_DEVICE"
      echo ""

      echo "── Element (VST host, background) ──"
      start_element
      echo ""
    ) &
    HEAVY_PID=$!
    disown $HEAVY_PID 2>/dev/null || true
    set -e

    echo "────────────────────────────────────────"
    echo "Multi-agent system ready."
    echo "  Frontend:  http://localhost:$FRONTEND_PORT"
    echo "  LangGraph: http://127.0.0.1:$LANGGRAPH_PORT"
    echo "  Backend:   http://127.0.0.1:$BACKEND_PORT"
    if [ "$COMFYUI_AUTO_START" = "1" ]; then
      echo "  ComfyUI:   http://127.0.0.1:$COMFYUI_PORT  (starting in background)"
    else
      echo "  ComfyUI:   off by default (set COMFYUI_AUTO_START=1 to enable)"
    fi
    echo "  Ollama:    http://127.0.0.1:$OLLAMA_PORT   (starting in background)"
    echo "  Audio:     System output → BlackHole 2ch → Element → Speakers (background)"
    echo "────────────────────────────────────────"
    ;;

  stop)
    echo "Stopping multi-agent system..."
    echo ""

    echo "── Frontend ──"
    stop_frontend

    echo "── Backend ──"
    stop_backend

    echo "── LangGraph ──"
    stop_langgraph

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
    echo "── Core services ──"
    status_langgraph
    status_backend
    status_frontend
    echo ""
    echo "── Heavy services ──"
    status_ollama
    status_comfyui
    status_element
    ;;

  restart)
    echo "Restarting multi-agent system..."
    "$0" stop
    sleep 2
    "$0" start
    ;;

  restart-core)
    echo "Restarting core chat services..."
    echo ""
    stop_frontend
    stop_backend
    stop_langgraph
    echo ""
    start_langgraph
    start_backend
    start_frontend
    echo ""
    echo "Core chat services ready at http://localhost:$FRONTEND_PORT"
    ;;

  *)
    echo "Usage: $0 {start|stop|status|restart|restart-core}"
    exit 1
    ;;
esac
