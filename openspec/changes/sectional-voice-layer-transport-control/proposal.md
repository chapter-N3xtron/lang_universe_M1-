## Why

The existing Pocket TTS streamed PCM/Web Audio path can start and stop a single narration session, but it does not provide one shared playback model for the latest answer, answer sections, message-level controls, keyboard actions, or macro keys. Users therefore lack predictable transport control as answers become longer and section-aware playback is introduced. This change proposes a lightweight frontend controller over the existing transport, preserving the backend/API while making replacement, cancellation, accessibility, and scroll behavior explicit.

## What Changes

- Add a staged frontend playback controller over the existing Pocket TTS streamed PCM/Web Audio layer.
- Stage 1: provide a bottom play/stop control beside the microphone for the latest completed assistant answer.
- Stage 2: add sequential playback of speakable answer sections and per-section playback controls.
- Share controller state and commands across bottom, message-level, and section controls.
- Define explicit stop-and-replace behavior when a section is selected during whole-answer playback.
- Route keyboard and macro-key actions through the same controller; defer true pause/resume until browser/audio verification supports it.
- Preserve conversation scroll position and scroll anchoring during playback and control interactions.
- Keep the existing Pocket TTS backend/API unless later evidence proves a backend change necessary.
- Define Markdown sectionization and unresolved policies for lists, code, tables, math, tool output, and streaming partial content.

## Capabilities

### New Capabilities

- `sectional-voice-layer-transport-control`: Shared staged playback transport for completed assistant answers and their speakable sections over the existing streamed PCM/Web Audio layer.

### Modified Capabilities

- None.

## Impact

Expected implementation impact is limited to frontend playback state, message/section metadata, transport/audio coordination, controls, keyboard/macro action routing, and focused browser/unit verification. The existing `/api/tts/stream` endpoint supplies base64 PCM SSE chunks; the current `useTTS()` hook is single-session start/stop and does not provide a shared queue or true pause/resume. Existing message-level controls and visualization-node narration are related capabilities, but are not the new shared controller. No durable playback records or LangGraph checkpoint state are introduced.

This change is separate from `conversation-scroll-anchoring`, `manual-scroll-observation-capture`, `visualization-board-alignment`, `durable-interaction-records`, and PM/governance work; it links to those boundaries where relevant without modifying them. The `conversation-scroll-anchoring` OpenSpec is cross-referenced for the requirement that playback and control events do not reposition the conversation.
