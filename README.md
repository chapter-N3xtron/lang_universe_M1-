# LangGraph Agent Chat UI + Deep Agents

A local multi-agent chat application with a Next.js UI, a LangGraph supervisor,
and a workspace-confined Deep Agents coding specialist.

## Components

- `agent-chat-ui/`: Next.js 15 / React 19 chat UI.
- `backend/src/chat_ui.py`: supervisor graph for Coding, Jasper, Research, and
  Magic Coder.
- `backend/src/coding_agent.py`: durable Deep Agents coding subgraph.
- `backend/src/secure_coding_tools.py`: approval-gated writes and allowlisted
  workspace commands.
- `backend/src/coding_persistence.py`: isolated SQLite or Postgres checkpoints.
- `backend/src/web_server.py`: local TTS, STT, model-list, session lifecycle,
  todo, and folder-picker sidecar.
- `todos.json`: project task source of truth, governed by `AGENTS.md`.

## Coding providers

The coding layer supports local Ollama, Ollama Cloud, and Hugging Face models.
Copy `backend/.env.example` to `backend/.env` and set only the providers you
intend to use. Keep credentials out of source and chat output.

Model IDs use these prefixes:

- `ollama/qwen3.5:27b`
- `ollama-cloud/qwen3.5:397b`
- `huggingface/org/model`

`CODING_MODEL` selects the default. `CODING_MODELS` is an optional comma-separated
list shown by the UI. Read-only mode is the default; mutation tools are exposed
only in approval mode and every mutation pauses for human review.

## Run

Backend graph:

```bash
./start_image_pipeline.sh start
```

The application UI requires the canonical Docker-backed Agent Server started by this
launcher. It rejects `langgraph dev` and other unverified runtimes so an in-memory
server on port 8123 cannot silently present a different thread catalog. Studio-only
development servers must use a separate port and are not accepted by the application
UI.

Sidecar:

```bash
cd backend
UV_CACHE_DIR=/tmp/deep-agent-uv-cache uv run uvicorn src.web_server:app --host 127.0.0.1 --port 8000
```

UI:

```bash
cd agent-chat-ui
pnpm install
pnpm dev
```

## Verification

```bash
cd backend
UV_CACHE_DIR=/tmp/deep-agent-uv-cache uv run pytest -q

cd ../agent-chat-ui
./node_modules/.bin/tsc --noEmit
./node_modules/.bin/next build
./node_modules/.bin/playwright test tests/ui-controls.spec.ts tests/tts.spec.ts
```

Security, persistence, and migration evidence are documented in
`backend/SECURITY.md`, `backend/PERSISTENCE.md`, and `backend/PARITY.md`.
