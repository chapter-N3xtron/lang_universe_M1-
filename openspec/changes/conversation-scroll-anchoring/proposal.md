## Why

The current conversation viewport does not reliably top-anchor newly inserted turns, and automated checks did not sufficiently verify the real browser visual behavior. This change records the unresolved state truthfully so the behavior is not treated as complete while live-browser investigation remains necessary.

## What Changes

- Record the observed failure for both newly submitted user messages and arriving assistant answers.
- Record that automated checks passed but were insufficient to establish the intended browser-visible behavior.
- Define the proposed one-shot positioning contract for new arrivals: after message insertion and layout settlement, position the new turn at the top once, then return full scroll control to the user without bottom-following.
- Define the proposed initial reopen contract separately: after a saved session/thread's hydrated message window is mounted, place a non-empty conversation at the bottom once so the latest saved content is visible; do not follow new processing or assistant reveal.
- Define empty-session, loading/error-history, fork/reopen, and reduced-motion outcomes, and reserve any future durable per-thread viewport position as an explicit override rather than inventing that feature.
- Keep implementation and live-browser verification explicitly pending until the arrival paths are observed in Chromium; focused application/test changes may be made only to investigate and satisfy this contract, without broadening into unrelated UI work.

## Related change

`../manual-scroll-observation-capture/` is the companion observation change. This change defines the conversation scroll behavior under test; the companion defines optional, human-centered evidence capture used to observe and report that behavior. They remain separate in scope: capture does not implement, alter, or prove the anchoring behavior. Whenever this change is opened or implemented, review the companion change as well, and prompt the same review in the opposite direction.

## Capabilities

### New Capabilities

- `conversation-scroll-anchoring`: Observed current behavior and proposed top-positioning contract for user-message and assistant-answer arrival paths.

### Modified Capabilities

- None.

## Impact

OpenSpec planning artifacts only under `openspec/changes/conversation-scroll-anchoring/`. No application code, tests, APIs, dependencies, credentials, permissions, or runtime behavior are changed.
