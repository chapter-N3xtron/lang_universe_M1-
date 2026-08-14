## Why

Conversation placement is currently not deterministic at the browser-visible message boundary. The implementation uses a hard-coded 32px offset and can target an invisible inner anchor, while existing automated coverage does not prove that the visible message shell/header and playback/command controls are on-screen; real assistant streaming/completion coverage is also incomplete.

## What Changes

- Replace the unresolved placement contract with an explicit, deterministic lifecycle:
  - On reopen/hydration, top-align the latest completed visible message exactly once.
  - On submission, top-align the new user message exactly once.
  - When that turn's assistant response completes, perform exactly one replacement placement on the completed assistant message.
- Define the destination from the conversation viewport's real usable content-top edge, including measured layout/control insets; do not encode a fixed 32px assumption.
- Make the visible target message shell/header the placement target, and require its playback/command controls to be fully on-screen without clipping above the viewport.
- Define tall-message behavior: the visible header and message top must be shown even when the full response cannot fit.
- Make wheel, touch, keyboard, scrollbar, selection, and any other human movement cancel pending automatic placement.
- Ensure streaming chunks, resizes, rerenders, reduced-motion mode, and layout mutations cannot repeat a completed placement.
- Add an implementation and verification plan covering source/layout audit, state-machine implementation, deterministic geometry assertions, real assistant streaming/completion, cancellation, and observation evidence.
- Keep the companion observation workflow explicitly cross-referenced; it observes and reports behavior but does not implement or prove this capability by itself.

## Capabilities

### New Capabilities
- `conversation-scroll-anchoring`: Deterministic one-shot placement of visible conversation turns across hydration, submission, and assistant completion.

### Modified Capabilities
- None.

## Impact

Implementation is expected in the conversation message-list/message-shell and viewport layout paths, with focused browser tests and live observation only during the later apply/verification phase. This run changes planning artifacts only: no application code, tests, evidence artifacts, `todos.json`, dashboard/PM/governance work, or the `manual-scroll-observation-capture` change is modified.
