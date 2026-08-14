# Spike B — MessageScroller-style adapter

`MessageScroller` is not an installable package in this repository or dependency graph. This is explicitly an **adapted source-pattern prototype**, not an official shadcn/UI package. It models the documented primitive pattern: scroll viewport + content ref + imperative `scrollToBottom` + user-interaction cancellation + ResizeObserver.

Native coverage: none of the Agent Chat/LangGraph lifecycle; adapter supplies generic bottom-stickiness, resize observation, and human cancellation. It does not solve semantic completion or duplicate identity by itself.

This cycle adds `src/spikes/message-scroller-scenario.html`, a self-contained rendered conversation prototype. The adapted primitive is instantiated around the actual `#viewport`/`#content` conversation DOM and owns ResizeObserver bottom-stickiness, imperative anchor placement, clamping, and cancellation listeners. The harness models semantic completion only after three delayed deltas, delayed Markdown/layout growth, and stream closure; placement is called exactly once after completion per turn. It is intentionally an adapted source-pattern prototype, not an installable package.

`run-message-scroller.mjs` is the Chromium-backed 10-turn runner. It uses real textarea fills and button clicks, records IDs, target tops, usable tops, scroll geometry, drift, clipping, duplicate count, boundaries, hydration, and cancellation outcomes. It must be run from this sandbox with `node run-message-scroller.mjs` (requires Playwright).

Rollback: `rm -rf /tmp/thread-behavior-spikes/message-scroller` (isolated sandbox only).
