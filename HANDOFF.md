# Handoff Notes — Multi-Agent Supervisor System

## Architecture

- **Frontend:** `agent-chat-ui/` (Next.js, port 3001). Connects to LangGraph API via SDK.
- **Backend:** `backend/` (Python, `langgraph dev` on port 8123). Manual supervisor graph.
- **Sidecar:** FastAPI on port 8000 for TTS/STT/models list.
- **Legacy:** `frontend.legacy/` is archived. Do not use.

---

# Original Plan (Phases 0-10)

### Phase 0 — Cleanup
Clean up repo structure: fix `.env` config, remove empty root dirs, delete dead code (`backend/src/tts.py`), update `langgraph.json` to Python 3.12, remove stale PID files. Archive or delete legacy `frontend/` directories.

### Phase 1 — Manual Supervisor Graph
Build a manual supervisor graph in `backend/src/chat_ui.py` with:
- State: `messages`, `workspace`, `target_agent`, `mode`, `model`, `opencode_session_id`, `active_agent`, `handoff_history`, `decision_log`, `pending_approval`, `pending_agent`
- Supervisor node that routes by `target_agent` or LLM decision (→ approval node)
- Approval node that calls `interrupt()` before handoff
- Static edges returning control to supervisor after each specialist
- Tests for supervisor routing, interrupts, and memory

### Phase 2 — Connect Agent Chat UI
Extend `agent-chat-ui` state types with supervisor fields, pass `target_agent`/`workspace`/`model` from UI, verify end-to-end via LangGraph SDK. Add Playwright tests.

### Phase 3 — Human-in-the-loop
Wire the approval node with `interrupt()` and `Command(resume=...)` pattern. Handle test isolation: `target_agent` bypasses approval, clear `target_agent` after routing to prevent infinite loops.

### Phase 4 — Jasper compiled sub-graph
Create compiled sub-graph `backend/src/jasper_agent.py` for file-system agent. 3 tests (message, error, history).

### Phase 5 — Magic Coder compiled sub-graph
Create compiled sub-graph `backend/src/magic_coder_graph.py` wrapping `run_magic_coder()`. 3 tests. Handle test isolation bug (stale `src.__dict__` after `_clear_src_modules()`).

### Phase 6 — Wire TTS/STT
Integrate TTS (Kyutai) and STT (faster-whisper) into the UI: `useTTS.ts` for speaking AI messages, `useSTT.ts` for push-to-talk microphone input. Wire into `Thread` component.

### Phase 7 — Add selectors to Agent Chat UI
Agent/model/workspace selector controls in the UI header.

### Phase 8 — Visual dashboard
Agent badges, handoff cards, activity visualization.

### Phase 9 — OpenCode streaming
Stream OpenCode sub-graph output. Deferred — highest risk.

### Phase 10 — Update `start_image_pipeline.sh`
Update deployment/startup script for current architecture.

---

# Current Status

### Phase 0 — ✅ Complete
- `backend/.env` line 13 fixed (`HF_TOKEN=...`)
- Empty root dirs removed (`app/`, `components/`, `hooks/`, `lib/`, `public/`, `scripts/`)
- `backend/src/tts.py` deleted (staged, not committed)
- `backend/langgraph.json` updated to Python 3.12
- Stale PID files removed from `.pids/`
- Agent Chat UI customizations (dark theme, TTS hook, Volume2 button) — uncommitted, `agent-chat-ui/` is untracked
- `frontend/` deleted (staged), `frontend.legacy/` archived (untracked) — uncommitted

### Phase 1 — ✅ Complete
- `backend/src/chat_ui.py` rewritten with supervisor + approval node per plan
- `backend/tests/test_supervisor.py` — 5 tests passing
- `backend/tests/test_interrupts.py` — 3 tests passing

### Phase 2 — ✅ Complete
- `agent-chat-ui/src/providers/Stream.tsx` — StateType extended with all supervisor fields
- `agent-chat-ui/src/components/thread/index.tsx` — `stream.submit()` passes `target_agent`, `workspace`, `model`
- `langgraph dev` verified end-to-end via Python SDK client
- `agent-chat-ui/tests/phase2.spec.ts` — 2 Playwright tests exist but currently failing (need langgraph dev running)
- `agent-chat-ui/playwright.config.ts` — Playwright config added

### Phase 3 — ✅ Complete
- Approval node with `interrupt()` added to graph
- 3 interrupt tests pass; supervisor + memory tests adapted
- **Fix applied:** `target_agent` bypasses approval node (no interrupt)
- **Fix applied:** supervisor clears `target_agent` after routing (`"target_agent": ""` in Command update)

### Phase 4 — ✅ Complete
- `backend/src/jasper_agent.py` — compiled sub-graph for file-system agent
- `backend/tests/test_jasper_agent.py` — 3 tests passing

### Phase 5 — ✅ Complete
- `backend/src/magic_coder_graph.py` — compiled sub-graph wrapping `run_magic_coder()`
- `backend/tests/test_magic_coder_graph.py` — 3 tests passing
- **Known issue:** Test isolation bug — after `_clear_src_modules()`, `from src import opencode_agent` returns stale module from `src.__dict__`. Use `importlib.import_module("src.opencode_agent")` instead.

### Phase 6 — ✅ Complete (agent selector pulled forward as testing dependency)
- `agent-chat-ui/src/hooks/useTTS.ts` — wired, Volume2 button speaks AI messages aloud. Chat responses work end-to-end after the Phase 6.2 supervisor/approval fix.
- `agent-chat-ui/src/hooks/useSTT.ts` — **REWRITTEN** to fix STT 500 bug (see bugfix notes below)
- `agent-chat-ui/src/components/thread/index.tsx` — `useTTS` + `useSTT` imported, `onSpeak` passed to `AssistantMessage`, mic button with push-to-talk
- **Agent selector dropdown** (originally Phase 7, pulled forward): `agent-chat-ui/src/components/ui/select.tsx` — shadcn-style Select primitive (`@radix-ui/react-select`). Wired `<Select>` in form footer with options: Auto, Jasper, OpenCode, Research, Magic Coder. `stream.submit()` passes `target_agent` → supervisor bypasses LLM decision and approval, routes directly to specialist.
- Voice layer tested: TTS stream (HTTP 200), STT endpoint (HTTP 200), end-to-end browser recording → transcript (HTTP 200)
- Frontend build: passes

**33/33 backend tests, 9/9 Playwright tests passing.**

**Known issue — UI is slow:**
- Loading/rendering feels sluggish. Likely causes: (1) stale `.next` cache requiring `rm -rf .next && pnpm dev`, (2) leftover process on port 3001 causing EADDRINUSE / contention, (3) 8 large local ollama models consuming RAM/VRAM.
- Recommended fix: `kill $(lsof -t -i:3001)`, `rm -rf .next`, `pnpm dev --port 3001`.
- Also: the FastAPI sidecar (port 8000) and LangGraph dev server (port 8123) both load ollama model metadata on every `/api/models` request — if lag coincides with model list usage, consider caching.

**Theme decisions:**
- `next-themes@0.4.6` declared in `package.json` but not imported anywhere
- Defaults to light mode. `sonner.tsx` hardcoded `theme="light"`.
- No `ThemeProvider` in `layout.tsx`, no `useTheme()` in components, no theme toggle

### Bugfix: STT 500 (Phase 6, discovered during implementation)
**Root cause:** Race condition in `useSTT.ts` — `getUserMedia()` is async (shows browser permission prompt on first call), but `onPointerUp` fired before the promise resolved. Recorder was stopped before `start()` ran, emitting only a 36-byte EBML container header with no audio data. ffmpeg then failed with "End of file".

**Fix applied:**
- Cached `MediaStream` after first `getUserMedia()` grant (`cachedStreamRef`) — subsequent presses are synchronous
- Removed `stopRequestedRef` race machinery — `stopRecording` checks `recorder.state !== "recording"` and bails
- `recorder.start(1000)` — 1-second timeslice for reliable chunk accumulation
- Added `[STT]` console diagnostics: `stop {chunks, blobSize, blobType}`, `blob too small`, `MediaRecorder error`, `recorder.stop() threw`
- Added `isAcquiring` state (exposed to UI, not yet wired)
- Guarded `startRecording` against double-start; wrapped `recorder.stop()` in try/catch
- Added `recorder.onerror` handler

**Push-to-talk confirmed working:** hold Voice → speak → release → transcript appears in input. First press grants mic permission; subsequent presses are synchronous.

### Bugfix: Stale `.next` cache (Phase 6, discovered during implementation)
**Root cause:** On-disk JS chunks were content-hashed (`main-app-cb556a22fbadacc3.js`) but SSR HTML referenced un-hashed dev paths (`main-app.js`) → 404 → `__webpack_modules__[id]` undefined → `TypeError: Cannot read properties of undefined (reading 'call')`. Not the "known Next.js webpack RSC bug" — just a stale cache.

**Fix applied:** `rm -rf agent-chat-ui/.next && pnpm dev --port 3001`

**If the error recurs:** check whether `/_next/static/chunks/main-app.js` returns 200 or 404. 404 = stale cache. 200 = real bundler issue.

### STT Debug Endpoint (added during implementation)
`POST /api/stt/debug` — returns `content_type`, `filename`, `headers`, `input_size`, `input_first_bytes` (hex), `input_last_bytes` (hex), `ffmpeg_version`, `ffmpeg_returncode`, `ffmpeg_stdout_size`, `ffmpeg_stderr`, and on success: `decoded_shape`/`decoded_min`/`decoded_max`/`decoded_mean`.

### Phase 7 — ✅ Complete (2026-07-26)
- Model selector dropdown: **dynamic fetch from `GET /api/models`** on mount — shows all available models from OpenCode Cloud plus every local Ollama model. Replaced the old hardcoded 7-model list that didn't match actual installed models (8 local models were missing).
- Repo selector button: opens native macOS folder picker via `window.showDirectoryPicker()`, displays selected folder name, stored in `selectedWorkspace`. Added feature detection + error toast for unsupported browsers (Firefox/Safari).
- **Bugfix 1:** `backend/src/agent_utils.py` — `get_user_query()` and `get_conversation_history()` only checked `m.get("role")` but LangGraph SDK messages use `"type"` (e.g. `"type": "human"`). Added `_msg_role()` helper that normalises both formats. This unblocked OpenCode and Research agents.
- **Bugfix 2:** `backend/src/chat_ui.py` — `_is_approved()` only checked `resume_value.get("type") == "approve"`, but the LangGraph SDK frontend sends `{decisions: [{type: "approve"}]}` (wrapped in a `decisions` key). Added unwrap logic for the `decisions` array. This was the root cause of approvals being silently treated as rejections — Auto → Jasper handoff was broken.
- **Frontend tests:** `tests/ui-controls.spec.ts` — 7 Playwright tests for agent/model/repo selectors, switch, upload, voice, send button.
- **Backend tests:** `tests/test_agent_utils.py` — 12 tests for `get_user_query` / `get_conversation_history` with mixed type/role formats.

### Phase 6.2 — ✅ DONE (2026-07-26) — Supervisor + approval fixed (unblocked chat responses)
- `backend/src/chat_ui.py` — `supervisor_node`: "done" and unrecognized agent names now fall back to jasper instead of ending the graph with no response. Every user message is guaranteed a specialist response.
- `backend/src/chat_ui.py` — `supervisor_node`: **re-routing loop fixed** — if the last message is from an assistant (specialist already responded), the supervisor ends the turn instead of re-routing and creating duplicate approval interrupts. This was the root cause of the 2 duplicate approval requests + duplicate React key errors.
- `backend/src/chat_ui.py` — `approval_node`: rewritten to emit the AgentInbox HITL schema (`action_requests: [{name, args, description}], review_configs: [{action_name, allowed_decisions: ["approve", "reject"]}]`) so the UI's `isAgentInboxInterruptSchema` check passes and Approve/Reject buttons render.
- `backend/src/chat_ui.py` — added `_is_approved(resume_value)` helper to handle both the new HITL Decision dict (`{"type": "approve"}`) and the legacy boolean resume (`True`/`False`) for backward compat with tests.
- `backend/tests/test_interrupts.py` — updated `test_interrupt_fires_on_handoff` to assert new schema; added `test_interrupt_approval_proceeds_via_decision_dict`, `test_interrupt_rejection_stops_via_decision_dict`, `test_supervisor_fallback_to_jasper_on_done`, `test_supervisor_fallback_on_unrecognized_agent`.
- `backend/tests/test_supervisor.py` — renamed `test_supervisor_ends_turn` → `test_supervisor_done_falls_back_to_jasper`; updated `test_supervisor_routes_to_research` to assert message production instead of `active_agent` persistence (supervisor now clears `active_agent` when ending turn).
- **21/21 backend tests pass.** Frontend typecheck passes. End-to-end verified via langgraph dev API.

### Phase 6.3 — ✅ DONE (2026-07-26) — UI fixes (push-to-talk, TTS button, duplicate keys)
- `agent-chat-ui/src/hooks/useSTT.ts` — re-added `stopRequestedRef` to handle the race where `onMouseUp` fires while `getUserMedia` is still acquiring. `stopRecording` now sets `stopRequestedRef = true` when `isAcquiring`, and `startRecording` checks it after the stream resolves — bails without starting the recorder if stop was requested. Eliminates orphan recorders and empty-blob second presses.
- `agent-chat-ui/src/components/thread/index.tsx` — mic button: switched from `onPointerDown`/`onPointerUp` (with `e.preventDefault()` that blocked events) to `onMouseDown`/`onMouseUp`/`onMouseLeave` for reliable push-to-talk.
- `agent-chat-ui/src/components/thread/index.tsx` — message keys: changed `key={message.id || ...}` to `key={${message.id || message.type}-${index}}` to prevent duplicate React key errors when the graph re-emits messages.
- `agent-chat-ui/src/components/thread/index.tsx` — `onSpeak` prop: removed the `message.type === "ai"` conditional so the speak-aloud button is always available for non-human messages (the backend's assistant messages may not carry `type: "ai"`).
- `agent-chat-ui/src/components/thread/messages/ai.tsx` — CommandBar visibility: changed `opacity-0 group-hover:opacity-100` to `opacity-100` so the Volume2 (speak-aloud) button is always visible on AI messages, not hidden until hover.

### Phase 8 — ⬜ Not Started
### Phase 9 — ⬜ Not Started (deferred, highest risk)
### Phase 10 — ⬜ Not Started

---

## Testing Pattern

### Supervisor tests (test_supervisor.py, test_interrupts.py, test_memory.py)

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

### Sub-graph tests (test_jasper_agent.py, test_magic_coder_graph.py)

Sub-graphs are already compiled — do NOT call `.compile()` on them:

```python
_clear_src_modules()
with patch("src.magic_coder_graph.run_magic_coder") as mock_run:
    mock_run.return_value = {"success": True, "text": "...", "error": None}
    app_module = importlib.import_module("src.magic_coder_graph")
    app = app_module.create_magic_coder_graph()
    result = app.invoke({...})
```

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

# Start FastAPI sidecar (TTS/STT — has dead code, see cleanup section)
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
| `backend/src/agent_utils.py` | Shared `get_user_query()` and `get_conversation_history()` |
| `backend/src/stt.py` | faster-whisper transcription |
| `backend/src/kyutai_tts.py` | Kyutai TTS 1.6B engine |
| `backend/src/web_server.py` | FastAPI sidecar (TTS/STT). Has dead code — strip per cleanup section. |
| `backend/langgraph.json` | Graph entry point for `langgraph dev` |
| `agent-chat-ui/src/providers/Stream.tsx` | StateType, useStream config |
| `agent-chat-ui/src/components/thread/index.tsx` | Main Thread component, submit() |
| `agent-chat-ui/src/hooks/useTTS.ts` | TTS hook (wired, speaks AI messages aloud) |
| `agent-chat-ui/src/hooks/useSTT.ts` | STT hook (hold-to-record mic button in input area) |
| `agent-chat-ui/.env` | `NEXT_PUBLIC_API_URL=http://127.0.0.1:8123` (exists) |

## Sidecar Cleanup Needed

`backend/src/web_server.py` has dead code that should be stripped. The sidecar is essential (browser can't call Python TTS/STT directly), but only 3 endpoints are actually used:

| Dead Code | Why |
|---|---|
| `lifespan` graph compilation | `langgraph dev` handles this on 8123 |
| `ChatMessage`, `ChatRequest`, `ChatResponse` models | Only used by old `/api/chat` |
| `_has_checkpoint`, `_build_invocation_input`, `_log_request` helpers | Only used by old `/api/chat` |
| `POST /api/chat` | Agent Chat UI uses LangGraph SDK on 8123 |
| `POST /api/tts` (non-streaming) | Frontend only uses `/api/tts/stream` |
| `POST /api/tts/voices/clone` | Not used by frontend |
| `GET /api/fs/*` | Not used by frontend |
| `GET /api/models` | Not used by frontend |
| `POST /api/jobs`, `GET /api/jobs/{id}` | Not used by frontend |
| Imports: `create_chat_ui`, `jobs`, `ollama_client` | Only used by dead endpoints |

**What should remain:**
- `POST /api/tts/stream` — Kyutai TTS streaming
- `GET /api/tts/voices` — list available voices
- `POST /api/stt` — faster-whisper transcription
- `GET /health` — health check
- CORS middleware
- Imports: `transcribe` from `src.stt`, `get_tts_engine` from `src.kyutai_tts`

## Next Steps (in order)

1. **Phase 8** — Visual dashboard (agent badges, handoff cards)
2. **Phase 8** — Visual dashboard (agent badges, handoff cards)
3. **Phase 9** — OpenCode streaming (deferred, highest risk)
4. **Phase 10** — Update `start_image_pipeline.sh`
5. **Sidecar cleanup** — Strip dead code from `web_server.py`

---

# Appendix: Steelman Analysis — STT 500 Bug (2026-07-26)

### Methodology

Steelmanning is the rhetorical method of addressing the **strongest form** of an argument, not the weakest. It rests on four pillars:

1. **Charity** — Interpret every hypothesis in its most reasonable light; assume coherence, not confusion.
2. **Accuracy** — Preserve the core commitments of each hypothesis without altering the stakes.
3. **Strengthening** — Actively search for the best evidence that could support each view, including evidence the original proponent missed.
4. **Verification** — Test each hypothesis empirically until it can either be confidently disproven or remains as the most parsimonious explanation.

This analysis was conducted by:
- Reading the FULL source code of every file in the data path: `agent-chat-ui/src/hooks/useSTT.ts` → `backend/src/web_server.py` (endpoint) → `backend/src/stt.py` (decoding)
- Reading the source code of all dependencies: Starlette's `UploadFile` (datastructures.py), Starlette's multipart parser (formparsers.py), python-multipart internals
- Reading all relevant documentation: FastAPI UploadFile docs, faster-whisper API reference, Next.js GitHub issues, ffmpeg man pages, MediaRecorder W3C spec
- **Running live shell commands** against ffmpeg 8.1, the running FastAPI backend, Python SpooledTemporaryFile, and the multipart parser code path

### Hypothesis H1: `audio.file.read()` returns empty bytes

**Strongest form**: The `SpooledTemporaryFile` underlying `UploadFile.file` has its position at the end after the multipart parser writes data. Calling `.read()` from the end returns `b""`, so `transcribe(b"")` receives empty bytes, ffmpeg fails on an empty file, and the endpoint returns 500.

**Evidence gathered in support**:
- Tested Python `SpooledTemporaryFile`: after `write(data)`, `f.read()` from current position (which is at end) returns 0 bytes. Must call `f.seek(0)` first.
- Starlette's `UploadFile.__init__` creates `tempfile.SpooledTemporaryFile(max_size=1024*1024)` and assigns it to `self.file` — no seek occurs during init.
- Starlette's `UploadFile.write()` calls `self.file.write(data)` — this moves the position to end.
- FastAPI's `def` endpoints run in a thread pool with the sync `file.file` — no `seek(0)` in FastAPI's wrapper.

**Evidence gathered against (stronger)**:
- Searched Starlette's formparsers.py source code — **found `await part.file.seek(0)`** called after all file data is written. The multipart parser explicitly resets position to 0 before the handler runs.
- Empirically tested: `curl -s -X POST http://127.0.0.1:8000/api/stt -F "audio=@/tmp/test_stt_audio.webm"` returned `{"transcript":"You"}` — HTTP 200 with valid transcription. The full pipeline works for valid input.
- FastAPI's documentation explicitly says `contents = myfile.file.read()` works in `def` endpoints, which is consistent with the parser's seek(0) behavior.

**Verdict**: CONFIDENTLY DISPROVEN. Confidence: 0.99. Starlette's multipart parser calls `seek(0)` after writing. The endpoint demonstrably works for valid WebM files.

### Hypothesis H2: `ffmpeg -seekable 0` is not recognized

**Strongest form**: The `-seekable` option is a Matroska demuxer private AVOption, not a global ffmpeg option. ffmpeg 8.1 on macOS (Homebrew build) might not register it in the generic option table, causing ffmpeg to immediately fail with "unrecognized option" and print version/help to stderr before exit code 1. This would explain the `ffmpeg version 8.1 ...` error message.

**Evidence gathered in support**:
- `-seekable` IS a private demuxer option, not a generic option. It's only meaningful for the Matroska/WebM demuxer.
- The error message reported by the user included `ffmpeg version 8.1 ...` — typical of ffmpeg's help/version output when an option is not recognized.
- curl-generated WebM succeeds but browser WebM fails — difference in file format could change which options fire.

**Evidence gathered against (stronger)**:
- Ran `ffmpeg -nostdin -loglevel error -seekable 0 -f webm -i /dev/null -f s16le -ac 1 -ar 16000 - 2>&1` — output was `EBML header parsing failed`, NOT "unrecognized option". The option IS recognized.
- Tested with option at different positions: `-seekable 0` before `-f webm`, after `-f webm`, and the flag removed entirely — all produce the same `EBML header parsing failed` for empty input. No difference in behavior.
- Tested with valid ffmpeg-generated WebM: `ffmpeg -seekable 0 -f webm -i valid.webm ...` — exit code 0, produces 16000 bytes PCM. The option works correctly for both truncated and non-truncated WebM.
- ffmpeg 8.1 Homebrew build includes `--enable-libopus` and full Matroska support.
- With `-loglevel error`, version string never appears in stderr for any error condition tested.

**Verdict**: CONFIDENTLY DISPROVEN. Confidence: 0.95. All ffmpeg options are recognized and function correctly. The version string in the earlier error report was from a previous code revision without `-loglevel error`.

### Hypothesis H3: `ffmpeg version 8.1 ...` is the current error

**Strongest form**: The error message `STT failed (500): ffmpeg failed: ffmpeg version 8.1 ...` is what the server currently returns. Therefore ffmpeg's stderr contains the version string, which means `-loglevel error` is either not working or is being overridden.

**Evidence gathered in support**:
- The user explicitly reported this error message.
- Stderr captures show `err.decode(errors='replace')`.

**Evidence gathered against (stronger)**:
- Ran ffmpeg with `-loglevel error` against empty files, nonexistent files, and valid files — version string NEVER appears in stderr output. The `-loglevel error` flag is verified to suppress the banner.
- The current `stt.py` code (all versions) has `-loglevel error` in the argument list.
- Ran `/opt/homebrew/bin/ffmpeg -version 2>&1` — confirmed the exact version string: `ffmpeg version 8.1 Copyright (c) 2000-2026 the FFmpeg developers`. This matches the reported error format.
- The reported error was from an earlier code iteration (PyAV → first ffmpeg iteration) that did NOT have `-loglevel error` in the command.
- Backend log only shows "500 Internal Server Error" without the detail message — the actual current error message has never been observed.

**Verdict**: CONFIDENTLY DISPROVEN for current code. Confidence: 0.99. The version-string error was from a previous code revision. Current code suppresses the version banner.

### Hypothesis H4: TypeError is from `next-themes`

**Strongest form**: The `TypeError: Cannot read properties of undefined (reading 'call')` error is caused by `next-themes@0.4.6`'s `ThemeProvider` or `useTheme` hook being incompatible with React 19 / Next.js 15.5.21. Removing all next-themes imports should fix it.

**Evidence gathered in support**:
- The error appears in the Next.js dev server output after adding theme functionality.
- `next-themes@0.4.6` is declared in `package.json` and installed in `node_modules/.pnpm/`.
- The `useTheme()` hook internally calls React context APIs that might change between React versions.

**Evidence gathered against (stronger)**:
- Searched the entire `agent-chat-ui/src/` directory for `useTheme`, `ThemeProvider`, `next-themes` — **zero references found**. All previous imports were removed.
- `sonner.tsx` has hardcoded `theme="light"` with no next-themes import.
- Researched this error on GitHub/Stack Overflow — it is a **well-known Next.js/Webpack RSC bundler bug** across versions 13, 14, and 15 (GitHub issues #49330, #70703, #78122, #61995, #49845).
- Root cause: `__webpack_modules__[moduleId]` is undefined when webpack tries to call `f[e].call(n.exports, ...)` in its module loader. This happens when stale JS chunks are served after a code change or deployment, or during HMR glitches.
- The error's stack trace points to webpack's internal runtime, not to any application component.
- Error frequency correlates with HMR cycles, not with theme-related interactions.

**Verdict**: DISPROVEN (next-themes cause). Actual root cause was a stale `.next` build cache — on-disk chunks were content-hashed but SSR HTML referenced un-hashed dev paths, producing 404s that caused `__webpack_modules__[id]` undefined → `.call()` TypeError. Fixed by `rm -rf .next && pnpm dev`. See bugfix notes in Current Status.

### Hypothesis H5: Error is in LangGraph supervisor graph

**Strongest form**: The STT 500 is caused by a bug in the LangGraph supervisor graph, interrupt pattern, or subgraph wrapper that somehow propagates to the sidecar.

**Evidence gathered in support**:
- The `web_server.py` has a `lifespan` handler that compiles the LangGraph app with `SqliteSaver`.
- The `/api/stt` endpoint imports `transcribe` from `src.stt`, which is part of the same Python package as the LangGraph agents.
- Import errors or module conflicts in `src/` could theoretically affect the STT endpoint.

**Evidence gathered against (stronger)**:
- STT is a standalone REST endpoint on the FastAPI sidecar (port 8000), completely independent of the LangGraph graph (port 8123).
- The STT endpoint does not call any LangGraph code — it only calls `stt.transcribe()` and `faster_whisper`.
- 17/17 backend tests pass, including tests that import and use all the same modules.
- The STT endpoint's error is specifically from ffmpeg subprocess failure, not from any Python import or graph invocation error.
- The backend log shows the error occurs during `/api/stt` processing, before any graph interaction.

**Verdict**: CONFIDENTLY DISPROVEN. Confidence: 0.99. The STT endpoint is fully independent from the LangGraph graph.

### Hypothesis H6 (DISPROVEN): Browser WebM not decodable by ffmpeg 8.1

**Strongest form**: Chrome's `MediaRecorder` produces Opus-in-WebM with specific Matroska elements (ClusterTimecode, DiscardPadding, `IsTruncated=1`, no Duration, no Cues) that ffmpeg 8.1 on macOS cannot decode even with `-seekable 0 -f webm`. The actual error (suppressed by `-loglevel error`) is `EBML header parsing failed`, `Invalid data found when processing input`, or similar.

**Evidence gathered in support**:
- Browser `MediaRecorder` WebM is known to have `IsTruncated=1`, no `Duration`, no `Cues` (per W3C MediaCapture Record Issue #119, blog.addpipe.com).
- The standard community fix for truncated WebM is `-seekable 0`, but it was designed for video WebM with VP8/VP9, not for Opus-only audio WebM.
- ffmpeg-generated truncated WebM decodes fine (exit 0, 16000 bytes PCM), but Chrome's output has different encoder metadata, ClusterTimebase, and Segment structure.
- Chrome sets `Writing application: Chrome`, while ffmpeg sets `Writing application: Lavf`. Different muxers produce different internal structure.
- The Opus-in-WebM spec requires `DiscardPadding` element in the first BlockGroup to handle Opus pre-skip — Chrome includes this but ffmpeg might handle it differently in `-seekable 0` mode.
- `-seekable 0` tells the Matroska demuxer to NOT seek around the file, which means it reads sequentially. If the first Cluster contains only Opus pre-skip data (due to DiscardPadding), sequential read might produce an empty/zero-length decoded buffer.

**Evidence gathered against**:
- `-seekable 0` specifically addresses truncated/live WebM by disabling seeking — this is the exact fix needed.
- The option worked for ffmpeg-generated truncated WebM in testing.
- Cannot confirm without inspecting actual browser blob bytes. All testing used synthetic ffmpeg output, not real browser recordings.
- The `decoded_min`, `decoded_max`, `decoded_mean` of the ffmpeg-generated test were all 0.0 (silence from `anullsrc`), so we didn't actually test with real audio content.

**Verdict**: DISPROVEN. The browser never sent valid WebM audio — the 36-byte file contained only the EBML header with no Clusters. ffmpeg 8.1 decodes valid browser WebM fine; the bug was upstream in `useSTT.ts`. See bugfix notes in Current Status.

### Hypothesis H7 (CONFIRMED): STT receives empty or corrupted bytes

**Strongest form**: Due to a browser-side issue (permissions, MediaRecorder bug, race condition, or blob corruption), the actual bytes received by the FastAPI endpoint are empty or corrupted (not a valid WebM file). The ffmpeg subprocess then fails because it receives invalid input.

**Evidence gathered in support**:
- `useSTT.ts` creates the blob from `chunksRef.current` via `new Blob(chunksRef.current, { type: recorder.mimeType })`. If `ondataavailable` fires in an unexpected order, `chunksRef.current` might be empty or contain partial data.
- `onstop` is set twice (once in `startRecording`, once in `stopRecording`) — both the same handler, but an edge case could cause the chunk array to be cleared before the blob is created.
- The `stopRequestedRef` pattern handles the race where `stopRecording` is called before `startRecording` completes — but if `recorder.stop()` is called before any data is captured, the blob will be empty.
- The `blob.size < 100` guard skips processing for small blobs, but does not log or report the skip.

**Evidence gathered against**:
- `blob.size` check prevents processing of truly empty recordings.
- `ondataavailable` fires before `onstop` per the MediaRecorder spec — data should be available.
- The race condition with `stopRequestedRef` is handled: if `stop()` is called before `start()` completes, the recorder starts and immediately stops, which SHOULD produce at least some data.
- The browser console would show errors if `getUserMedia` fails.

**Verdict**: CONFIRMED. Browser sent a 36-byte file = just the EBML header, no audio data. Root cause was the `getUserMedia()` async race with `onPointerUp`, not a MediaRecorder data-handling bug. Fixed by caching the granted `MediaStream` so subsequent presses are synchronous. See bugfix notes in Current Status.

### Summary of Empirical Tests Run

| Test | Target | Result | Date |
|------|--------|--------|------|
| `python3 -c "import tempfile; ..."` | SpooledTemporaryFile position after write | Position at end. read() returns b"". | 2026-07-26 |
| grep starlette/formparsers.py | seek(0) in multipart parser | Found `await part.file.seek(0)` | 2026-07-26 |
| curl POST /api/stt with ffmpeg WebM | End-to-end pipeline | HTTP 200, `{"transcript":"You"}` | 2026-07-26 |
| curl POST /api/stt/debug with valid WebM | Debug endpoint | Returncode 0, 16000 bytes PCM | 2026-07-26 |
| curl POST /api/stt/debug with empty file | Debug endpoint | Returncode 183, "EBML header parsing failed" | 2026-07-26 |
| ffmpeg -seekable 0 -f webm -i /dev/null | Option recognition | No "unrecognized option" error | 2026-07-26 |
| ffmpeg (no flags) -i /dev/null | Baseline comparison | Same error (EBML), no version string | 2026-07-26 |
| ffmpeg empty file detection | Empty vs nonexistent | Empty: exit 183. Nonexistent: exit 254 | 2026-07-26 |
| ffmpeg option ordering (4 positions) | Option parsing sensitivity | All 4 positions produce same output | 2026-07-26 |
| ffmpeg truncated WebM decode | -seekable 0 effectiveness | Exit 0, 16000 bytes PCM decoded | 2026-07-26 |
| Read Starlette UploadFile source | Byte flow verification | Confirmed seek(0) in formparsers.py | 2026-07-26 |
| Grep agent-chat-ui/src for next-themes | TypeError source | Zero references found | 2026-07-26 |
| Web search TypeError + Next.js | Known bug check | Confirmed #49330, #70703, #78122 | 2026-07-26 |
| Read LangGraph new docs (docs.langchain.com) | Architecture verification | Confirmed supervisor/subgraph/interrupt patterns correct | 2026-07-26 |

### Critical Gaps (all closed)

These gaps were resolved by testing against a real browser recording:

1. ~~**Never seen the actual CURRENT error message**~~ — **SEEN:** `ffmpeg failed: [in#0 @ 0x145613880] 0x00 at pos 36 (0x24) invalid as first byte of an EBML number / Error opening input: End of file`. The version-string error was indeed from an earlier code revision.
2. ~~**Never captured a real browser blob**~~ — **CAPTURED:** 36 bytes, just the EBML header (`1a45dfa3...`), no audio data. Confirmed H7.
3. ~~**Never checked `UploadFile.content_type` from a real browser request**~~ — **VERIFIED:** `audio/webm` from Chrome. Backend pipeline handles it correctly (synthetic WebM transcribes fine).
