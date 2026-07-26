# Handoff Notes — Multi-Agent Supervisor System

## Architecture

- **Frontend:** `agent-chat-ui/` (Next.js, port 3001). Connects to LangGraph API via SDK.
- **Backend:** `backend/` (Python, `langgraph dev` on port 8123). Manual supervisor graph.
- **Sidecar:** FastAPI on port 8000 for TTS/STT/FS only. Chat endpoint removed.
- **Legacy:** `frontend.legacy/` is archived. Do not use.

## What's Done

### Phase 0 — Cleanup
- `backend/.env` line 13 fixed (`HF_TOKEN=...`)
- Empty root dirs removed (`app/`, `components/`, `hooks/`, `lib/`, `public/`, `scripts/`)
- `backend/src/tts.py` deleted (orphaned, `kyutai_tts.py` is active)
- `backend/langgraph.json` updated to Python 3.12
- Stale PID files removed from `.pids/`
- Agent Chat UI customizations committed (dark theme, TTS hook, Volume2 button)
- `frontend/` renamed to `frontend.legacy/`

### Phase 1 — Manual Supervisor Graph
- `backend/src/chat_ui.py` rewritten with supervisor + approval node
- State has: `messages`, `workspace`, `target_agent`, `mode`, `model`, `opencode_session_id`, `active_agent`, `handoff_history`, `decision_log`, `pending_approval`, `pending_agent`
- Supervisor node: routes by `target_agent` (no interrupt) or LLM decision (routes to approval node)
- Approval node: calls `interrupt()` to ask human before handoff
- After each specialist, control returns to supervisor via static edges
- Per LangGraph docs: "For each node, use either Command or static edges, not both"
- `backend/tests/test_supervisor.py` — 5 tests
- `backend/tests/test_interrupts.py` — 3 tests

### Phase 2 — Connect Agent Chat UI
- `agent-chat-ui/src/providers/Stream.tsx` — StateType extended with `active_agent`, `handoff_history`, `decision_log`, `target_agent`, `workspace`, `model`, `mode`
- `agent-chat-ui/src/components/thread/index.tsx` — `stream.submit()` passes `target_agent`, `workspace`, `model`
- `langgraph dev` verified end-to-end via Python SDK client
- `agent-chat-ui/tests/phase2.spec.ts` — 2 Playwright tests passing (smoke test + thread persistence)
- `agent-chat-ui/playwright.config.ts` — Playwright config

### Phase 3 — Human-in-the-loop (done)
### Phase 4 — Jasper compiled sub-graph (done)
### Phase 5 — Magic Coder compiled sub-graph (done)
- Approval node with `interrupt()` added to graph
- 3 interrupt tests pass; supervisor + memory tests adapted
- **Fix for tests:** `target_agent` bypasses approval node (no interrupt)
- **Fix for infinite loop:** supervisor clears `target_agent` after routing (`"target_agent": ""` in Command update)
- **Test isolation bug:** After `_clear_src_modules()`, `from src import opencode_agent` returns the stale module object from `src.__dict__` instead of importing fresh. Use `importlib.import_module("src.opencode_agent")` instead.
- 11/11 backend tests passing

## Testing Pattern

All tests follow this pattern:

```python
import sys
from unittest.mock import MagicMock, patch
from langgraph.checkpoint.memory import InMemorySaver

def _compile(app):
    return app.compile(checkpointer=InMemorySaver())

def _make_llm_response(content: str):
    mock = MagicMock()
    mock.content = content
    return mock

def _clear_src_modules():
    to_remove = [k for k in list(sys.modules) if k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]

# In each test:
_clear_src_modules()
with patch("src.llm.ChatOllama", return_value=mock_llm):
    from src.chat_ui import create_chat_ui
    app = _compile(create_chat_ui())
    # ... invoke and assert
```

Key rules:
1. Clear `sys.modules` before patching so imports are fresh
2. Patch `src.llm.ChatOllama` (the constructor), not `get_llm`
3. Import `create_chat_ui` INSIDE the `with` block
4. Compile with `InMemorySaver` for tests
5. Use `target_agent` to bypass approval node when testing routing
6. For interrupt tests, use `Command(resume=True/False)` to resume

## Running Tests

```bash
# Backend tests
cd backend && ./venv/bin/python -m pytest tests/ -v

# Frontend Playwright tests
cd agent-chat-ui && npx playwright test
```

## Running Services

```bash
# Start langgraph dev
cd backend && nohup ./venv/bin/langgraph dev --port 8123 --no-browser &

# Start Agent Chat UI
cd agent-chat-ui && pnpm dev --port 3001

# Start FastAPI sidecar (TTS/STT only)
cd backend && ./venv/bin/uvicorn src.web_server:app --port 8000
```

## Key Files

| File | Purpose |
|------|---------|
| `backend/src/chat_ui.py` | Supervisor graph with approval node |
| `backend/src/opencode_agent.py` | OpenCode sub-graph (already compiled) |
| `backend/src/research_agent.py` | Research sub-graph (already compiled) |
| `backend/src/jasper_agent.py` | Jasper compiled sub-graph (Phase 4 done) |
| `backend/src/magic_coder_agent.py` | Magic Coder agent (tools + run_magic_coder entry point) |
| `backend/src/magic_coder_graph.py` | Magic Coder compiled sub-graph (Phase 5 done) |
| `backend/src/llm.py` | LLM factory (ChatOllama) |
| `backend/src/web_server.py` | FastAPI sidecar (TTS/STT/FS only) |
| `backend/langgraph.json` | Graph entry point for `langgraph dev` |
| `agent-chat-ui/src/providers/Stream.tsx` | StateType, useStream config |
| `agent-chat-ui/src/components/thread/index.tsx` | Main Thread component, submit() |
| `agent-chat-ui/src/hooks/useTTS.ts` | TTS hook (exists, not wired) |
| `agent-chat-ui/.env` | `NEXT_PUBLIC_API_URL=http://127.0.0.1:8123` |

## Next Steps (in order)

1. **Phase 6** — Wire TTS/STT (hook exists, just needs connection)
2. **Phase 7** — Add selectors to Agent Chat UI
3. **Phase 8** — Visual dashboard (agent badges, handoff cards)
4. **Phase 9** — OpenCode streaming (deferred, highest risk)
5. **Phase 10** — Update `start_image_pipeline.sh`
