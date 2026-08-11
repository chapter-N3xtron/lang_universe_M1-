## Purpose

Provides a development-only, human-centered smoke-test evidence bundle that correlates what a tester saw with browser-observed scroll, rendering, and conversation state. It is not production telemetry, a replay harness, or proof that the active scroll implementation is correct.

## Companion behavior change

Review `../../conversation-scroll-anchoring/` whenever this capability is opened or implemented. Capture observes that behavior without changing its runtime decisions.

## ADDED Requirements

### Requirement: Development-only URL-gated activation

The capability SHALL be a no-op in production and SHALL install its browser-console API only in development when the URL contains `manualScrollCapture=1`. Ordinary development without that query flag SHALL not install capture instrumentation.

#### Scenario: Capture is not activated
- **WHEN** the app is production, or development is opened without `?manualScrollCapture=1`
- **THEN** no capture API or instrumentation SHALL start

#### Scenario: Tester starts capture
- **WHEN** the tester calls `window.manualScrollObservation.start({ scenarioId, threadId })` and confirms the browser warning
- **THEN** an in-memory session with unique `session_id` SHALL begin; a non-empty scenario ID is required

### Requirement: Console-controlled local session

The current capability SHALL be controlled through the browser console API (`start`, `pause`, `resume`, `stop`, `discard`, `delete`, `setRecording`, `status`, and `redact`). It SHALL not claim to provide a visible human-facing control or terminal launcher. It SHALL remain opt-in, stoppable, and non-blocking to ordinary conversation use.

#### Scenario: Tester uses the current control surface
- **WHEN** the tester invokes a documented console method
- **THEN** only the local in-memory session is controlled and ordinary conversation remains usable

#### Scenario: Tester looks for a UI or terminal launcher
- **WHEN** the tester seeks a visible control or terminal command
- **THEN** the documentation SHALL identify both as unavailable current functionality rather than implying they exist

### Requirement: Explicit thread metadata

The session SHALL support `threadId` in capture options and message metadata. The tester SHALL supply it explicitly when thread correlation is needed; the implementation SHALL not automatically harvest it from LangGraph Studio, React/app state, network data, or model/provider internals. A URL `threadId` value is an explicit fallback, not discovery.

#### Scenario: Explicit thread ID is supplied
- **WHEN** the tester passes `threadId` to `start()` (or explicitly supplies the documented URL fallback)
- **THEN** message snapshots SHALL carry that value as thread metadata where available

#### Scenario: No automatic thread discovery exists
- **WHEN** no explicit thread ID is provided
- **THEN** the capture SHALL not claim to know the LangGraph Studio or app-state thread identity

### Requirement: Bounded observed event schema

The log SHALL be a versioned ordered event timeline with session/scenario IDs, sequence, monotonic elapsed time, wall-clock time, type, source, optional correlation ID, and payload. While active it SHALL support rendered message IDs/content, explicit thread IDs, anchor IDs, anchor geometry, viewport geometry, `scrollTop`, `scrollHeight`, DOM mutation summaries, user scrolls, reversible `scrollTo`/`scrollBy` diagnostics, resize observations, and visible UI-state snapshots. It SHALL cap events at 2,000 and each captured content string at 12,000 characters; unavailable values may be null. Hydration, streaming, fallback, error, recovery, and layout-settlement are currently represented only by observable snapshot fields (booleans or null where no detector exists), not a full lifecycle transition stream.

#### Scenario: Bounded observation is emitted
- **WHEN** an active session observes messages, scrolling, mutations, or resize
- **THEN** it SHALL append supported fields with correlated timestamps without exceeding the event or content bounds

#### Scenario: Transition is not directly observable
- **WHEN** hydration, recovery, or layout settlement has no installed detector
- **THEN** the snapshot SHALL use null or an explicitly unavailable field rather than fabricate a transition event

### Requirement: Confirmed content-aware local capture

Rendered message content SHALL be captured only after the start confirmation and only in the isolated in-memory session/download. Content SHALL be truncated and passed through denylist redaction before persistence/export. The capture SHALL exclude credentials, cookies, authorization headers, tokens, private keys, environment-file contents, network payloads, browser storage, unrelated page data, and internal model reasoning. Redaction is heuristic and requires review before sharing.

#### Scenario: Warning is declined
- **WHEN** the tester declines the browser confirmation
- **THEN** the session SHALL not start

#### Scenario: Sensitive-looking text is encountered
- **WHEN** captured text matches a configured private-key, bearer/basic credential, common secret/token/auth/cookie assignment, token query parameter, or selected environment-variable rule
- **THEN** the matching value SHALL be replaced with `[REDACTED]` and the event SHALL retain a redaction indication where applicable

### Requirement: Manual paired artifact handling

`stop()` SHALL finalize an in-memory manifest and event bundle and manually download `<session>.json` plus `<session>.manifest.json`. QuickTime remains a separate manually started/stopped artifact; optional recording metadata is attached through `setRecording`. The manifest SHALL identify local-only status, automatic-upload false, recording primitive/status, lifecycle, timestamps, event count, and review `null`.

The browser cannot delete files already placed in its Downloads folder. `discard()`/`delete()` clear the in-memory session before download but do not provide automated deletion or retention cleanup for downloaded files.

#### Scenario: Tester stops a session
- **WHEN** the tester stops an active or paused session
- **THEN** the browser SHALL download the JSON bundle and manifest, while QuickTime remains a separate manual artifact

#### Scenario: Tester discards before download
- **WHEN** the tester invokes `discard()` or `delete()` before stopping
- **THEN** in-memory events SHALL be cleared and no browser download SHALL be deleted by the page

### Requirement: Lifecycle and instrumentation boundaries

The API SHALL support active/paused/stopped/discarded lifecycle bookkeeping, stop/pause/resume/discard controls, bounded collection, and restoration of scroll hooks and observers on normal stop/discard cleanup. The manifest schema includes an error state, but error, navigation, and cancellation cleanup are not yet fully verified. It SHALL not alter active scroll behavior, production telemetry, durable interaction records, Playwright assertions, or create a replay/dashboard system.

#### Scenario: Session ends normally
- **WHEN** stop or discard runs
- **THEN** capture observers and reversible scroll hooks SHALL be restored and the lifecycle SHALL be recorded

#### Scenario: Cleanup failure path is exercised
- **WHEN** navigation, cancellation, or an instrumentation error interrupts capture
- **THEN** the artifacts SHALL report this path as unverified/partial until dedicated browser validation exists

#### Scenario: Active scroll implementation is exercised
- **WHEN** a smoke session observes conversation scrolling
- **THEN** capture SHALL observe without changing scroll decisions or claiming correctness

### Requirement: Validation and future work status

The current documentation SHALL distinguish implemented behavior from partial/unverified behavior and future work. Visible frictionless UI, terminal launch, automatic thread-ID discovery, automated deletion/retention cleanup, and full automated browser/deletion validation SHALL remain explicitly marked as future work or validation gaps.

#### Scenario: Reviewer audits implementation status
- **WHEN** a reviewer compares the artifacts with the coder implementation
- **THEN** the artifacts SHALL identify which requirements are implemented, partial/unverified, and future work without claiming missing controls or validation exist
