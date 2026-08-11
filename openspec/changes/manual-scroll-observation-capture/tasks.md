## Cross-change review reminder

Review `../conversation-scroll-anchoring/` as well. This change observes that behavior and does not implement it.

## 1. Implemented reconnaissance and capture boundary

- [x] 1.1 Confirm the implementation target and existing message/anchor identifiers without changing active scroll behavior.
- [x] 1.2 Establish the current recording boundary: QuickTime is started/stopped manually; the browser only accepts optional metadata and downloads JSON/manifest artifacts.
- [x] 1.3 Implement a named scenario requirement and browser confirmation warning before content-bearing capture.
- [x] 1.4 Gate activation to development plus `?manualScrollCapture=1`; keep production and ordinary development as no-ops.

## 2. Implemented structured observation log

- [x] 2.1 Implement the v1 manifest and event envelope with scenario/session IDs, sequence, monotonic and wall-clock timestamps, artifact links, lifecycle, recording status, and finalization error.
- [x] 2.2 Capture rendered message/thread metadata (thread ID supplied explicitly), content, anchors, geometry, viewport, `scrollTop`, `scrollHeight`, and visible UI state.
- [x] 2.3 Capture user scroll, bounded mutation summaries, resize observations, and reversible `scrollTo`/`scrollBy` before/after metrics.
- [x] 2.4 Represent observable streaming/fallback/error state in snapshots; document hydration/recovery/layout-settlement as unavailable/null where no detector exists.
- [x] 2.5 Bound the session to 2,000 events and 12,000 characters per captured content string.

## 3. Implemented privacy and separation boundaries

- [x] 3.1 Apply heuristic denylist redaction/truncation before in-memory persistence and expose the same redaction path for review/export; exclude credentials, cookies, auth headers, tokens, private keys, environment files, network payloads, storage, and model reasoning.
- [x] 3.2 Keep artifacts local-only by default, prevent automatic upload, and preserve ordinary conversation behavior when capture is disabled or declined.
- [x] 3.3 Keep QuickTime, durable interaction records, Playwright artifacts, production telemetry, and active scroll decisions separate.

## 4. Current manual handoff

- [x] 4.1 Document console commands for one named scenario, explicit thread ID, optional QuickTime metadata, stop/download, timeline alignment, and observed-versus-inferred interpretation.
- [x] 4.2 Document manifest schema, file names, lifecycle, local/in-memory behavior, and the fact that browser downloads cannot be deleted by the page.
- [x] 4.3 Preserve `review: null`; no model review, upload, or automated interpretation is enabled.

## 5. Partial implementation and validation work remaining

- [ ] 5.1 Add a visible, frictionless human-facing control instead of requiring the browser console.
- [ ] 5.2 Add or explicitly reject a terminal launcher design.
- [ ] 5.3 Add safe automatic thread-ID discovery from an approved app integration; do not infer it from network/provider data.
- [ ] 5.4 Implement deletion/retention cleanup for downloaded artifacts and temporary fragments where browser permissions allow, with failure reporting.
- [ ] 5.5 Verify all instrumentation and recording resources are stopped/restored on pause, cancellation, navigation, and errors.
- [ ] 5.6 Run isolated human/browser scenarios and automated checks covering required event categories, timing correlation, redaction, deletion limitations, and non-interference with scroll behavior.
