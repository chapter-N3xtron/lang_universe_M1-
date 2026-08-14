# MessageScroller-only autonomous cycle report

## Status: UNVALIDATED

The adapted primitive is integrated into the rendered conversation viewport in `src/spikes/message-scroller-scenario.html`; it is not merely imported. The scenario and Chromium runner were added, but this cycle could not execute the runner from the isolated sandbox: the available shell resolves `/tmp/thread-behavior-spikes/message-scroller` to the main repository working directory, while the native isolated filesystem tools expose the candidate sandbox separately. Running the command would therefore risk testing or modifying the main worktree, which was explicitly forbidden.

No MessageScroller metrics are claimed. In particular, actual `scrollHeight`, per-turn placements, target tops, usable tops, drift, clipping, controls, duplicate count, and cancellation outcomes are **not available**. The 10-turn scenario is consequently unvalidated, not a success.

## Intended required run

```sh
cd /tmp/thread-behavior-spikes/message-scroller
node run-message-scroller.mjs > message-scroller-run.json
node run-message-scroller.mjs > message-scroller-run-repeat.json
```

The runner performs exactly ten sequential real textarea fills/submits, three delayed assistant deltas per turn, Markdown/layout growth, delayed resize/rerender, semantic completion and closure, one post-completion placement per turn, duplicate initiation content on odd turns with distinct generated IDs, hydration, boundary/clamp checks, and cancellation events for wheel, touch, keyboard, pointer, selection (scrollbar cancellation is covered by the viewport scroll listener where browser-generated events permit it). It emits JSON containing all requested per-turn fields and actual geometry.

## Implementation checks not run

Chromium scenario: not run. Repeat run: not run. TypeScript/build/format/diff checks: not run because this candidate contains no runnable package metadata in the native isolated view and shell execution cannot safely target it.

## Rollback

Only this isolated candidate contains cycle changes. Exact rollback path:

```sh
rm -rf /tmp/thread-behavior-spikes/message-scroller
```

No production code, OpenSpecs, `todos.json`, baseline/main worktrees, or existing evidence artifacts were modified.
