## 1. Baseline and transport audit

- [ ] 1.1 Inventory `/api/tts/stream` base64 PCM SSE events, cancellation behavior, AudioContext lifecycle, and every current `useTTS()` call site; document the preserved API boundary and known browser assumptions.
- [ ] 1.2 Inventory stable assistant message identities, completed/streaming states, latest-answer selection, current message-level controls, visualization-node narration, microphone/bottom layout, and keyboard/macro routing; record boundaries without modifying related capabilities.
- [ ] 1.3 Define and record the Stage 2 Markdown policies for headings/paragraphs, lists, code, tables, math, tool output, and streaming partial content; unresolved policies must block Stage 2 promotion, not be silently assumed.

## 2. Shared controller and audio adapter

- [ ] 2.1 Define the ephemeral controller state, command interface, stable message/section identity model, queue item shape, and monotonic generation/session rules from the spec and design.
- [ ] 2.2 Implement the narrow adapter over the existing streamed PCM SSE/Web Audio path with start, completion, cancellation, and categorized error events; do not change Pocket TTS backend/API or add persistence.
- [ ] 2.3 Implement controller transitions for idle/start/playing/advance/stop/error, including one active item, ordered queue ownership, explicit stop, and safe cleanup of SSE/audio resources.
- [ ] 2.4 Implement generation and identity guards so stale completion, error, chunk, abort, and audio callbacks cannot mutate a replacement session or advance a cleared queue.
- [ ] 2.5 Implement new-message overlap and source-replacement rules so new identities do not enter an existing queue and old identities cannot affect new state.

## 3. Stage 1 stable bottom-locking surface

- [ ] 3.1 Add the bottom play/stop control beside the microphone for the latest completed non-empty assistant answer, with disabled/unavailable behavior for empty, loading, failed, or partial answers.
- [ ] 3.2 Connect existing message-level actions, where retained, to the shared controller without creating an independent audio session; keep visualization-node narration explicitly outside this controller.
- [ ] 3.3 Route documented keyboard and macro-key play/stop actions through the same controller, respecting text-entry focus, accessible names, status announcements, and explicit user intent.
- [ ] 3.4 Add Stage 1 feature placement and stable bottom-locking branch gate; do not promote until transport, error, accessibility/human-control, and no-scroll evidence passes.

## 4. Stage 2 experimental section playback

- [ ] 4.1 Implement completed-answer sectionization for the approved Markdown heading/paragraph policy, deterministic source order, whitespace handling, empty omission, and stable section IDs.
- [ ] 4.2 Add per-section controls and message-level whole-answer controls as projections of shared controller state; expose active, queued, stopped, and error states consistently.
- [ ] 4.3 Implement sequential whole-answer playback and exactly-once advancement for ordered speakable sections.
- [ ] 4.4 Implement section selection as stop-and-replace: cancel active audio, clear whole-answer queue, start only the selected section, and invalidate prior generations.
- [ ] 4.5 Keep lists, code, tables, math, tool output, and streaming partial behavior behind explicit documented policy decisions; block experimental acceptance for any unresolved boundary.

## 5. Scroll, focus, and human-control safeguards

- [ ] 5.1 Ensure playback lifecycle updates never call automatic conversation placement, mutate scroll containers, or interfere with the `conversation-scroll-anchoring` contract; keep `manual-scroll-observation-capture` as separate evidence only.
- [ ] 5.2 Preserve focus and scroll anchoring across bottom, message, and section control rerenders; add accessible state/status announcements without focus jumps or unexpected layout scroll.
- [ ] 5.3 Keep stop/cancel reliable and user-authoritative; do not auto-restart after stop, replacement, error, reload, or a stale callback.
- [ ] 5.4 Leave true pause/resume unimplemented unless a later browser/audio verification decision separately authorizes it; document any evidence without making it an initial gate.

## 6. Verification matrix

- [ ] 6.1 Add controller tests for empty answers, latest-answer selection, queue ordering, completion advancement, stop cancellation, replacement, repeated commands, new-message overlap, source replacement, and stale callbacks.
- [ ] 6.2 Add SSE/audio tests for base64 PCM decoding failures, unexpected stream close, abort/stop races, AudioContext failure, retry/error state, and cleanup of active/queued resources.
- [ ] 6.3 Add Stage 1 browser tests for bottom control, latest completed answer, keyboard/macro equivalence, accessible names/status, and stable-branch acceptance behavior.
- [ ] 6.4 Add Stage 2 browser tests for deterministic section IDs/order, per-section controls, whole-answer sequencing, section stop-and-replace, and unresolved block policies.
- [ ] 6.5 Add no-scroll tests around start, chunk arrival, section advance, replacement, errors, stop, rerender, and control updates at non-default conversation scroll positions; assert scroll anchoring remains unchanged.
- [ ] 6.6 Run focused tests plus available typecheck/lint/format/build commands, record pre-existing failures separately, and report Stage 1 stable versus Stage 2 experimental evidence without claiming pause/resume.
