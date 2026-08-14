## 1. Baseline and layout contract audit

- [x] 1.1 Review `agent-chat-ui/src/components/thread/message-list.tsx`, the human/assistant message shells, viewport wrapper, and relevant CSS to map hydration, submission, streaming, completion, controls, and all layout/control insets; document the authoritative measured usable content-top owner and remove the 32px assumption from the implementation plan.
- [x] 1.2 Review `../manual-scroll-observation-capture/` and the supplied observation evidence; record which claims are visual observation versus structured evidence, and keep this companion cross-reference explicit without changing the companion artifacts.
- [x] 1.3 Inventory visible shell/header, playback, command, branch, and loading-control geometry for human and completed assistant variants, including controls positioned outside the message body; define selectors/semantics for browser assertions.

## 2. Deterministic placement state machine

- [ ] 2.1 Implement per-thread/per-turn placement state that emits one request for the latest completed visible hydrated message, one for the submitted user message, and one replacement request for its completed assistant response; keep each request identity/generation idempotent across rerenders.
- [x] 2.2 Replace fixed-offset and invisible-anchor placement with measured usable-content-top geometry targeting the visible message shell/header; defer until valid layout geometry exists rather than guessing, and support a target taller than the viewport.
- [ ] 2.3 Implement precise programmatic-scroll bookkeeping so only the active placement's own scroll event is ignored; cancel pending work on wheel, touch/pointer, keyboard, scrollbar, selection/drag, and other human movement. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 2.4 Ensure streaming chunks, answer reveal, resize observers, rerenders, reduced-motion changes, and DOM/layout mutations cannot enqueue or repeat a consumed placement; preserve instant/no-animation destination semantics for reduced motion. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## 3. Focused browser verification

- [ ] 3.1 Extend the placement recorder/fixtures to capture semantic target identity and exact geometry at each automatic placement, including usable viewport top, shell/header top, target top content, and every required playback/command control rectangle.
- [ ] 3.2 Add hydration coverage asserting the latest completed visible message is placed exactly once, shell/header top equals the measured usable top, no header/top/control is clipped, and empty/loading/error histories do not place.
- [ ] 3.3 Add submission coverage asserting exactly one user placement and subsequent user scroll authority; include wheel, touch, keyboard, scrollbar, selection/drag, and synthetic human scroll cancellation cases. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [x] 3.4 Add a real assistant stream fixture that delivers multiple chunks after submission and then a semantic completion; assert no placement during chunks and exactly one replacement placement on the completed assistant shell/header with visible controls.
- [ ] 3.5 Add tall-response, reduced-motion, resize, rerender, answer-reveal, and layout-mutation cases asserting header/top visibility, exact usable-top alignment, and no repeated placement.

## 4. Validation and evidence

- [ ] 4.1 Run focused Playwright tests, typecheck/lint/format checks, and the relevant broader project commands; record pre-existing failures separately from regressions.
- [ ] 4.2 Run the companion `manual-scroll-observation-capture` workflow where appropriate and correlate its evidence with the automated results without treating capture as proof of geometry or completion.
- [ ] 4.3 Report hydration, submission, and assistant-completion results independently; do not mark this change complete while real assistant streaming/completion or any required geometry/cancellation case remains unresolved.
