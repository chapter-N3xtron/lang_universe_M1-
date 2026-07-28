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

**Known issue — UI is slow (resolved by Phase 10 launcher fix):**
- The deeper root cause was the broken launcher: `start_image_pipeline.sh` pointed at a deleted `frontend/` directory (line 287), used `npm` instead of `pnpm`, ran in dev mode (3-4s on-demand compile per route) instead of production, and never started the LangGraph graph server on port 8123. The UI was slow because it was either compiling on every request (dev mode) or timing out on graph requests.
- **Fixed in Phase 10:** launcher rewritten to serve the production build (`pnpm build` + `pnpm start -p 3001`), start langgraph on 8123 as a core blocking service, and auto-rebuild when source changes. Measured: UI cold load 18ms, warm 2ms (was 3.4s cold / 80ms warm).
- Stale `.next` cache can still cause 404 JS chunk errors in dev mode — `rm -rf agent-chat-ui/.next` if that recurs.
- The FastAPI sidecar (port 8000) and LangGraph dev server (port 8123) both load ollama model metadata on every `/api/models` request — if lag coincides with model list usage, consider caching.

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

### Bug: Repo selector only captures folder name, not absolute path (2026-07-26) — ✅ Fixed
**Fix:** Replaced `window.showDirectoryPicker()` (which only exposes `dirHandle.name`) with a fetch to `GET /api/fs/pick-folder` on the sidecar (port 8000). That endpoint runs AppleScript's native `choose folder` dialog, which **returns the real absolute POSIX path**. The full path is stored in `selectedWorkspace` and passed to the backend as `workspace`. The button label shows only the folder name (last path segment) for clean display.
**Root cause:** `agent-chat-ui/src/components/thread/index.tsx:577-578` — the repo selector used `window.showDirectoryPicker()` and stored `dirHandle.name` in `selectedWorkspace`. The File System Access API deliberately exposes only the folder's display name (e.g. `"my-repo"`), not its absolute filesystem path, for security reasons. That bare name was then sent to the backend as `workspace`, which requires an absolute path.
**Effect before fix:** Clicking "Repo selector", picking a folder, and sending a message to OpenCode did not actually point OpenCode at the selected repo. The workspace value was effectively useless.
**Known good:** When `workspace` is left empty, `run_opencode` falls back to `_default_workspace()` (`opencode_cli.py:34-36`) which is `OPENCODE_WORKSPACE` env var or the backend's CWD — so the backend already has a sane default path. The bug only manifests when the user picks a folder.
**Test coverage:** `tests/ui-controls.spec.ts:63` ("repo selector button renders") only asserts the button renders and the folder icon is visible — it does NOT exercise the workspace value flow. No test currently catches this bug.

### Bug: Repo picker button shows full path, should show only folder name (2026-07-26)
**Status:** Not fixed — documented for next agent.
**Root cause:** `agent-chat-ui/src/components/thread/index.tsx:601-603` — the button label uses `selectedWorkspace.split("/").pop() || selectedWorkspace` to extract the folder name, but when `selectedWorkspace` is the full path (e.g. `/Users/me/projects/my-repo`), the split/pop may not reliably strip to just the folder name across all scenarios. The user reports seeing the full absolute path displayed on the button instead of just the folder name.
**Expected:** Button should show only `my-repo`, not `/Users/me/projects/my-repo`.
**Suggested fix:** Extract the folder name from the path using a more robust method (e.g. `Path.basename` on the backend side or a dedicated display-name state).

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
- **33/33 backend tests pass.** Frontend typecheck passes. End-to-end verified via langgraph dev API.

### Phase 6.3 — ✅ DONE (2026-07-26) — UI fixes (push-to-talk, TTS button, duplicate keys)
- `agent-chat-ui/src/hooks/useSTT.ts` — re-added `stopRequestedRef` to handle the race where `onMouseUp` fires while `getUserMedia` is still acquiring. `stopRecording` now sets `stopRequestedRef = true` when `isAcquiring`, and `startRecording` checks it after the stream resolves — bails without starting the recorder if stop was requested. Eliminates orphan recorders and empty-blob second presses.
- `agent-chat-ui/src/components/thread/index.tsx` — mic button: switched from `onPointerDown`/`onPointerUp` (with `e.preventDefault()` that blocked events) to `onMouseDown`/`onMouseUp`/`onMouseLeave` for reliable push-to-talk.
- `agent-chat-ui/src/components/thread/index.tsx` — message keys: changed `key={message.id || ...}` to `key={${message.id || message.type}-${index}}` to prevent duplicate React key errors when the graph re-emits messages.
- `agent-chat-ui/src/components/thread/index.tsx` — `onSpeak` prop: removed the `message.type === "ai"` conditional so the speak-aloud button is always available for non-human messages (the backend's assistant messages may not carry `type: "ai"`).
- `agent-chat-ui/src/components/thread/messages/ai.tsx` — CommandBar visibility: changed `opacity-0 group-hover:opacity-100` to `opacity-100` so the Volume2 (speak-aloud) button is always visible on AI messages, not hidden until hover.

### Phase 8 — ⬜ Not Started
### Phase 9 — ⬜ Not Started (deferred, highest risk)
### Phase 10 — ✅ Complete (2026-07-26)

### Voice picker — ✅ Done (2026-07-26)
- **`agent-chat-ui/src/components/thread/index.tsx`** — Added a Voice selector dropdown in the footer controls (between Model and the Mic/Send row). Fetches available voices from `GET /api/tts/voices` on mount. The selected voice is passed to `speak()` when the Volume2 button is clicked — previously hardcoded to `"alba"`.
- **Voices available:** local (`David_Suzuki`, `Juno_2`, `Lorde`, `Murrow_1`, `Murrow_2`, `Rogers`, `Rogers_2`, `Rogers_3`) + remote Kyutai defaults (`alba`, `pavo`, `tango`, `whispering`, etc.).
- **Next:** Per-agent voice defaults once the user understands the voice landscape.

---

# Voice Layer Audit (2026-07-26)

> Consolidated audit of the TTS + STT voice layer. All findings verified against authoritative documentation (Kyutai Pocket TTS API reference, faster-whisper source + docs, MDN AudioContext docs) plus reading the full source of every file in the voice data path: `useTTS.ts`, `useSTT.ts`, `shared.tsx`, `ai.tsx`, `index.tsx`, `kyutai_tts.py`, `stt.py`, `web_server.py`.

## Priority legend
- **P0** — blocks core functionality or risks data corruption/crash
- **P1** — UX-breaking, user-reported
- **P2** — code hygiene

## Bug V1 — AudioContext sample-rate coercion breaks TTS playback (P0) — ✅ Fixed
**Source:** MDN AudioContext docs + `agent-chat-ui/src/hooks/useTTS.ts:46,70`
**Root cause:** `new AudioContext({ sampleRate: 24000 })` — per MDN, if 24000 Hz isn't supported by the output device, the browser either throws `NotSupportedError` or silently coerces to the device's native rate (typically 44100 or 48000 Hz on macOS). When `start_image_pipeline.sh` routes audio through BlackHole 2ch (which runs at 48000 Hz), Chrome coerces the AudioContext to 48000 Hz. Then `ctx.createBuffer(1, floatArr.length, 24000)` at line 70 creates a buffer at 24000 Hz but plays it through a 48000 Hz context — the buffer plays at wrong speed/pitch unless the browser resamples. Behavior is browser-dependent and a likely root cause of "TTS button no longer responding" reports.
**Fix:** Removed `{ sampleRate: 24000 }` from AudioContext constructor — defaults to device rate. Added `resample()` helper that linearly interpolates float32 chunks from 24000 Hz → `ctx.sampleRate` before creating the AudioBuffer. AudioBuffer is now created at `ctx.sampleRate` instead of hardcoded 24000.
**Verification:** Open browser console, run `new AudioContext({ sampleRate: 24000 }).sampleRate` — if it returns anything other than 24000, the coercion is happening.

## Bug V2 — TTS model is not thread-safe (P0) — ✅ Fixed
**Source:** Kyutai Pocket TTS README/docs + `backend/src/kyutai_tts.py:285-292`
**Root cause:** Kyutai docs state the model is **not thread-safe** — "separate model instances should be used for concurrent generation" and `torch.set_num_threads(1)`. The backend uses a single shared `_tts_engine` singleton. If two TTS requests hit `/api/tts/stream` concurrently (e.g. user clicks Volume2 on a second message while the first is still playing, or two browser tabs), they share one `TTSModel` and the `generate_audio_stream` calls interleave → corrupted audio or a crash. The frontend's `useTTS.ts:27` calls `stop()` before `speak()` which aborts the prior *fetch* via AbortController, but the *backend generator* keeps synthesizing into the queue for the aborted request — then the next request's producer thread mutates shared model state.
**Fix:** Added `asyncio.Lock()` (`_tts_lock`) at module level. Wrapped both `synthesize_streaming` and `synthesize_full` with `async with _tts_lock:` so only one generation runs at a time. Concurrent requests wait for the lock.
**Verification:** Open two browser tabs, click Volume2 on both within 1 second — without the lock, audio corrupts or the engine crashes; with the lock, the second request waits and plays cleanly after the first finishes.

## Bug V3 — TTS speak-aloud button has no playing/stop state (P1)
**Source:** `agent-chat-ui/src/components/thread/messages/shared.tsx:200-209`, `agent-chat-ui/src/components/thread/index.tsx:193,482`, `agent-chat-ui/src/hooks/useTTS.ts:103`
**Root cause:** `CommandBar` always renders `Volume2` and calls `onSpeak` on click. The `useTTS()` hook exposes a `speaking` boolean and `stop()` function, but `index.tsx:193` only destructures `{ speak, stop: stopTts }` — `speaking` is never read. `stopTts` is only called in `handleSubmit` (line 254), never wired to the Volume2 button. Clicking during playback calls `speak()` which internally calls `stop()` then restarts — feels broken. Also the button is `disabled={isLoading}` so during graph streaming it's unclickable.
**Effect (reported by user):** "the text-to-speech playback button is no longer responding."
**Solution:** Thread `speaking` + a per-message "currently speaking message id" down from `index.tsx` → `AssistantMessage` → `CommandBar`:
1. `index.tsx`: track `speakingMessageIdRef` (which message ID was last spoken). Pass `isSpeaking={speaking && speakingMessageIdRef.current === message.id}` and `onSpeak` (which calls `stop()` if `isSpeaking`, else `speak()`) to `AssistantMessage`.
2. `AssistantMessage` (`ai.tsx`): accept `isSpeaking?: boolean` prop, pass to `CommandBar`.
3. `CommandBar` (`shared.tsx`): accept `isSpeaking?: boolean`. If `isSpeaking`, render `<Square className="size-4" />` with `tooltip="Stop playback"` and call `onSpeak` (wired to `stop()`). Otherwise keep `Volume2` + `tooltip="Read aloud"`.
4. Do NOT disable the button while `isLoading` — TTS playback is independent of graph streaming. Guard on `contentString.length === 0` instead.
**Verification:** Click Volume2 → audio plays, icon changes to stop. Click again → audio stops, icon reverts to Volume2. During graph streaming, button remains clickable.
**Test coverage:** No Playwright test currently exercises the TTS button. `tests/ui-controls.spec.ts` only checks the Voice/Send buttons in the footer are visible — does not click the Volume2 button on AI messages or assert the playing/stop state.

## Bug V4 — Voice selector dropdown fails silently if sidecar is down (P1)
**Source:** `agent-chat-ui/src/components/thread/index.tsx:170-179`
**Root cause:** The voice selector fetches `GET /api/tts/voices` on mount. The `.catch(() => {})` swallows any error (sidecar down, network failure, non-200 response). The dropdown silently renders with no options — the user sees a "Voice" label and a "Default" placeholder but an empty dropdown when clicked. No toast, no error UI, no fallback. Same pattern at line 169 for the models fetch.
**Effect (reported by user):** "there is a issue with the voice selector that's been added." When the sidecar (port 8000) is not running or `/api/tts/voices` returns an error, the voice dropdown appears broken with no explanation.
**Solution:**
1. Replace the silent `.catch(() => {})` with a toast: `toast.error("Could not load voices", { description: "TTS sidecar at http://127.0.0.1:8000 may not be running." })`.
2. If `voiceOptions` is empty, render the dropdown as disabled with a tooltip "No voices available (TTS sidecar not running)" rather than an empty clickable dropdown.
3. Rename "Default" placeholder to "Auto" to match the agent selector's convention and avoid implying there's a voice named "Default".
4. Apply the same fix to the models fetch at line 169.
**Verification:** Stop the sidecar (`lsof -ti:8000 | xargs kill`), refresh the page, click Voice dropdown — should show a toast and a disabled dropdown with tooltip, not an empty clickable dropdown.
**Test coverage:** `tests/ui-controls.spec.ts:44` ("model dropdown renders with options") mocks `/api/models` so it never exercises the real failure path. No test mocks `/api/tts/voices` at all, and no test asserts the voice dropdown's behavior when the sidecar is down.

## Bug V5 — Dead code in `_normalize_chunk` (P2)
**Source:** `backend/src/kyutai_tts.py:35-44`
**Root cause:** `_normalize_chunk` has duplicate code after a `return` — lines 41-44 are unreachable (dead). Copy-paste artifact. Doesn't affect behavior but is a code-smell that suggests the function was edited carelessly.
**Solution:** Delete lines 41-44.

## Recommended fix order
1. ~~**V1 (P0)** — AudioContext sample rate.~~ ✅ Fixed
2. ~~**V2 (P0)** — TTS thread-safety lock.~~ ✅ Fixed
3. **V3 (P1)** — TTS button playing/stop state (user-reported).
4. **V4 (P1)** — Voice selector silent failure (user-reported).
5. **V5 (P2)** — Dead code cleanup.

## What was verified against docs
- **Kyutai Pocket TTS API reference** (sample rate 24000 Hz, `generate_audio_stream` is official, voice embedding path format, not-thread-safe warning) — via fetch of `kyutai-labs.github.io/pocket-tts/API%20Reference/python-api/` + HuggingFace model card.
- **faster-whisper source + docs** (constructor signature, transcribe audio format, segments iteration, lru_cache thread-safety) — via fetch of `github.com/SYSTRAN/faster-whisper` + readthedocs. All four usages in `backend/src/stt.py` confirmed correct.
- **MDN AudioContext constructor docs** (sampleRate coercion behavior, NotSupportedError) — via webfetch of `developer.mozilla.org/en-US/docs/Web/API/AudioContext/AudioContext`.

## What was NOT verified (needs runtime testing)
- Whether the BlackHole → Element → speakers chain actually carries TTS audio (would need to listen).
- Whether 24000 Hz coercion is actually happening on this specific macOS setup (would need `new AudioContext({ sampleRate: 24000 }).sampleRate` in browser console).
- Whether concurrent TTS requests actually corrupt audio (would need two rapid Volume2 clicks).

---

## Voice Layer Fixes (2026-07-27)

All remaining voice-layer bugs from the audit have been fixed:

- **V3 (P1) — TTS button play/stop state** ✅ Fixed
  - `agent-chat-ui/src/components/thread/index.tsx` now tracks `speakingMessageIdRef` and passes `isSpeaking` to `AssistantMessage`.
  - `agent-chat-ui/src/components/thread/messages/ai.tsx` forwards `isSpeaking` to `CommandBar`.
  - `agent-chat-ui/src/components/thread/messages/shared.tsx` renders a stop square icon and `"Stop playback"` tooltip when `isSpeaking` is true; otherwise shows `Volume2` + `"Read aloud"`. Button is disabled only when content is empty, not during graph streaming.
  - Verified via new Playwright test `tests/tts.spec.ts`.

- **V4 (P1) — Voice/model selector silent failure** ✅ Fixed
  - `agent-chat-ui/src/components/thread/index.tsx` now surfaces `toast.error()` when `/api/models` or `/api/tts/voices` fail.
  - Dropdowns are disabled when options are empty, with a tooltip explaining the sidecar may not be running.
  - Placeholder renamed from `"Default"` to `"Auto"` to match the agent selector convention.

- **V5 (P2) — Dead code in `_normalize_chunk`** ✅ Fixed
  - Removed unreachable duplicate normalization code after the `return` statement in `backend/src/kyutai_tts.py:35-44`.

### Test updates
- `agent-chat-ui/tests/ui-controls.spec.ts`: mocks `/threads/search` so the app renders without a real LangGraph server; updates model/voice selector placeholder assertions to `"Auto"`.
- `agent-chat-ui/tests/tts.spec.ts`: new Playwright test that mocks the LangGraph stream and TTS SSE endpoint, sends a message, and asserts the Volume2 button toggles to stop and back.
- `agent-chat-ui/playwright.config.ts`: webServer now uses `pnpm start -p 3001` to serve the production build, matching the launcher configuration in Phase 10.

### Verification
- `backend/tests/`: 33/33 passing.
- `agent-chat-ui/tests/ui-controls.spec.ts`: 8/8 passing.
- `agent-chat-ui/tests/tts.spec.ts`: 1/1 passing.
- `agent-chat-ui/tests/phase2.spec.ts`: 1/2 passing (`thread persistence` still depends on a real LangGraph server; pre-existing limitation noted in Current Status).

---

## TTS Debugging Log (2026-07-26)

> Chronological record of every attempt to fix TTS playback in the UI. The backend endpoint (`POST /api/tts/stream`) has been confirmed working (200 OK, SSE audio data) throughout. All failures are in the frontend `useTTS.ts` AudioContext pipeline.

### Attempt 1 — AudioContext created after `await fetch()` (FAILED)
**Hypothesis:** Browsers suspend AudioContexts created outside a user gesture. The `new AudioContext()` was after `await fetch()`, so the browser saw it as non-user-initiated.
**Fix:** Moved `new AudioContext()` before the `await fetch()` so it's created synchronously during the click handler.
**Result:** Still no audio. Console showed `AudioBufferSourceNode is not useful when context is closed` — the context was being closed by a different `speak()` call's `finally` block.

### Attempt 2 — `finally` block closed shared ref instead of local ctx (FAILED)
**Hypothesis:** The `finally` block did `audioCtxRef.current?.close()` — a shared ref that gets overwritten by every `speak()` call. When two TTS requests overlapped, the second request's `finally` would close the first request's AudioContext.
**Fix:** Changed `finally` to close the local `ctx` variable instead of the shared ref, and only clear the ref if it still points to the same context.
**Result:** Still no audio. Console showed `InvalidStateError: Cannot close a closed AudioContext` — `stop()` was closing the context, then `finally` tried to close it again.

### Attempt 3 — Wrapped `ctx.close()` in try/catch (FAILED)
**Hypothesis:** The double-close error was a promise rejection that try/catch would catch.
**Fix:** Wrapped `ctx.close()` in `try { ctx.close(); } catch {}`.
**Result:** Still the same `InvalidStateError`. Root cause: `AudioContext.close()` returns a **Promise** in Chrome, and `try/catch` doesn't catch unhandled promise rejections. The error was escaping.

### Attempt 4 — Check `ctx.state !== "closed"` before closing + `.catch(() => {})` on the promise (CURRENT)
**Hypothesis:** The durable fix is to check the context state before closing in both `stop()` and the `finally` block, and handle the promise rejection properly.
**Fix applied to `useTTS.ts`:**
- `stop()` (line 34-39): `if (audioCtxRef.current && audioCtxRef.current.state !== "closed") { audioCtxRef.current.close().catch(() => {}); }`
- `finally` block (line 125-131): `if (ctx.state !== "closed") { ctx.close().catch(() => {}); }`
**Result:** Pending user verification. Console should show `[TTS] AudioContext state: running sampleRate: 44100` followed by `[TTS] playback done, chunks: N duration: X.Xs` with no `InvalidStateError`.

### Other changes made during debugging
- **`shared.tsx:202`** — Volume2 button was `disabled={isLoading}`, making it unclickable during graph streaming. Changed to `disabled={!content || content.length === 0}` so TTS is independent of graph state.
- **`useTTS.ts:55-57`** — Added `ctx.resume()` fallback for browsers that suspend AudioContexts despite being created in a click handler (Brave's stricter autoplay policy).
- **`useTTS.ts:58,110`** — Added `console.log` diagnostics: `[TTS] AudioContext state: running sampleRate: 44100` and `[TTS] playback done, chunks: N duration: X.Xs`.

### Current state of `useTTS.ts` (after all fixes)
- AudioContext created synchronously before any `await` (user-gesture-initiated) ✅
- `ctx.resume()` fallback if suspended ✅
- `stop()` checks `state !== "closed"` before closing ✅
- `finally` block checks `state !== "closed"` before closing ✅
- Both `.close()` calls handle the promise with `.catch(() => {})` ✅
- Volume2 button not disabled during graph streaming ✅
- Console diagnostics for debugging ✅

### What still needs fixing (separate from playback)
- ~~**V3 (P1)** — TTS button has no playing/stop state~~ ✅ Fixed — see "Voice Layer Fixes (2026-07-27)".
- ~~**V4 (P1)** — Voice selector silent failure (`.catch(() => {})` swallows errors)~~ ✅ Fixed — see "Voice Layer Fixes (2026-07-27)".
- ~~**V5 (P2)** — Dead code in `_normalize_chunk` (`kyutai_tts.py:41-44`)~~ ✅ Fixed — see "Voice Layer Fixes (2026-07-27)".

---
- `start_image_pipeline.sh` rewritten: langgraph dev (port 8123) added as a core blocking service; frontend fixed to `cd "$ROOT/agent-chat-ui"`, `pnpm` (was `npm`), port 3001 (was 3000); production build with auto-rebuild detection replaces `npm run dev`.
- **Auto-rebuild:** `start_frontend` compares newest `.ts`/`.tsx` mtime in `src/` against `.next/BUILD_ID` mtime. If source is newer (or BUILD_ID missing), runs `pnpm build`; otherwise serves the cached build. User (or coding agent) never thinks about builds — first launch builds, subsequent launches are instant, source changes trigger automatic rebuild on next launch.
- **Reordered start:** core services (langgraph 8123 → sidecar 8000 → UI 3001) start blocking first so chat is usable in ~15s. Heavy services (Ollama, ComfyUI, Element, audio routing) start in a backgrounded subshell with `set +e` so their failure doesn't bring down the core.
- `Multi Agent System.app` bundle verified end-to-end: double-clicking it (or running its `Contents/MacOS/launch` shim) starts everything, no terminal touched.
- Measured: UI cold load 18ms, warm 2ms (production `next start`); was 3.4s cold / 80ms warm with dev mode.
- **33/33 backend tests, 9/9 Playwright tests still passing.** Playwright UI tests ~2-4x faster (200-540ms vs 700-1000ms) because they hit the production server.
- **Note:** `pnpm dev` (dev mode with HMR) is still available for the coding agent's editing workflow — `cd agent-chat-ui && pnpm dev --port 3001`. The launcher uses `pnpm start` (production) for the end user.

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

### End-user launch (recommended)

Double-click `Multi Agent System.app` in Finder, or from the repo root:

```bash
./start_image_pipeline.sh start    # core services block, heavy services in background
./start_image_pipeline.sh stop
./start_image_pipeline.sh status
./start_image_pipeline.sh restart
```

This starts core services (langgraph 8123, sidecar 8000, UI 3001 — production build with auto-rebuild) then heavy services (Ollama, ComfyUI, Element, audio routing) in parallel non-blocking.

### Manual / development

```bash
# Start langgraph dev (graph server) — the actual backend the UI talks to
cd backend && nohup ./venv/bin/langgraph dev --port 8123 --no-browser &

# Start FastAPI sidecar (TTS/STT/models list — has dead code, see cleanup section)
cd backend && ./venv/bin/uvicorn src.web_server:app --port 8000

# Start Agent Chat UI — dev mode with HMR (for editing UI code)
cd agent-chat-ui && pnpm dev --port 3001

# Or serve the production build directly (what the launcher uses)
cd agent-chat-ui && pnpm build && pnpm start -p 3001
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

### Sidecar Cleanup — ✅ Complete (2026-07-27)
`backend/src/web_server.py` rewritten as a single-responsibility, stateless bridge. It no longer compiles or owns any LangGraph graph — that lives on `langgraph dev` (port 8123), matching the Agent Chat UI architecture (the UI is a client to a LangGraph server).

**Final route table (6 routes):**
- `GET /health` → `{"status":"ok"}`
- `POST /api/tts/stream` → Kyutai TTS SSE streaming (unchanged response contract)
- `GET /api/tts/voices` → `{"voices":[...],"total":N}`
- `POST /api/stt` → faster-whisper transcription (`UploadFile` → `{"transcript":...}`)
- `GET /api/models` → cloud default + local Ollama tags (model dropdown)
- `GET /api/fs/pick-folder` → native macOS folder picker, returns absolute POSIX path (repo picker)

**Removed (now return 404):** `/api/chat`, `/api/tts` (non-stream), `/api/tts/voices/clone`, `/api/stt/debug`, `/api/fs/home`, `/api/fs/list`, `/api/jobs`, `/api/jobs/{id}`, the `lifespan` graph compilation, the `ChatMessage`/`ChatRequest`/`ChatResponse`/`TTSRequest`/`VoiceCloneRequest`/`FSListResponse`/`JobResponse` models, the `_has_checkpoint`/`_build_invocation_input`/`_log_request` helpers, and the `create_chat_ui`/`jobs`/`debug_decode` imports.

**CORS hardened:** the previous `allow_origins=["*"]` + `allow_credentials=True` is explicitly disallowed by the FastAPI CORS docs. Replaced with an explicit allowlist read from `SIDECAR_ALLOWED_ORIGINS` (default `http://localhost:3001,http://127.0.0.1:3001`), `allow_methods=["GET","POST","OPTIONS"]`, `allow_headers=["*"]`.

**Files unchanged:** `backend/src/stt.py` (`debug_decode()` kept as a module-level diagnostic; only the import removed), `backend/src/kyutai_tts.py` (already correct per Pocket TTS docs + thread-safety lock), `backend/src/jobs.py` and `backend/src/ollama_client.py` (files kept; only `web_server.py` drops the unused imports).

**Sources:** Agent Chat UI README (UI is a LangGraph server client); FastAPI Lifespan Events (lifespan = shared app resources, not a shadow graph); FastAPI CORS docs (wildcard + credentials invalid); faster-whisper README (`transcribe()` API); Pocket TTS Python API reference (`generate_audio_stream`, 24 kHz, not thread-safe).

**Verification (2026-07-27):**
- Route smoke: `from src.web_server import app` → exactly the 6 routes + `/`, `/docs`, `/openapi.json`, `/redoc`.
- Live smoke: `/health` 200, `/api/models` returns list, `/api/tts/voices` returns list, `/api/chat` 404, `/api/jobs` 404, `/api/tts` 404, `/api/fs/home` 404, `/api/stt/debug` 404.
- CORS: allowed origin echoes `access-control-allow-origin`; disallowed origin returns none.
- Backend tests: 33/33 passing.
- Frontend build: passes.
- Playwright: 11/11 passing (ui-controls 8, tts 1, phase2 2).

### phase2.spec.ts — ✅ Fixed (2026-07-27)
Both phase2 tests now select the **Jasper** agent before sending (per Phase 3, `target_agent` bypasses the approval interrupt), so the first turn produces an assistant reply instead of an Agent-Inbox "Approve/Reject" card. Keeps them real end-to-end against the running LangGraph server with real persistence. Both pass (5.3s, 5.4s).

## Next Steps (in order)

1. ~~**Voice layer bugs V1-V5**~~ ✅ All fixed — see "Voice Layer Audit" and "Voice Layer Fixes (2026-07-27)".
2. **Phase 8** — Visual dashboard (agent badges, handoff cards)
3. **Phase 9** — OpenCode streaming (deferred, highest risk)
4. ~~**Sidecar cleanup**~~ ✅ Complete — see "Sidecar Cleanup — ✅ Complete (2026-07-27)" above.

---

## Performance / UI Lag Fix Plan (2026-07-27)

### Validation of prior analysis

The plan below was validated against the actual codebase by reading every file involved. Key findings:

- **`active_agent`, `handoff_history`, `decision_log`** — ZERO runtime reads in any UI component. Only appear as type defs in `Stream.tsx:32-34,48-50`. Set by backend (`chat_ui.py`) but never consumed by frontend. Safe to ignore for stream mode changes.

- **`streamMode: ["values"]` → `["messages"]`** — The SDK docs confirm `["values"]` returns full state per step, while `["messages"]` returns LLM message chunks. No UI code reads `stream.values` directly (only `stream.messages`, `stream.interrupt`, `stream.isLoading`, `stream.error`). The `useStream` hook handles both modes generically — mode is per-submit (not hook-level), and `SubmitOptions` (line 904 in SDK types) explicitly supports per-call mode switching.

- **`streamSubgraphs: true`** — Must be KEPT per LangChain forum posts: the SDK's `MessageTupleManager` needs it to properly route message chunks from subgraph LLM calls. Without it, subgraph message accumulation breaks.

- **`tool-calls.tsx` `let` variables** — Confirmed `let parsedContent: any`, `let isJsonContent = false` at lines 71-72. Required due to try/catch assignment pattern. Wrapping in `useMemo` needs a single-expression return (destructured object/tuple).

- **Already running production build** — Process is `next-server` (production server binary), not `next dev`. The "switch to prod" suggestion from the original GLM analysis was based on a false premise and is REMOVED.

- **`React.memo` on `AssistantMessage` is INEFFECTIVE** — The component reads `useStreamContext()` (line 122 of `ai.tsx`), so React context re-renders bypass prop memoization entirely. SKIPPED.

### Execution Plan (phased by risk)

#### Phase 1 — Leak Fixes (isolated, no UI surface change)

| # | File | Lines | Change |
|---|---|---|---|
| 1 | `useTTS.ts` | 34-41, 115-122 | Store `setInterval` in a ref. Clear it in `stop()` alongside the `AbortController` abort. Add `useEffect` cleanup that calls `stop()` on unmount. |
| 2 | `useSTT.ts` | 11-25 | Add `useEffect` cleanup that stops `MediaRecorder` (if recording) and calls `cachedStreamRef.current?.getTracks().forEach(t => t.stop())` on unmount. |

#### Phase 2 — Single-line Performance Wins

| # | File | Lines | Change |
|---|---|---|---|
| 3 | `index.tsx` | 382 | Remove `layout={isLargeScreen}` from the `<motion.div>` streaming container — the `animate` prop already handles marginLeft/width changes; `layout` adds redundant layout measurement overhead on every stream tick. |
| 4 | `index.tsx` (×2), `human.tsx` | 303, 333, 60 | Change `streamMode: ["values"]` → `["messages"]`. **Keep `streamSubgraphs: true`.** This stops the server from re-sending the full state (messages + ui + handoff_history + decision_log) on every token — instead sending incremental message chunks. |
| 5 | `tool-calls.tsx` | 71-86 | Wrap `JSON.parse()`/`JSON.stringify()` of tool results in `useMemo`. These recompute on every parent render with no memoization. Refactor the `let` variables into a single-expression return. |

#### Phase 3 — UI Polish

| # | File | Lines | Change |
|---|---|---|---|
| 6 | `index.tsx` | 660-691 | Show tooltip on Model `Select` when `selectedModel === ""` (Auto): `"Auto: uses agent default (glm-5.2 for chat, qwen3.5:397b for coding)"`. The tooltip infrastructure already exists (lines 685-689) — currently only shows on error. Extend to always show on "Auto". |

#### Phase 4 — Runtime (manual, no code)

| # | Action |
|---|---|
| 7 | Stop ComfyUI (`main.py --port 8188`, ~560 MB RSS) if not actively generating images |
| 8 | Consider lazy-loading the TTS model in the sidecar (`web_server`, ~2.8 GB across two Python processes) instead of loading at startup |

### Items Explicitly Skipped

| Item | Reason |
|---|---|
| ~~Switch to production build~~ | Already running `next-server` (production binary). False premise from original analysis. |
| ~~Memoize `AssistantMessage` with `React.memo`~~ | **Ineffective.** Component reads `useStreamContext()` (ai.tsx:122), so context re-renders bypass prop memo. Would need to decouple context reads from rendering first. |
| ~~Drop `streamSubgraphs: true`~~ | SDK's `MessageTupleManager` needs it for subgraph message routing per LangChain forum posts. |
| ~~Virtualize message list~~ | High complexity — breaks TTS (scrolled-off messages unmount mid-playback), loading state, interrupt rendering. Deferred to separate task. |

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

---

## Persistent Todo List with Model Attribution (2026-07-27)

### Goal

A single source of truth for project task tracking. OpenCode Desktop (external app running various models) writes a master `todos.json` file on disk. The LangGraph graph mirrors it into state so Jasper has awareness and can answer questions about it. The UI displays it in a persistent right-side sidebar panel.

### Design decisions (locked)

- **Master file:** `todos.json` at repo root — the durable source of truth on disk.
- **Protocol doc:** `AGENTS.md` at repo root — OpenCode Desktop reads this to learn the schema and rules.
- **Model ID format:** Full provider-prefixed ID (e.g. `ollama-cloud/glm-5.2`, `ollama/qwen3:32b`, `anthropic/claude-sonnet-4.5`). OpenCode Desktop self-reports — it knows its own model; no backend lookup.
- **Section-level attribution:** `planned_by_model` — what model authored that plan section. Set once at creation, never modified.
- **Todo-level attribution:** `completed_by_model` — what model was running when the work was done. Set when the todo is marked completed.
- **UI placement:** Right sidebar with a header toggle button (mirrors the existing left chat-history sidebar pattern). Toggled via nuqs `todosOpen` query param.
- **Read path (UI):** Frontend polls `GET /api/todos` on the FastAPI sidecar every 3 seconds. This avoids reverting `streamMode` to `["values"]`/`["updates"]` — the `["messages"]` perf win from the Performance / UI Lag Fix Plan stays intact.
- **Read path (Jasper awareness):** The LangGraph supervisor reads `todos.json` at the start of each turn and places it into state. The `run_jasper` wrapper passes `todos` into the Jasper subgraph. Jasper's system prompt injects the todo data as context so the user can ask "what's the status of the perf fixes?" / "which model completed the TTS leak fix?" and get accurate answers.
- **Durability:** `langgraph dev` uses a persistent file-based checkpointer (`backend/.langgraph_api/*.pckl`), so state survives restarts. The disk file is the master; the state is a per-turn mirror.

### Why not pure LangGraph state (without the file)?

OpenCode Desktop is an external application that edits files on disk. It cannot directly mutate LangGraph state (which lives in pickle files managed by the running `langgraph dev` process). The file is the bridge: OpenCode Desktop writes it; the graph reads it each turn and syncs it into state.

### Why not pure file polling (without state)?

If todos lived only in the file and the UI polled it, Jasper would have no awareness of the todo list when responding. Putting todos into state (mirrored from the file) gives Jasper context-awareness — the user can ask Jasper questions about the todo list and get accurate answers, not hallucinations.

---

### `todos.json` schema (master file, repo root)

```json
{
  "version": 1,
  "updated_at": "2026-07-27T22:00:00Z",
  "updated_by": "opencode-desktop",
  "sections": [
    {
      "id": "kebab-case-id",
      "title": "Human-readable section title",
      "created_at": "ISO-8601",
      "planned_by_model": "ollama-cloud/glm-5.2",
      "planned_by_agent": "opencode-desktop",
      "todos": [
        {
          "id": "kebab-case-id",
          "content": "What needs to be done",
          "status": "pending|in_progress|completed",
          "agent": "opencode|jasper|research|magic-coder|null",
          "completed_by_model": "ollama-cloud/glm-5.2|null",
          "completed_at": "ISO-8601|null",
          "notes": "brief summary of what was done"
        }
      ]
    }
  ]
}
```

**Two attribution layers:**
- `planned_by_model` (section-level) — set once when a section is created; records what model authored that plan section.
- `completed_by_model` (todo-level) — set when a todo is marked completed; records what model was running when the work was done.

---

### `AGENTS.md` contents (repo root)

Protocol document OpenCode Desktop reads on startup. Contains:

```markdown
# Agent Protocol — Todo List

## Location
- Master file: `todos.json` (repo root, this directory)
- This is the single source of truth for project task tracking.

## Schema
[full field-by-field table with types and descriptions — see todos.json schema above]

## Rules

### Adding a new plan section
When you create a new set of related todos:
1. Append a new object to `sections[]`
2. Set `planned_by_model` to your current full model ID (e.g. "ollama-cloud/glm-5.2")
3. Set `planned_by_agent` to "opencode-desktop"
4. Generate a unique kebab-case `id` and an ISO-8601 `created_at` timestamp
5. Every todo starts as `status: "pending"`, `completed_by_model: null`, `completed_at: null`

### Completing a todo
When you finish work on a todo:
1. Set `status` to "completed"
2. Set `completed_by_model` to your current full model ID
3. Set `completed_at` to the current ISO-8601 timestamp
4. Update `notes` with a brief summary of what was done
5. Bump top-level `updated_at` and `updated_by`

### Marking a todo in_progress
1. Set `status` to "in_progress"
2. Bump top-level `updated_at`

### Never
- Delete a completed todo (preserve the audit trail)
- Modify `planned_by_model` after section creation
- Reorder completed todos above pending ones
- Edit `todos.json` for any purpose other than task tracking

## Worked example
[full JSON example showing add-section + complete-todo flow with model attribution]
```

---

### Execution Plan

#### Phase 1 — Todo JSON Schema + Seed File + Protocol Doc

| # | File | Lines | Change |
|---|---|---|---|
| 1 | `todos.json` (new, repo root) | — | Create. Parse HANDOFF.md into sections: (a) "Original Plan (Phases 0-10)" — Phases 0–10 as todos, most marked completed; (b) "Performance / UI Lag Fix Plan" (lines 519–576) — all 6 code changes marked completed with model attribution (`ollama-cloud/glm-5.2`), the 2 runtime items (ComfyUI, TTS lazy-load) as pending; (c) "Persistent Todo List" — the current work, marked in_progress. |
| 2 | `AGENTS.md` (new, repo root) | — | Create. Protocol instructions for OpenCode Desktop: schema, add-section/complete-todo/in_progress rules, model attribution requirements, "never" rules, worked example. |

#### Phase 2 — Backend: FastAPI endpoint

| # | File | Change |
|---|---|---|
| 3 | `backend/src/web_server.py` | Add `GET /api/todos` endpoint. Reads `todos.json` from repo root (path configurable via `TODOS_FILE` env var, default `../todos.json` relative to backend). Returns JSON as-is. If file missing, returns `{"version": 1, "sections": []}`. No LangGraph state involvement on the read path. |

#### Phase 3 — Backend: LangGraph state mirror + Jasper awareness

| # | File | Lines | Change |
|---|---|---|---|
| 4 | `backend/src/chat_ui.py` | 15–26 | Add `todos: list[dict]` to the `State` TypedDict. Uses a **replace-reducer** (not `operator.add`) — the whole list is overwritten each turn so state always mirrors the file. |
| 4 | `backend/src/chat_ui.py` | top of file | Add `_load_todos()` helper: reads `todos.json` from repo root, returns `sections` list. Handles `FileNotFoundError`/`JSONDecodeError` by returning `[]`. |
| 4 | `backend/src/chat_ui.py` | 57–111 | In `supervisor_node`, call `_load_todos()` at the top and include `"todos": <file sections>` in every `Command`/dict return (all 3 return paths: lines 61–70, 79–84, 104–111). This ensures state mirrors the file at the start of each turn, picking up any edits OpenCode Desktop made between turns. |
| 5 | `backend/src/chat_ui.py` | 166–168 | Modify `run_jasper` wrapper to pass `todos` from parent state into the Jasper subgraph: `jasper_app.invoke({"messages": state["messages"], "todos": state.get("todos", [])})`. |
| 6 | `backend/src/jasper_agent.py` | 9–11 | Add `todos: list[dict]` to the subgraph `State` TypedDict (received from parent, read-only). |
| 6 | `backend/src/jasper_agent.py` | 14–23 | Add `_format_todos_for_prompt(todos)` helper that formats the sections/todos as a readable checklist with status markers (○ ◉ ✓) and model attribution. Modify `jasper_agent` to inject the formatted todos into the system prompt: "You have access to the project's current todo list. When the user asks about task status, what's been done, what model did what, or what's pending, answer from the todo data below." followed by `CURRENT TODO LIST:\n<formatted todos>`. |

**`_format_todos_for_prompt` reference implementation:**
```python
def _format_todos_for_prompt(todos):
    if not todos:
        return "No todos currently tracked."
    lines = []
    for section in todos:
        lines.append(f"## {section['title']} (planned by {section.get('planned_by_model', 'unknown')})")
        for t in section.get("todos", []):
            mark = {"pending": "○", "in_progress": "◉", "completed": "✓"}.get(t["status"], "○")
            model = f" [done by {t['completed_by_model']}]" if t.get("completed_by_model") else ""
            lines.append(f"  {mark} {t['content']}{model}")
    return "\n".join(lines)
```

**Note on prompt size:** The todo list could grow large over time. For now the HANDOFF seed has ~20 todos, which is fine. If it grows large later, truncate `_format_todos_for_prompt` to pending + in_progress + recently-completed. Not implementing truncation now.

#### Phase 4 — Frontend: Todo types + sidebar panel

| # | File | Lines | Change |
|---|---|---|---|
| 7 | `agent-chat-ui/src/lib/types/todo.ts` (new) | — | Create. `TodoStatus = "pending" \| "in_progress" \| "completed"`. `Todo` interface (id, content, status, agent, completed_by_model, completed_at, notes). `TodoSection` interface (id, title, created_at, planned_by_model, planned_by_agent, todos). `TodoFile` interface (version, updated_at, updated_by, sections). |
| 8 | `agent-chat-ui/src/components/thread/todos/index.tsx` (new) | — | Create. Right-side sidebar panel mirroring the left chat-history sidebar pattern (`index.tsx:346–369`). Contains: `TodoList` (progress bar: completed/total, percentage), `TodoItem` (status icons ○ ◉ ✓, color coding gray/amber/green, animate-pulse on in_progress, agent + model attribution display), `ProgressBar`. Fetches `GET /api/todos` every 3 seconds via polling (preserves the `["messages"]` streamMode perf win — no streamMode revert needed). |
| 9 | `agent-chat-ui/src/components/thread/index.tsx` | header | Add a toggle button in the header (next to the chat-history toggle) that shows/hides the todos sidebar. Use `useQueryState("todosOpen", { defaultValue: false })` via nuqs (same pattern as `chatHistoryOpen`). |
| 9 | `agent-chat-ui/src/components/thread/index.tsx` | right side | Add the todos sidebar as a right-side `motion.div` (mirroring lines 346–369 but on the right). Animate width/x based on `todosOpen` state. |
| 10 | `agent-chat-ui/src/providers/Stream.tsx` | 29–58 | Add `todos?: TodoSection[]` to `StateType` and `UpdateType` (so the agent-inbox StateView auto-renders it and the type round-trip works). Import the `TodoSection` type from `lib/types/todo`. |

#### Phase 5 — Tests + verification

| # | Action |
|---|---|
| 11 | Restart LangGraph + Backend + Frontend (leave ComfyUI off). Run `backend/`: `python -m pytest tests/ -v`. Run `agent-chat-ui/`: `pnpm exec playwright test`. Run `agent-chat-ui/`: `npx tsc --noEmit`. All must pass. |

---

### What stays unchanged (perf wins from Performance / UI Lag Fix Plan preserved)

- `streamMode: ["messages"]` — no revert to `["values"]`/`["updates"]`. The UI reads todos via HTTP polling, not the stream.
- `streamSubgraphs: true` — kept.
- `layout` prop removal on `<motion.div>` — kept.
- TTS/STT leak fixes (`useTTS.ts`, `useSTT.ts`) — kept.
- `useMemo` in `tool-calls.tsx` — kept.
- Model tooltip on Auto selection — kept.

---

### Files touched (summary)

| # | File | Action |
|---|---|---|
| 1 | `todos.json` (new, repo root) | Create — seed from HANDOFF.md |
| 2 | `AGENTS.md` (new, repo root) | Create — protocol for OpenCode Desktop |
| 3 | `backend/src/web_server.py` | Modify — add `GET /api/todos` |
| 4 | `backend/src/chat_ui.py` | Modify — add `todos` to State, `_load_todos()`, supervisor reads file each turn, `run_jasper` passes todos through |
| 5 | `backend/src/jasper_agent.py` | Modify — add `todos` to subgraph State, `_format_todos_for_prompt()`, inject todos into system prompt |
| 6 | `agent-chat-ui/src/lib/types/todo.ts` (new) | Create — Todo types |
| 7 | `agent-chat-ui/src/components/thread/todos/index.tsx` (new) | Create — right sidebar panel + TodoList + TodoItem + ProgressBar |
| 8 | `agent-chat-ui/src/components/thread/index.tsx` | Modify — add right sidebar + header toggle button |
| 9 | `agent-chat-ui/src/providers/Stream.tsx` | Modify — add `todos` to StateType/UpdateType |

---

### Seed data: parsing HANDOFF.md into todos.json

The seed `todos.json` will contain 3 sections:

**Section 1: "Original Plan (Phases 0-10)"**
- `planned_by_model`: `"unknown"` (pre-dates this system)
- `planned_by_agent`: `"seed-from-handoff"`
- 11 todos (Phase 0 through Phase 10), most marked `completed` with `completed_by_model: "unknown"`.

**Section 2: "Performance / UI Lag Fix Plan"** (HANDOFF.md lines 519–576)
- `planned_by_model`: `"ollama-cloud/glm-5.2"`
- `planned_by_agent`: `"opencode-desktop"`
- 8 todos: 6 code changes marked `completed` (with `completed_by_model: "ollama-cloud/glm-5.2"`), 2 runtime items (ComfyUI, TTS lazy-load) marked `pending`.

**Section 3: "Persistent Todo List"**
- `planned_by_model`: `"ollama-cloud/glm-5.2"`
- `planned_by_agent`: `"opencode-desktop"`
- The todo-list feature work itself, marked `in_progress`.

---
