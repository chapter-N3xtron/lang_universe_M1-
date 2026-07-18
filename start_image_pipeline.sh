#!/bin/zsh
# Start the full image-generation pipeline:
# - ComfyUI (image renderer)
# - Ollama (local LLM host)
# - Backend FastAPI (agent /image routing)
# - Frontend Next.js dev server

set -e

echo "Starting image pipeline..."

# 1. Ollama
if ! curl -s http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Starting Ollama..."
  ollama serve &
  sleep 5
else
  echo "Ollama already running."
fi

# 2. ComfyUI
if ! curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
  echo "Starting ComfyUI..."
  cd "$HOME/fun-multi-character-chats/ComfyUI"
  if [ -f "$HOME/fun-multi-character-chats/.venv/bin/python" ]; then
    "$HOME/fun-multi-character-chats/.venv/bin/python" main.py --listen 127.0.0.1 --port 8188 --disable-xformers > /tmp/comfyui.log 2>&1 &
  else
    python3 main.py --listen 127.0.0.1 --port 8188 --disable-xformers > /tmp/comfyui.log 2>&1 &
  fi
  for i in {1..30}; do
    if curl -s http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
      break
    fi
    sleep 2
  done
else
  echo "ComfyUI already running."
fi

# 3. Backend
if ! curl -s http://127.0.0.1:8000/ >/dev/null 2>&1; then
  echo "Starting backend..."
  cd "/Volumes/Storage/LangGraph_AgentChat_ui_Opencode_CLI/backend"
  source ./venv/bin/activate
  nohup python3 -m uvicorn src.web_server:app --host 127.0.0.1 --port 8000 >/tmp/backend.log 2>&1 &
  disown
  sleep 5
else
  echo "Backend already running."
fi

# 4. Frontend
if ! curl -s http://127.0.0.1:3000 >/dev/null 2>&1; then
  echo "Starting frontend..."
  cd "/Volumes/Storage/LangGraph_AgentChat_ui_Opencode_CLI/frontend"
  nohup npm run dev >/tmp/frontend.log 2>&1 &
  disown
  sleep 5
else
  echo "Frontend already running."
fi

echo "Pipeline ready."
echo "  Frontend: http://127.0.0.1:3000"
echo "  Backend:  http://127.0.0.1:8000"
echo "  ComfyUI:  http://127.0.0.1:8188"
echo "  Ollama:   http://127.0.0.1:11434"
