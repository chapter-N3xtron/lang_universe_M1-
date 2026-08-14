## Context

See `proposal.md` for motivation and scope, and `specs/sectional-voice-layer-transport-control/spec.md` for the behavior contract. The existing `/api/tts/stream` endpoint supplies base64 PCM SSE chunks. The current `useTTS()` hook is a single-session start/stop facility: it does not provide a shared queue, section sequencing, replacement generations, or true pause/resume. Existing message-level controls and visualization-node narration are related existing capabilities, not this shared controller.

The companion `../conversation-scroll-anchoring/` OpenSpec defines deterministic message placement and is cross-referenced here only at the boundary: playback state changes must not become placement events. `manual-scroll-observation-capture`, `visualization-board-alignment`, `durable-interaction-records`, and PM/governance work remain separate.

## Goals / Non-Goals

**Goals:**

- Introduce a frontend-only transport coordinator with one authoritative state and command path for bottom, message, section, keyboard, and macro controls.
- Reuse the current streamed PCM/Web Audio boundary and isolate transport adaptation from UI state.
- Support Stage 1 latest-completed-answer play/stop, then Stage 2 deterministic section sequencing and per-section replacement.
- Make cancellation, stale callbacks, errors, new-message overlap, stable IDs, and no-scroll behavior testable.
- Place the Stage 1 design in the stable bottom-locking branch only after its gate; keep Stage 2 experimental until evidence and policies are complete.

**Non-Goals:**

- No Pocket TTS backend/API change, new endpoint, durable playback record, LangGraph checkpoint field, PM/dashboard work, governance change, or application implementation in this planning change.
- No initial true pause/resume acceptance requirement.
- No automatic scroll-to-message, bottom-following, focus stealing, or narration of arbitrary tool/visualization output.

## Decisions

### 1. One controller owns intent and playback generations

Use a small frontend controller/store as the only owner of playback intent. Its state is conceptually:

```text
idle | starting | playing | advancing | stopping | error
active: { messageId, sectionId?, mode: answer|section, generation }
queue: ordered PlaybackItem[]
requested: command metadata
error: safe user-facing category | null
```

Commands are `playAnswer(messageId)`, `playSection(messageId, sectionId)`, `stop(reason)`, and the evidence-gated future `pause/resume`. Every command increments or validates a monotonic generation. A section command always performs stop-and-replace, clearing the whole-answer queue before starting the selected item. Completion and error callbacks carry the generation and item identity; mismatches are ignored.

**Alternative rejected:** separate hook instances or local booleans per control. They permit two audio sessions, disagreeing labels, and callbacks that update an obsolete surface.

### 2. Adapter boundary around existing SSE PCM audio

Keep the existing `/api/tts/stream` request and base64 PCM SSE protocol. Add an adapter boundary that accepts one playback item and returns lifecycle events (`started`, PCM/chunk progress if needed, `completed`, `canceled`, `error`). The controller owns queue advancement and cancellation; the adapter owns stream decoding, AudioContext/AudioBuffer scheduling, and abort/cleanup. Stop must abort the SSE request and disconnect/clear scheduled audio where the browser permits.

True pause/resume is deliberately not represented as a required initial adapter guarantee. A future implementation must first prove browser behavior for streamed PCM, queued buffers, and restart position.

**Alternative rejected:** changing the backend to return whole files or durable jobs. That increases latency/API surface and violates the preserve-backend constraint without evidence.

### 3. Stable identity model

Use the existing stable assistant message identity where available. For each completed message, section identity is scoped as `messageId + deterministic section key`; the key should combine section boundary/order and normalized source identity rather than array index alone. A controller generation is session-ephemeral and never persisted. If source identity changes, old callbacks are invalid even when rendered text looks similar.

### 4. Sectionization is deterministic and conservative

Sectionization runs only after completion. Markdown headings and paragraphs are candidate boundaries; whitespace is normalized only for speakability and source order is preserved. The implementation must make an explicit policy decision before accepting lists, code, tables, math, tool output, and partial streams. Until resolved, unsupported blocks are excluded or visibly marked unsupported, never silently narrated. This keeps the initial queue predictable and avoids speaking syntax or hidden tool payloads by accident.

### 5. UI surfaces are projections, not owners

The bottom control beside the microphone represents the latest completed answer in Stage 1. Message-level and per-section controls become projections of shared state in Stage 2. The controller should expose selectors for active identity, queue membership, busy/error status, and whether an action is allowed. Keyboard and macro adapters translate input into the same commands and respect text-entry focus and reduced-motion/accessibility conventions.

### 6. Scroll and focus isolation

Audio lifecycle events must not call conversation placement or mutate scroll containers. Control state updates should preserve DOM identity where practical, avoid focus relocation, and use stable labels/live-region announcements rather than layout movement. Verification should record scrollTop/anchor state before and after start, chunk, advance, error, stop, and rerender. This is a boundary with `conversation-scroll-anchoring`, not a modification of it.

### 7. Branch and rollout placement

Stage 1 belongs in the stable bottom-locking branch after the Stage 1 acceptance gate passes. Stage 2 sectionization/per-section controls stay in the experimental branch until boundary policies, replacement, queue, and browser/audio evidence pass. Optional pause/resume remains a future design, proposed rather than implemented, and cannot be used to claim either stage complete.

## Risks / Trade-offs

- [SSE chunks arrive after stop or replacement] → Abort the request, disconnect audio, and reject callbacks by generation and item identity.
- [Audio scheduling differs across browsers] → Keep the adapter narrow, test supported browser/audio combinations, and expose stop as the reliable initial control; do not promise pause/resume.
- [Long answers create expensive or noisy queues] → Build sections only for completed answers, omit empty sections, and cap/measure queue work in verification without changing source order.
- [Markdown semantics are ambiguous] → Record explicit policies for lists, code, tables, math, tool output, and partial content before Stage 2 promotion.
- [A new message appears while playback runs] → Keep identity-scoped queue entries; define replacement only through explicit user command, preventing accidental overlap.
- [Control rerenders move the conversation] → Maintain control layout and focus semantics, and run no-scroll assertions against all lifecycle transitions.
- [Existing narration capability is mistaken for shared transport] → Keep visualization-node narration as a separately documented boundary and test that it does not create a duplicate controller.
- [User loses control through automatic restart] → Never auto-restart after stop/error/replacement; require an explicit action and provide accessible status.

## Migration Plan

1. Audit the current `useTTS()` call sites, `/api/tts/stream` event decoding, existing message-level controls, visualization narration, stable message IDs, microphone/bottom layout, and keyboard/macro routing.
2. Implement and unit-test the controller and adapter behind Stage 1 feature placement; preserve the existing hook/API until the new boundary is verified.
3. Add Stage 1 bottom control and shared state projection, then run transport/error/accessibility/no-scroll browser checks.
4. Gate stable bottom-locking placement on the Stage 1 evidence matrix; keep rollback as removal/disablement of the new controller surface with the current single-session capability intact.
5. In the experimental branch, add completed-answer sectionization, explicit policies, ordered queueing, per-section controls, and stop-and-replace tests.
6. Only after browser/audio verification, separately decide whether a future pause/resume proposal is warranted.

Rollback is bounded to the frontend controller/surface integration and feature placement. It introduces no API migration, data migration, durable records, checkpoint changes, or changes to the linked OpenSpecs.

## Open Questions

- Which exact existing stable message ID field and TTS invocation payload should the adapter consume must be confirmed by the implementation audit; this does not alter the identity contract.
- Policies for lists, code, tables, math, tool output, and streaming partial content are intentionally unresolved design decisions and must be recorded before Stage 2 acceptance; they are not evidence for initial Stage 1 acceptance.
- Which browser/audio matrix is sufficient to consider pause/resume reliable is deferred until the adapter has real streamed PCM verification.
