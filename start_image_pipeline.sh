#!/bin/zsh
# start_image_pipeline.sh — launch / stop / status / restart the full multi-agent stack.
#
# Services:
#   Ollama     :11434   local LLM host (required for Magic Coder)
#   ComfyUI    :8188    image renderer (optional)
#   Element    GUI      VST/AU plugin host (Rare → LALA → reverb/delay)
#   Host exec  :8765    optional, separately installed macOS executor (loopback only)
#   Docker brk :8766    optional, separately installed Docker broker (loopback only)
#   LangGraph  :8123    supervisor graph server (core — UI talks to this)
#   Backend    :8000    FastAPI sidecar (TTS/STT/models list)
#   Frontend   :3001    Next.js chat UI (production build, served by next start)
#
# The host executor and Docker broker are never installed or updated by ordinary
# start/restart/restart-core. An operator must explicitly run the corresponding
# install command; this launcher performs no canary actions.
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
#   ./start_image_pipeline.sh restart-core  Restart host executor and core services
#   ./start_image_pipeline.sh install-host-executor  Explicit operator-only install
#   ./start_image_pipeline.sh install-docker-broker  Explicit operator-only install

set -e
umask 077

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
HOST_EXECUTOR_PORT=8765
DOCKER_BROKER_PORT=8766

# This installation is deliberately outside every writable repository. Runtime
# startup only consumes this integrity-checked snapshot; it never imports from ROOT.
HOST_EXECUTOR_ROOT="$HOME/.jasper/macos-host-executor"
HOST_EXECUTOR_RUNTIME="$HOST_EXECUTOR_ROOT/runtime"
HOST_EXECUTOR_PRIVATE="$HOST_EXECUTOR_ROOT/private"
HOST_EXECUTOR_PUBLIC="$HOST_EXECUTOR_ROOT/public"
HOST_EXECUTOR_POLICY="$HOST_EXECUTOR_PRIVATE/config/policy.json"
HOST_EXECUTOR_STATE="$HOST_EXECUTOR_PRIVATE/state"
HOST_EXECUTOR_PIDFILE="$HOST_EXECUTOR_PRIVATE/run/executor.pid"
HOST_EXECUTOR_LOG="$HOST_EXECUTOR_PRIVATE/logs/executor-redacted.log"
HOST_EXECUTOR_PYTHON="$HOST_EXECUTOR_RUNTIME/venv/bin/python"
HOST_EXECUTOR_HELPER="$HOST_EXECUTOR_RUNTIME/bin/macos-host-confirmation"
HOST_EXECUTOR_PUBLIC_KEY="$HOST_EXECUTOR_PUBLIC/receipt-signing.pub"
HOST_EXECUTOR_AGENT_SERVER="http://127.0.0.1:8123"
HOST_EXECUTOR_BOOTSTRAP_PYTHON="${HOST_EXECUTOR_BOOTSTRAP_PYTHON:-$(command -v python3 2>/dev/null || true)}"

# Like the host executor, the broker runs only from an operator-installed,
# integrity-checked snapshot outside the writable repository.
DOCKER_BROKER_ROOT="$HOME/.jasper/docker-broker"
DOCKER_BROKER_RUNTIME="$DOCKER_BROKER_ROOT/runtime"
DOCKER_BROKER_PRIVATE="$DOCKER_BROKER_ROOT/private"
DOCKER_BROKER_STATE="$DOCKER_BROKER_PRIVATE/state"
DOCKER_BROKER_PIDFILE="$DOCKER_BROKER_PRIVATE/run/broker.pid"
DOCKER_BROKER_LOG="$DOCKER_BROKER_PRIVATE/logs/broker.log"
DOCKER_BROKER_PYTHON="$DOCKER_BROKER_RUNTIME/venv/bin/python"
DOCKER_BROKER_AGENT_SERVER="http://127.0.0.1:8123"
DOCKER_BROKER_OWNER="local-owner-v1"
DOCKER_BROKER_LEASE_SECONDS=14400
DOCKER_BROKER_DOCKER="/usr/local/bin/docker"
DOCKER_BROKER_ALLOWED_ROOT="${DOCKER_BROKER_ALLOWED_ROOT:-$ROOT}"
DOCKER_BROKER_BOOTSTRAP_PYTHON="${DOCKER_BROKER_BOOTSTRAP_PYTHON:-$(command -v python3 2>/dev/null || true)}"

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
  mkdir -p "$LOGDIR" "$PIDDIR" "$HOST_EXECUTOR_PUBLIC"
  chmod 755 "$HOST_EXECUTOR_PUBLIC"
}

_pid_alive() {
  [ -n "$1" ] && kill -0 "$1" 2>/dev/null
}

_port_listening() {
  lsof -nP -tiTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
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

_wait_for_backend_ready() {
  local max="${1:-60}"
  for _ in $(seq 1 "$max"); do
    if curl -fsS --connect-timeout 2 --max-time 10 \
        "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null && \
      curl -fsS --connect-timeout 2 --max-time 30 \
        "http://127.0.0.1:$BACKEND_PORT/api/models" | \
        grep -Eq '"models"[[:space:]]*:[[:space:]]*\[[[:space:]]*\{' && \
      curl -fsS --connect-timeout 2 --max-time 30 \
        "http://127.0.0.1:$BACKEND_PORT/api/tts/voices" | \
        grep -Eq '"voices"[[:space:]]*:[[:space:]]*\[[[:space:]]*"'; then
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

# ── optional macOS host executor ───────────────────────────────────────

_host_executor_installed() {
  [ -f "$HOST_EXECUTOR_RUNTIME/integrity.sha256" ]
}

_host_executor_process_executable() {
  "$HOST_EXECUTOR_PYTHON" -B -c 'import ctypes, os; buffer = ctypes.create_string_buffer(4096); libproc = ctypes.CDLL("/usr/lib/libproc.dylib"); size = libproc.proc_pidpath(os.getpid(), buffer, len(buffer)); assert size > 0; print(os.fsdecode(buffer.value))'
}

_host_executor_command() {
  local process_executable
  process_executable=$(_host_executor_process_executable) || return 1
  print -r -- "$process_executable -B -m macos_host_executor --host 127.0.0.1 --port $HOST_EXECUTOR_PORT --policy-json $HOST_EXECUTOR_POLICY --agent-server-url $HOST_EXECUTOR_AGENT_SERVER --confirmation-helper $HOST_EXECUTOR_HELPER --state-directory $HOST_EXECUTOR_STATE --public-key-output $HOST_EXECUTOR_PUBLIC_KEY"
}

_host_executor_pid_matches() {
  local pid="$1" expected actual
  [[ "$pid" == <-> ]] || return 1
  _pid_alive "$pid" || return 1
  expected=$(_host_executor_command)
  actual=$(ps -p "$pid" -o command= 2>/dev/null) || return 1
  [ "$actual" = "$expected" ]
}

_verify_host_executor_integrity() {
  _host_executor_installed || return 1
  (cd "$HOST_EXECUTOR_RUNTIME" && /usr/bin/shasum -a 256 -c integrity.sha256 >/dev/null 2>&1)
}

_host_executor_healthy() {
  local body
  body=$(curl -fsS --connect-timeout 1 --max-time 2 \
    "http://127.0.0.1:$HOST_EXECUTOR_PORT/health" 2>/dev/null) || return 1
  print -r -- "$body" | grep -Eq '"ok"[[:space:]]*:[[:space:]]*true' && \
    print -r -- "$body" | grep -Eq '"service"[[:space:]]*:[[:space:]]*"macos-host-executor"'
}

install_host_executor() {
  if [ ! -t 0 ]; then
    echo "  Refusing non-interactive host-executor installation."
    return 1
  fi
  if [ ! -x "$HOST_EXECUTOR_BOOTSTRAP_PYTHON" ] || \
    ! "$HOST_EXECUTOR_BOOTSTRAP_PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
    echo "  Python 3.11 or newer is required; set HOST_EXECUTOR_BOOTSTRAP_PYTHON."
    return 1
  fi
  echo "This operator-only action snapshots the current executor source outside the repo."
  echo "It installs Python dependencies and compiles the native Swift confirmation helper."
  printf "Type INSTALL to continue: "
  local answer
  read -r answer
  [ "$answer" = "INSTALL" ] || { echo "  Installation cancelled."; return 1; }

  if [ -f "$HOST_EXECUTOR_PIDFILE" ]; then
    local running_pid
    running_pid=$(cat "$HOST_EXECUTOR_PIDFILE" 2>/dev/null || true)
    if _host_executor_pid_matches "$running_pid" || \
      { [[ "$running_pid" == <-> ]] && _pid_alive "$running_pid"; }; then
      echo "  Stop the exact host-executor process before replacing its runtime snapshot."
      return 1
    fi
    # A dead PID is only stale state. Removing the file cannot signal a reused PID.
    rm -f "$HOST_EXECUTOR_PIDFILE"
  fi

  umask 077
  mkdir -p "$HOST_EXECUTOR_ROOT" "$HOST_EXECUTOR_PRIVATE/config" \
    "$HOST_EXECUTOR_PRIVATE/state" "$HOST_EXECUTOR_PRIVATE/run" \
    "$HOST_EXECUTOR_PRIVATE/logs" "$HOST_EXECUTOR_PRIVATE/tmp" \
    "$HOST_EXECUTOR_PRIVATE/home" "$HOST_EXECUTOR_PUBLIC"
  chmod 700 "$HOST_EXECUTOR_ROOT" "$HOST_EXECUTOR_PRIVATE" \
    "$HOST_EXECUTOR_PRIVATE/config" "$HOST_EXECUTOR_PRIVATE/state" \
    "$HOST_EXECUTOR_PRIVATE/run" "$HOST_EXECUTOR_PRIVATE/logs" \
    "$HOST_EXECUTOR_PRIVATE/tmp" "$HOST_EXECUTOR_PRIVATE/home"
  chmod 755 "$HOST_EXECUTOR_PUBLIC"

  local staged="$HOST_EXECUTOR_ROOT/.runtime-new-$$"
  rm -rf "$staged"
  mkdir -p "$staged/snapshot" "$staged/bin"
  /usr/bin/ditto --noqtn "$ROOT/macos-host-executor" "$staged/snapshot"
  rm -rf "$staged/snapshot/.pytest_cache" "$staged/snapshot/.ruff_cache" \
    "$staged/snapshot/.venv" "$staged/snapshot/native/ConfirmationHelper/.build"

  echo "  Creating isolated Python environment..."
  "$HOST_EXECUTOR_BOOTSTRAP_PYTHON" -m venv "$staged/venv"
  "$staged/venv/bin/python" -m pip install --disable-pip-version-check \
    "$staged/snapshot"

  echo "  Compiling native confirmation helper..."
  /usr/bin/xcrun swift build -c release \
    --package-path "$staged/snapshot/native/ConfirmationHelper"
  cp "$staged/snapshot/native/ConfirmationHelper/.build/release/macos-host-confirmation" \
    "$staged/bin/macos-host-confirmation"
  rm -rf "$staged/snapshot/native/ConfirmationHelper/.build"
  chmod 500 "$staged/bin/macos-host-confirmation"

  (cd "$staged" && find snapshot venv bin -type f \
    -exec /usr/bin/shasum -a 256 {} + | LC_ALL=C sort > integrity.sha256)
  chmod -R a-w "$staged"
  find "$staged" -type d -exec chmod a+rx {} +
  chmod u+w "$staged"

  local previous="$HOST_EXECUTOR_ROOT/.runtime-previous"
  rm -rf "$previous"
  [ ! -d "$HOST_EXECUTOR_RUNTIME" ] || mv "$HOST_EXECUTOR_RUNTIME" "$previous"
  mv "$staged" "$HOST_EXECUTOR_RUNTIME"
  chmod a-w "$HOST_EXECUTOR_RUNTIME"
  rm -rf "$previous"

  if [ ! -f "$HOST_EXECUTOR_POLICY" ]; then
    cp "$HOST_EXECUTOR_RUNTIME/snapshot/policy.example.json" "$HOST_EXECUTOR_POLICY"
    chmod 600 "$HOST_EXECUTOR_POLICY"
  fi
  echo "  Installed integrity-isolated runtime at $HOST_EXECUTOR_RUNTIME"
  echo "  Review $HOST_EXECUTOR_POLICY before enabling any host action."
  echo "  No host operation or canary was run."
}

start_host_executor() {
  if ! _host_executor_installed; then
    echo "  macOS host operations unavailable (operator has not installed executor)"
    return 0
  fi
  if ! _verify_host_executor_integrity; then
    echo "  Host executor integrity check failed; refusing core startup"
    return 1
  fi
  if [ ! -f "$HOST_EXECUTOR_POLICY" ]; then
    echo "  Host executor policy is missing; refusing core startup"
    return 1
  fi

  local pid=""
  [ ! -f "$HOST_EXECUTOR_PIDFILE" ] || pid=$(cat "$HOST_EXECUTOR_PIDFILE" 2>/dev/null || true)
  if _host_executor_pid_matches "$pid"; then
    if _host_executor_healthy; then
      echo "  macOS host executor already healthy on 127.0.0.1:$HOST_EXECUTOR_PORT (pid $pid)"
      return 0
    fi
    echo "  Installed host executor has matching process identity but is unhealthy"
    return 1
  elif [[ "$pid" == <-> ]] && _pid_alive "$pid"; then
    echo "  Refusing live foreign executor PID identity in $HOST_EXECUTOR_PIDFILE"
    return 1
  elif [ -n "$pid" ]; then
    # Dead/malformed PID state is safe to clear; never signal it.
    rm -f "$HOST_EXECUTOR_PIDFILE"
  fi

  umask 077
  mkdir -p "$HOST_EXECUTOR_STATE" "$HOST_EXECUTOR_PRIVATE/run" \
    "$HOST_EXECUTOR_PRIVATE/logs" "$HOST_EXECUTOR_PRIVATE/tmp" \
    "$HOST_EXECUTOR_PRIVATE/home" "$HOST_EXECUTOR_PUBLIC"
  chmod 700 "$HOST_EXECUTOR_PRIVATE" "$HOST_EXECUTOR_STATE" \
    "$HOST_EXECUTOR_PRIVATE/run" "$HOST_EXECUTOR_PRIVATE/logs" \
    "$HOST_EXECUTOR_PRIVATE/tmp" "$HOST_EXECUTOR_PRIVATE/home"
  chmod 755 "$HOST_EXECUTOR_PUBLIC"
  touch "$HOST_EXECUTOR_LOG"
  chmod 600 "$HOST_EXECUTOR_LOG"

  echo "  Starting optional macOS host executor..."
  nohup env -i HOME="$HOST_EXECUTOR_PRIVATE/home" PATH="/usr/bin:/bin:/usr/sbin:/sbin" \
    TMPDIR="$HOST_EXECUTOR_PRIVATE/tmp" PYTHONDONTWRITEBYTECODE=1 \
    "$HOST_EXECUTOR_PYTHON" -B -m macos_host_executor \
    --host 127.0.0.1 --port "$HOST_EXECUTOR_PORT" \
    --policy-json "$HOST_EXECUTOR_POLICY" \
    --agent-server-url "$HOST_EXECUTOR_AGENT_SERVER" \
    --confirmation-helper "$HOST_EXECUTOR_HELPER" \
    --state-directory "$HOST_EXECUTOR_STATE" \
    --public-key-output "$HOST_EXECUTOR_PUBLIC_KEY" \
    >> "$HOST_EXECUTOR_LOG" 2>&1 &
  pid=$!
  print -r -- "$pid" > "$HOST_EXECUTOR_PIDFILE"
  disown

  local attempt
  for attempt in {1..30}; do
    if ! _host_executor_pid_matches "$pid"; then
      echo "  Host executor exited or changed identity; refusing core startup"
      rm -f "$HOST_EXECUTOR_PIDFILE"
      return 1
    fi
    if _host_executor_healthy; then
      chmod 444 "$HOST_EXECUTOR_PUBLIC_KEY"
      echo "  macOS host executor healthy on http://127.0.0.1:$HOST_EXECUTOR_PORT"
      return 0
    fi
    sleep 1
  done
  echo "  Installed host executor failed health checks; refusing core startup"
  return 1
}

stop_host_executor() {
  if [ ! -f "$HOST_EXECUTOR_PIDFILE" ]; then
    echo "  macOS host executor not running"
    return 0
  fi
  local pid
  pid=$(cat "$HOST_EXECUTOR_PIDFILE" 2>/dev/null || true)
  if ! _host_executor_pid_matches "$pid"; then
    if [[ "$pid" == <-> ]] && _pid_alive "$pid"; then
      echo "  Refusing to signal live foreign host-executor PID '$pid'"
      return 1
    fi
    rm -f "$HOST_EXECUTOR_PIDFILE"
    echo "  Removed stale host-executor PID state without signaling a process"
    return 0
  fi
  kill -TERM "$pid"
  local attempt
  for attempt in {1..50}; do
    _pid_alive "$pid" || break
    sleep 0.1
  done
  if _pid_alive "$pid"; then
    if ! _host_executor_pid_matches "$pid"; then
      echo "  Host-executor identity changed during stop; refusing further signals"
      return 1
    fi
    kill -KILL "$pid"
  fi
  rm -f "$HOST_EXECUTOR_PIDFILE"
  echo "  macOS host executor (pid $pid) stopped"
}

status_host_executor() {
  if ! _host_executor_installed; then
    echo "  Host exec  :$HOST_EXECUTOR_PORT  –  unavailable (not installed)"
    return 0
  fi
  local pid=""
  [ ! -f "$HOST_EXECUTOR_PIDFILE" ] || pid=$(cat "$HOST_EXECUTOR_PIDFILE" 2>/dev/null || true)
  if _host_executor_pid_matches "$pid" && _host_executor_healthy; then
    echo "  Host exec  :$HOST_EXECUTOR_PORT  ✓  healthy (pid $pid)"
  elif [ -n "$pid" ]; then
    echo "  Host exec  :$HOST_EXECUTOR_PORT  !  installed but unhealthy/identity mismatch"
    return 1
  else
    echo "  Host exec  :$HOST_EXECUTOR_PORT  ✗  installed but stopped"
    return 1
  fi
}

# ── optional Docker broker ─────────────────────────────────────────────

_docker_broker_installed() {
  [ -f "$DOCKER_BROKER_RUNTIME/integrity.sha256" ]
}

_docker_broker_process_executable() {
  "$DOCKER_BROKER_PYTHON" -B -c 'import ctypes, os; buffer = ctypes.create_string_buffer(4096); libproc = ctypes.CDLL("/usr/lib/libproc.dylib"); size = libproc.proc_pidpath(os.getpid(), buffer, len(buffer)); assert size > 0; print(os.fsdecode(buffer.value))'
}

_docker_broker_command() {
  local process_executable
  process_executable=$(_docker_broker_process_executable) || return 1
  print -r -- "$process_executable -B -m docker_broker --host 127.0.0.1 --port $DOCKER_BROKER_PORT --allowed-root $DOCKER_BROKER_ALLOWED_ROOT --state-directory $DOCKER_BROKER_STATE --docker-path $DOCKER_BROKER_DOCKER --agent-server-url $DOCKER_BROKER_AGENT_SERVER --owner-id $DOCKER_BROKER_OWNER --lease-seconds $DOCKER_BROKER_LEASE_SECONDS --allow-builds"
}

_docker_broker_pid_matches() {
  local pid="$1" expected actual
  [[ "$pid" == <-> ]] || return 1
  _pid_alive "$pid" || return 1
  expected=$(_docker_broker_command) || return 1
  actual=$(ps -p "$pid" -o command= 2>/dev/null) || return 1
  [ "$actual" = "$expected" ]
}

_verify_docker_broker_integrity() {
  _docker_broker_installed || return 1
  (cd "$DOCKER_BROKER_RUNTIME" && /usr/bin/shasum -a 256 -c integrity.sha256 >/dev/null 2>&1)
}

_docker_broker_healthy() {
  local body
  body=$(curl -fsS --connect-timeout 1 --max-time 2 \
    "http://127.0.0.1:$DOCKER_BROKER_PORT/health" 2>/dev/null) || return 1
  print -r -- "$body" | grep -Eq '"service"[[:space:]]*:[[:space:]]*"docker-broker"'
}

install_docker_broker() {
  if [ ! -t 0 ]; then
    echo "  Refusing non-interactive Docker-broker installation."
    return 1
  fi
  if [ ! -x "$DOCKER_BROKER_BOOTSTRAP_PYTHON" ] || \
    ! "$DOCKER_BROKER_BOOTSTRAP_PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
    echo "  Python 3.11 or newer is required; set DOCKER_BROKER_BOOTSTRAP_PYTHON."
    return 1
  fi
  echo "This operator-only action snapshots the current Docker broker outside the repo."
  printf "Type INSTALL to continue: "
  local answer
  read -r answer
  [ "$answer" = "INSTALL" ] || { echo "  Installation cancelled."; return 1; }

  if [ -f "$DOCKER_BROKER_PIDFILE" ]; then
    local running_pid
    running_pid=$(cat "$DOCKER_BROKER_PIDFILE" 2>/dev/null || true)
    if _docker_broker_pid_matches "$running_pid" || \
      { [[ "$running_pid" == <-> ]] && _pid_alive "$running_pid"; }; then
      echo "  Stop the exact Docker-broker process before replacing its runtime snapshot."
      return 1
    fi
    rm -f "$DOCKER_BROKER_PIDFILE"
  fi

  umask 077
  mkdir -p "$DOCKER_BROKER_ROOT" "$DOCKER_BROKER_PRIVATE/state" \
    "$DOCKER_BROKER_PRIVATE/run" "$DOCKER_BROKER_PRIVATE/logs" \
    "$DOCKER_BROKER_PRIVATE/tmp" "$DOCKER_BROKER_PRIVATE/home"
  chmod 700 "$DOCKER_BROKER_ROOT" "$DOCKER_BROKER_PRIVATE" \
    "$DOCKER_BROKER_PRIVATE/state" "$DOCKER_BROKER_PRIVATE/run" \
    "$DOCKER_BROKER_PRIVATE/logs" "$DOCKER_BROKER_PRIVATE/tmp" \
    "$DOCKER_BROKER_PRIVATE/home"

  local staged="$DOCKER_BROKER_ROOT/.runtime-new-$$"
  rm -rf "$staged"
  mkdir -p "$staged/snapshot"
  /usr/bin/ditto --noqtn "$ROOT/docker-broker" "$staged/snapshot"
  rm -rf "$staged/snapshot/.pytest_cache" "$staged/snapshot/.ruff_cache" \
    "$staged/snapshot/.venv"
  echo "  Creating isolated Docker-broker Python environment..."
  "$DOCKER_BROKER_BOOTSTRAP_PYTHON" -m venv "$staged/venv"
  "$staged/venv/bin/python" -m pip install --disable-pip-version-check \
    "$staged/snapshot"
  (cd "$staged" && find snapshot venv -type f \
    -exec /usr/bin/shasum -a 256 {} + | LC_ALL=C sort > integrity.sha256)
  chmod -R a-w "$staged"
  find "$staged" -type d -exec chmod a+rx {} +
  chmod u+w "$staged"

  local previous="$DOCKER_BROKER_ROOT/.runtime-previous"
  if [ -d "$previous" ]; then
    chmod -R u+w "$previous" || return 1
    rm -rf "$previous" || return 1
  fi
  if [ -d "$DOCKER_BROKER_RUNTIME" ]; then
    chmod u+w "$DOCKER_BROKER_RUNTIME" || return 1
    if ! mv "$DOCKER_BROKER_RUNTIME" "$previous"; then
      chmod a-w "$DOCKER_BROKER_RUNTIME"
      return 1
    fi
  fi
  if ! mv "$staged" "$DOCKER_BROKER_RUNTIME"; then
    echo "  Docker-broker runtime swap failed; restoring the previous snapshot."
    if [ -d "$previous" ]; then
      mv "$previous" "$DOCKER_BROKER_RUNTIME"
      chmod a-w "$DOCKER_BROKER_RUNTIME"
    fi
    return 1
  fi
  chmod a-w "$DOCKER_BROKER_RUNTIME"
  if [ -d "$previous" ]; then
    chmod -R u+w "$previous" || return 1
    rm -rf "$previous" || return 1
  fi
  echo "  Installed integrity-isolated Docker broker at $DOCKER_BROKER_RUNTIME"
  echo "  No Docker operation or canary was run."
}

start_docker_broker() {
  if ! _docker_broker_installed; then
    echo "  Docker broker unavailable (operator has not installed it)"
    return 0
  fi
  if ! _verify_docker_broker_integrity; then
    echo "  Docker broker integrity check failed; refusing core startup"
    return 1
  fi

  local pid=""
  [ ! -f "$DOCKER_BROKER_PIDFILE" ] || pid=$(cat "$DOCKER_BROKER_PIDFILE" 2>/dev/null || true)
  if _docker_broker_pid_matches "$pid"; then
    if _docker_broker_healthy; then
      echo "  Docker broker already healthy on 127.0.0.1:$DOCKER_BROKER_PORT (pid $pid)"
      return 0
    fi
    echo "  Installed Docker broker has matching process identity but is unhealthy"
    return 1
  elif [[ "$pid" == <-> ]] && _pid_alive "$pid"; then
    echo "  Refusing live foreign Docker-broker PID identity in $DOCKER_BROKER_PIDFILE"
    return 1
  elif [ -n "$pid" ]; then
    rm -f "$DOCKER_BROKER_PIDFILE"
  fi

  umask 077
  mkdir -p "$DOCKER_BROKER_STATE" "$DOCKER_BROKER_PRIVATE/run" \
    "$DOCKER_BROKER_PRIVATE/logs" "$DOCKER_BROKER_PRIVATE/tmp" \
    "$DOCKER_BROKER_PRIVATE/home"
  chmod 700 "$DOCKER_BROKER_ROOT" "$DOCKER_BROKER_PRIVATE" \
    "$DOCKER_BROKER_STATE" "$DOCKER_BROKER_PRIVATE/run" \
    "$DOCKER_BROKER_PRIVATE/logs" "$DOCKER_BROKER_PRIVATE/tmp" \
    "$DOCKER_BROKER_PRIVATE/home"
  touch "$DOCKER_BROKER_LOG"
  chmod 600 "$DOCKER_BROKER_LOG"

  echo "  Starting optional Docker broker..."
  nohup env -i HOME="$DOCKER_BROKER_PRIVATE/home" \
    PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    TMPDIR="$DOCKER_BROKER_PRIVATE/tmp" PYTHONDONTWRITEBYTECODE=1 \
    "$DOCKER_BROKER_PYTHON" -B -m docker_broker \
    --host 127.0.0.1 --port "$DOCKER_BROKER_PORT" \
    --allowed-root "$DOCKER_BROKER_ALLOWED_ROOT" --state-directory "$DOCKER_BROKER_STATE" \
    --docker-path "$DOCKER_BROKER_DOCKER" \
    --agent-server-url "$DOCKER_BROKER_AGENT_SERVER" \
    --owner-id "$DOCKER_BROKER_OWNER" \
    --lease-seconds "$DOCKER_BROKER_LEASE_SECONDS" --allow-builds \
    >> "$DOCKER_BROKER_LOG" 2>&1 &
  pid=$!
  print -r -- "$pid" > "$DOCKER_BROKER_PIDFILE"
  disown

  local attempt
  for attempt in {1..30}; do
    if ! _docker_broker_pid_matches "$pid"; then
      echo "  Docker broker exited or changed identity; refusing core startup"
      rm -f "$DOCKER_BROKER_PIDFILE"
      return 1
    fi
    if _docker_broker_healthy; then
      echo "  Docker broker healthy on http://127.0.0.1:$DOCKER_BROKER_PORT"
      return 0
    fi
    sleep 1
  done
  echo "  Installed Docker broker failed health checks; refusing core startup"
  return 1
}

stop_docker_broker() {
  if [ ! -f "$DOCKER_BROKER_PIDFILE" ]; then
    echo "  Docker broker not running"
    return 0
  fi
  local pid
  pid=$(cat "$DOCKER_BROKER_PIDFILE" 2>/dev/null || true)
  if ! _docker_broker_pid_matches "$pid"; then
    if [[ "$pid" == <-> ]] && _pid_alive "$pid"; then
      echo "  Refusing to signal live foreign Docker-broker PID '$pid'"
      return 1
    fi
    rm -f "$DOCKER_BROKER_PIDFILE"
    echo "  Removed stale Docker-broker PID state without signaling a process"
    return 0
  fi
  kill -TERM "$pid"
  local attempt
  for attempt in {1..50}; do
    _pid_alive "$pid" || break
    sleep 0.1
  done
  if _pid_alive "$pid"; then
    if ! _docker_broker_pid_matches "$pid"; then
      echo "  Docker-broker identity changed during stop; refusing further signals"
      return 1
    fi
    kill -KILL "$pid"
  fi
  rm -f "$DOCKER_BROKER_PIDFILE"
  echo "  Docker broker (pid $pid) stopped"
}

status_docker_broker() {
  if ! _docker_broker_installed; then
    echo "  Docker brk :$DOCKER_BROKER_PORT  –  unavailable (not installed)"
    return 0
  fi
  local pid=""
  [ ! -f "$DOCKER_BROKER_PIDFILE" ] || pid=$(cat "$DOCKER_BROKER_PIDFILE" 2>/dev/null || true)
  if _docker_broker_pid_matches "$pid" && _docker_broker_healthy; then
    echo "  Docker brk :$DOCKER_BROKER_PORT  ✓  healthy (pid $pid)"
  elif [ -n "$pid" ]; then
    echo "  Docker brk :$DOCKER_BROKER_PORT  !  installed but unhealthy/identity mismatch"
    return 1
  else
    echo "  Docker brk :$DOCKER_BROKER_PORT  ✗  installed but stopped"
    return 1
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
  nohup ./.venv/bin/langgraph up --image "jasper-langgraph:current" --port "$LANGGRAPH_PORT" --wait \
    --docker-compose "$ROOT/backend/docker-compose.override.yml" \
    >> "$LOGDIR/langgraph.log" 2>&1 &
  echo $! > "$PIDDIR/langgraph.pid"
  disown

  if _wait_for_port "$LANGGRAPH_PORT" 300; then
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
  else
    _ensure_dirs
    echo "  Starting backend..."
    cd "$ROOT/backend"
    source ./.venv/bin/activate
    nohup python -m src.web_server >> "$LOGDIR/backend.log" 2>&1 &
    echo $! > "$PIDDIR/backend.pid"
    disown
  fi

  if _wait_for_backend_ready 60; then
    echo "  Backend ready on http://127.0.0.1:$BACKEND_PORT"
  else
    echo "  Backend failed readiness checks — check $LOGDIR/backend.log"
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

  # Auto-rebuild: rebuild the production bundle if required build artifacts
  # are missing or any UI source/config file is newer than the last build. This
  # lets the user (or their coding agent) edit UI code and have the next launch
  # pick up the changes automatically — no manual `pnpm build` step required.
  local needs_build=0
  local frontend_api_url="http://127.0.0.1:$LANGGRAPH_PORT"
  local frontend_assistant_id="agent"
  local frontend_docker_broker_url="http://127.0.0.1:$DOCKER_BROKER_PORT/v1/coder/confirmations"
  local frontend_build_config="api=$frontend_api_url assistant=$frontend_assistant_id docker_broker=$frontend_docker_broker_url"
  if [ ! -f ".next/BUILD_ID" ] || [ ! -f ".next/prerender-manifest.json" ]; then
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
  if [ "$(cat .next/.jasper-runtime-config 2>/dev/null || true)" != "$frontend_build_config" ]; then
    needs_build=1
  fi

  if [ "$needs_build" = "1" ]; then
    echo "  Building frontend (production)..."
    NEXT_PUBLIC_API_URL="$frontend_api_url" \
      NEXT_PUBLIC_ASSISTANT_ID="$frontend_assistant_id" \
      NEXT_PUBLIC_DOCKER_BROKER_URL="$frontend_docker_broker_url" \
      ./node_modules/.bin/next build >> "$LOGDIR/frontend-build.log" 2>&1 || {
      echo "  Frontend build failed — check $LOGDIR/frontend-build.log"
      return 1
    }
    print -r -- "$frontend_build_config" > .next/.jasper-runtime-config
  else
    echo "  Using cached build (.next/BUILD_ID up to date)"
  fi

  echo "  Starting frontend (production server)..."
  nohup ./node_modules/.bin/next start -p "$FRONTEND_PORT" >> "$LOGDIR/frontend.log" 2>&1 &
  echo $! > "$PIDDIR/frontend.pid"
  disown

  if _wait_for_port "$FRONTEND_PORT" 60; then
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

    # Both isolated host services require Agent Server first. An installed
    # service that cannot become healthy closes the whole core boundary.
    echo "── Docker broker (optional, port $DOCKER_BROKER_PORT) ──"
    if ! start_docker_broker; then
      stop_docker_broker || true
      stop_langgraph
      echo "  Core startup refused: installed Docker broker is unavailable."
      exit 1
    fi
    echo ""

    echo "── macOS host executor (optional, port $HOST_EXECUTOR_PORT) ──"
    if ! start_host_executor; then
      stop_docker_broker
      stop_langgraph
      echo "  Core startup refused: installed host executor is unavailable."
      exit 1
    fi
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

    echo "── macOS host executor ──"
    stop_host_executor

    echo "── Docker broker ──"
    stop_docker_broker

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
    status_docker_broker || true
    status_host_executor || true
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
    stop_host_executor
    stop_docker_broker
    stop_langgraph
    echo ""
    start_langgraph
    if ! start_docker_broker; then
      stop_docker_broker || true
      stop_langgraph
      echo "  Core restart refused: installed Docker broker is unavailable."
      exit 1
    fi
    if ! start_host_executor; then
      stop_docker_broker
      stop_langgraph
      echo "  Core restart refused: installed host executor is unavailable."
      exit 1
    fi
    start_backend
    start_frontend
    echo ""
    echo "Core chat services ready at http://localhost:$FRONTEND_PORT"
    ;;

  install-host-executor)
    install_host_executor
    ;;

  install-docker-broker)
    install_docker_broker
    ;;

  *)
    echo "Usage: $0 {start|stop|status|restart|restart-core|install-host-executor|install-docker-broker}"
    exit 1
    ;;
esac
