#!/bin/zsh
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUNTIME_ROOT="${ROOT}-bottom-locking-runtime"
RUNTIME_BRANCH="refs/heads/stabilization/bottom-locking"
ENV_SOURCE="$ROOT/backend/.env"
RUNTIME_ENV="$RUNTIME_ROOT/backend/.env"
UI_DIR="$RUNTIME_ROOT/agent-chat-ui"
LOGDIR="$ROOT/logs"
PIDDIR="$ROOT/.pids"
UI_PORT=3002

if [ ! -e "$RUNTIME_ROOT/.git" ] || [ ! -d "$UI_DIR" ]; then
  echo "Clean bottom-locking runtime worktree not found at $RUNTIME_ROOT" >&2
  exit 1
fi

if [ ! -f "$ENV_SOURCE" ]; then
  echo "Broker-held backend environment file not found at $ENV_SOURCE" >&2
  exit 1
fi
chmod 600 "$ENV_SOURCE"
if [ -L "$RUNTIME_ENV" ]; then
  if [ "$(readlink "$RUNTIME_ENV")" != "$ENV_SOURCE" ]; then
    echo "Runtime environment symlink points to an unexpected file; refusing startup." >&2
    exit 1
  fi
elif [ -e "$RUNTIME_ENV" ]; then
  echo "Runtime environment path is not the approved symlink; refusing startup." >&2
  exit 1
else
  ln -s "$ENV_SOURCE" "$RUNTIME_ENV"
fi

if [ -n "$(git -C "$RUNTIME_ROOT" status --porcelain)" ]; then
  echo "Clean bottom-locking runtime worktree has local changes; refusing startup." >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required to install the committed backend dependencies." >&2
  exit 1
fi

mkdir -p "$LOGDIR" "$PIDDIR"
runtime_commit="$(git -C "$ROOT" rev-parse "$RUNTIME_BRANCH")"
git -C "$RUNTIME_ROOT" switch --quiet --detach "$runtime_commit"
if ! git -C "$RUNTIME_ROOT" submodule update --init --recursive --no-fetch; then
  echo "The pinned bottom-locking submodule commit is unavailable locally; refusing credentialed fetching." >&2
  exit 1
fi
if ! uv sync --frozen --extra sidecar --project "$RUNTIME_ROOT/backend" \
  >> "$LOGDIR/bottom-locking-backend-dependencies.log" 2>&1; then
  echo "Committed backend dependency sync failed; check $LOGDIR/bottom-locking-backend-dependencies.log" >&2
  exit 1
fi

rm "$RUNTIME_ENV"
: > "$RUNTIME_ENV"
chmod 600 "$RUNTIME_ENV"
if ! (cd "$RUNTIME_ROOT/backend" && \
  ./.venv/bin/langgraph build --no-pull -t jasper-langgraph:current) \
  >> "$LOGDIR/bottom-locking-langgraph-build.log" 2>&1; then
  rm -f "$RUNTIME_ENV"
  ln -s "$ENV_SOURCE" "$RUNTIME_ENV"
  echo "Committed LangGraph image build failed; check $LOGDIR/bottom-locking-langgraph-build.log" >&2
  exit 1
fi
rm -f "$RUNTIME_ENV"
ln -s "$ENV_SOURCE" "$RUNTIME_ENV"

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm is required to install the bottom-locking dependencies." >&2
  exit 1
fi
cd "$UI_DIR"
pnpm install --frozen-lockfile >> "$LOGDIR/bottom-locking-dependencies.log" 2>&1

export SIDECAR_ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001,http://localhost:3002,http://127.0.0.1:3002"

if ! "$RUNTIME_ROOT/start_image_pipeline.sh" restart-core; then
  echo "Committed bottom-locking core services did not become ready; the UI was not started." >&2
  exit 1
fi

NEXT_PUBLIC_API_URL="http://127.0.0.1:8123" \
NEXT_PUBLIC_ASSISTANT_ID="chat_ui" \
  ./node_modules/.bin/next build >> "$LOGDIR/bottom-locking-frontend-build.log" 2>&1

if [ -f "$PIDDIR/frontend.pid" ]; then
  frontend_pid="$(cat "$PIDDIR/frontend.pid")"
  if kill -0 "$frontend_pid" 2>/dev/null; then
    kill "$frontend_pid" 2>/dev/null || true
  fi
  rm -f "$PIDDIR/frontend.pid"
fi
lsof -nP -tiTCP:3001 -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true

if [ -f "$PIDDIR/bottom-locking-frontend.pid" ]; then
  bottom_pid="$(cat "$PIDDIR/bottom-locking-frontend.pid")"
  if kill -0 "$bottom_pid" 2>/dev/null; then
    kill "$bottom_pid" 2>/dev/null || true
  fi
  rm -f "$PIDDIR/bottom-locking-frontend.pid"
fi
lsof -nP -tiTCP:"$UI_PORT" -sTCP:LISTEN 2>/dev/null | xargs kill 2>/dev/null || true

nohup env \
  NEXT_PUBLIC_API_URL="http://127.0.0.1:8123" \
  NEXT_PUBLIC_ASSISTANT_ID="chat_ui" \
  ./node_modules/.bin/next start -p "$UI_PORT" \
  >> "$LOGDIR/bottom-locking-frontend.log" 2>&1 &
echo $! > "$PIDDIR/bottom-locking-frontend.pid"
disown

for _ in {1..60}; do
  if lsof -nP -tiTCP:"$UI_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    open -a "Brave Browser" "http://127.0.0.1:$UI_PORT/"
    exit 0
  fi
  sleep 1
done

echo "Bottom-locking UI failed to start; check $LOGDIR/bottom-locking-frontend.log" >&2
exit 1
