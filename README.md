# LangGraph Agent Chat UI + Deep Agents

A local multi-agent chat application with a Next.js UI, a LangGraph supervisor,
and a repository-path-confined Deep Agents coding specialist. In persisted
contracts, `workspace_id` means a durable repository binding ID, not a visual UI
workspace; Chat/Split/Visual presentation state is separate. See
`openspec/TERMINOLOGY.md` for the compatibility terminology rules.

## Components

- `agent-chat-ui/`: Next.js 15 / React 19 chat UI.
- `backend/src/chat_ui.py`: supervisor graph for Coding, Jasper, Librarian, and
  Magic Coder.
- `backend/src/coding_agent.py`: durable Deep Agents coding subgraph that sends
  repository work directly to native Custodian.
- `backend/src/custodian_backend.py`: authenticated, repository-bound Deep Agents
  filesystem bridge.
- `backend/custodian_worker.py`: native macOS filesystem and bounded-command
  boundary on port 8765.
- `backend/custodian_orchestrator.py`: native Custodian orchestrator on port 8767.
- `backend/src/coding_persistence.py`: isolated SQLite or Postgres checkpoints.
- `backend/src/web_server.py`: local text-to-speech, speech-to-text, model-list,
  session lifecycle, and todo sidecar.
- `todos.json`: project task source of truth, governed by `AGENTS.md`.

Coder has no executor or broker hop. Repository filesystem operations and typed
commands go directly through Custodian.

## Coding providers

The coding layer supports local Ollama, Ollama Cloud, and Hugging Face models.
Copy `backend/.env.example` to `backend/.env` and set only the providers you
intend to use. Keep credentials out of source and chat output.

Model IDs use these prefixes:

- `ollama/qwen3.5:27b`
- `ollama-cloud/qwen3.5:397b`
- `huggingface/org/model`

`CODING_MODEL` selects the default. `CODING_MODELS` is an optional comma-separated
list shown by the UI. The browser initially selects approval mode; read-only and
autonomous modes remain available. In approval mode, repository mutations pause for
review. Autonomous repository work remains bounded by Custodian, while deployment-
changing Compose actions require explicit approval.

## Run

The canonical launcher starts native Custodian, the Docker-backed Jasper application,
the local Plane/Temporal topology, and KopiaUI:

```bash
./bttm_lock_start.command start
```

It opens the Jasper application at `http://127.0.0.1:3002` and attempts to open
Kopia at `http://127.0.0.1:51515` in Brave. The Agent Server uses port 8123, the
speech/model sidecar uses port 8000, native Custodian uses port 8765, and the native
Custodian orchestrator uses port 8767. Plane is served locally on port 8080 and
Temporal's UI on port 8088. The application rejects `langgraph dev` and other
unverified runtimes so a separate in-memory server cannot silently present a different
thread catalog.

Starting this stack may build or recreate containers and must be an intentional
operator action. Kopia is a native macOS application rather than a Docker container;
its local web server must already be configured and running before its Brave page is
available.

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
