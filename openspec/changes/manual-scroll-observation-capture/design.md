## Context

This change observes the active conversation scroll implementation; it does not implement or validate that behavior. The current coder implementation is a small client-side diagnostic module, activated by `ManualScrollObservationActivation` in the root layout. It is installed only when `NODE_ENV !== "production"` and `?manualScrollCapture=1` is present.

The current surface is intentionally console-driven:

```js
window.manualScrollObservation.start({
  scenarioId: "reopen-stream-manual-scroll",
  threadId: "<explicit thread id>",
});
```

The browser confirmation is the content-capture consent boundary. There is currently no visible control, terminal command, automatic thread-ID discovery, or automatic screen recording.

## Goals / Non-Goals

**Goals:**

- Give a human smoke tester a bounded, time-correlated view of browser-observed events beside a manually recorded screen capture.
- Preserve rendered message content only inside an explicitly confirmed, isolated, local in-memory session and downloaded temporary artifact.
- Make the bundle useful for debugging without implying deterministic replay or production telemetry.
- Keep instrumentation active only for the session and restore patched browser methods on normal stop/discard cleanup; error, navigation, and cancellation cleanup remain unverified.

**Non-Goals:**

- No production metrics, analytics pipeline, dashboard, automatic upload, terminal launcher, or visible frictionless UI in the current implementation.
- No automatic harvesting of `threadId` from LangGraph Studio, app state, or network data.
- No capture of network payloads, browser storage, credentials, cookies, auth headers, tokens, private keys, environment files, or internal model reasoning.
- No modification of scroll anchoring, hydration, streaming, fallback, or message-rendering decisions.
- No reproduction engine, scripted input runner, headless-test replacement, assertion oracle, or automated video capture.

## Decisions

1. **Use a distinct in-memory session namespace.** Generate a scenario ID supplied by the tester and a unique session ID. The manifest records schema, lifecycle, timestamps, artifact names, local-only status, and recording metadata. A durable production ledger is out of scope.

2. **Use a bounded append-oriented event timeline.** Events contain session/scenario IDs, sequence, monotonic elapsed time, wall time, type, source, optional correlation ID, and payload. The implementation caps the timeline at 2,000 events and caps each captured content string at 12,000 characters. It emits session lifecycle, UI snapshot, user-scroll, DOM-mutation, resize, programmatic-scroll, and recording-metadata events; transition state is currently represented by observable boolean/null fields in snapshots, not by a complete transition event detector.

3. **Observe scroll calls through reversible diagnostic hooks.** While active, the module wraps `Element.prototype.scrollTo` and `scrollBy`, records requested arguments and before/after metrics, and restores both originals during cleanup. This is diagnostic instrumentation and must not become an active scroll implementation.

4. **Keep QuickTime independent.** The tester starts/stops QuickTime manually and may attach filename/path/start/end/notes through `setRecording`. The browser downloads only the JSON bundle and manifest on `stop()`; it does not create or control the movie. The manifest marks the recording as manual or not provided.

5. **Capture only rendered observation-boundary content.** Snapshots read `[data-message-id]` elements, rendered text, anchor IDs, bounding rectangles, viewport metrics, and visible UI state. The module does not inspect requests, responses, storage, cookies, headers, environment files, credentials, tokens, private keys, or model/provider internals. The denylist redacts private-key blocks, bearer/basic credentials, common secret assignments/query parameters, and selected environment-style assignments; content is truncated before those rules run.

6. **Use confirmation and manual lifecycle controls.** `start()` requires a non-empty scenario ID and `window.confirm()`. The console API supports `pause`, `resume`, `stop`, `discard`, `delete`, `setRecording`, `status`, and `redact`. `discard()` and `delete()` clear the in-memory events but cannot delete files already downloaded by the browser. There is no automated retention cleanup.

7. **Describe requirements by implementation state.** Local opt-in capture, bounded observation, redaction boundaries, manual download, and separation are implemented. Visible controls, terminal launch, automatic ID discovery, deletion of downloaded artifacts, retention cleanup, and full browser/deletion validation remain future or validation work.

## Risks / Trade-offs

- Message content can contain sensitive information despite warnings: confirmation, local-only default, bounded redaction, and explicit deletion instructions reduce but do not eliminate risk.
- Redaction is heuristic and not a guarantee; users must review temporary downloads before sharing.
- Video and log clocks can drift because QuickTime is independent; use manifest recording timestamps and event wall/monotonic timestamps as approximate correlation only.
- Instrumentation can affect timing; it is active only during capture and hooks are restored during cleanup, but automated proof is still outstanding.
- A diagnostic artifact can be mistaken for truth: label it observed evidence, not replay input or proof of anchoring correctness.

## Migration Plan

No migration or rollout occurs. The current implementation is gated out of production. Future work should add any UI/launcher only behind the same boundary, test disposable fixtures, and preserve the no-network/no-secret boundary.

## Open Questions / Future Work

- Whether and how to provide a visible human-facing start/stop control without making ordinary use noisy.
- Whether a terminal launcher is appropriate.
- A safe, explicit source for automatic thread-ID discovery.
- Browser-compatible deletion/retention handling for downloaded files and complete automated browser validation.
