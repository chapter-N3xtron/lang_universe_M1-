## Context

See `proposal.md` for motivation and `specs/conversation-scroll-anchoring/spec.md` for the distinction between observed behavior and the proposed contract. Automated checks passed, but they did not sufficiently establish the real browser-visible scroll behavior for either message-arrival path.

## Companion observation change

Review `../manual-scroll-observation-capture/` whenever this change is opened or implemented. It defines the optional human-centered evidence capture for observing and reporting this change's behavior under test; it does not implement or change the scroll contract. Review of both changes is required to preserve the implementation/observation boundary.

## Goals / Non-Goals

**Goals:**

- Keep the unresolved status explicit for both user-message and assistant-answer arrival.
- Validate the intended visual timing in a live browser after insertion and layout settlement.
- Preserve one-shot top positioning followed by full user scroll control, with no bottom-following.

**Non-Goals:**

- No broad application feature work is authorized; focused code and regression-test changes are limited to investigating and satisfying this scroll contract.
- No claim is made that the current implementation already satisfies the proposed contract.

## Decisions

1. Treat live-browser observation as the acceptance boundary for this visual interaction. Unit or automated checks can support the record, but cannot establish viewport positioning, layout settlement timing, or whether a later render reclaims scroll control.

2. Investigate the user-message and assistant-answer arrival paths separately. A result for one path must not be generalized to the other because insertion timing and rendered content growth may differ.

3. Define the desired new-arrival interaction as a one-shot top position after the new turn settles. Once that action occurs, subsequent user scrolling is authoritative and no bottom-following behavior is permitted.

4. Define the desired reopen interaction separately: after a saved session/thread's hydrated message window is mounted, place a non-empty history at the bottom once so the latest saved content is visible. This is not bottom-following during processing or assistant-answer reveal and must not reinstate removed bottom-lock behavior. Empty sessions have no message target; loading/error history states do not perform a misleading placement until hydration succeeds; forked/reopened threads use the same default unless a future explicitly saved per-thread viewport position overrides it. Reduced motion changes animation (instant/no animation), not the destination or one-time/user-control semantics.

## Risks / Trade-offs

- [A passing automated check masks a browser-only timing failure] → Keep the implementation pending until both live-browser paths are observed.
- [Assistant content growth triggers repeated repositioning] → Verify behavior after layout settlement and after the user begins scrolling.
- [A fix for one arrival path leaves the other unresolved] → Report and investigate user-message and assistant-answer paths independently.
