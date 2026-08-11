## Why

Live-browser scroll behavior is difficult to explain from automated assertions alone: a human needs to compare what was seen with the exact DOM, scroll, hydration, and streaming timeline that produced it. This change defines a deliberately manual, isolated smoke-test evidence bundle without turning production telemetry into a content archive, coupling it to the active scroll-anchoring work, or creating a deterministic replay harness.

## Current implementation status

A development implementation now exists in `agent-chat-ui`, but it is narrower than the original proposal. The capture API is installed only when the app is running in development and the URL contains `?manualScrollCapture=1`. The tester starts and stops it through the browser console; there is no visible human-facing control and no terminal launcher. The logger is local and in-memory, and stopping manually downloads a JSON event bundle and manifest. QuickTime recording remains an independent manual artifact.

`threadId` is accepted in session metadata and is included in message snapshots, but the tester must provide it explicitly (or explicitly expose it through the documented URL value). The implementation does not discover a thread ID from LangGraph Studio, React/app state, or another automatic integration.

## What Changes

- Document and maintain the implemented development-only, URL-gated manual capture API.
- Pair the downloaded JSON event bundle and manifest with a separately created screen recording when a tester supplies recording metadata.
- Retain rendered message content in this isolated artifact only after the browser confirmation; apply bounded, content-aware redaction and truncation before persistence in memory and again through the exposed redaction path before sharing.
- Capture correlated timestamps, scenario/session IDs, explicit thread/message IDs where supplied, observed content, anchor IDs and geometry, viewport and scroll metrics, DOM mutation summaries, user scrolls, reversible programmatic scroll diagnostics, resize observations, and visible UI-state snapshots.
- Keep the capability separate from `conversation-scroll-anchoring`, durable production interaction records, existing Playwright checks/artifacts, and any deterministic replay harness.
- Record the remaining work explicitly: a visible frictionless UI, terminal launcher, automatic thread-ID discovery, robust artifact deletion/retention, and full automated browser/deletion validation.

## Related change

`../conversation-scroll-anchoring/` is the companion behavior change. That change defines the conversation scroll behavior under test; this change defines optional, human-centered evidence capture used to observe and report that behavior. Observation does not implement, alter, or prove anchoring behavior.

## Capabilities

### New Capabilities

- `manual-scroll-observation-capture`: Human-controlled, opt-in capture bundles for diagnosing observed conversation scrolling and related rendering transitions.

### Modified Capabilities

- None. The active `conversation-scroll-anchoring` change is referenced as an observation subject only; its requirements are not changed.

## Impact

Implemented files are `agent-chat-ui/src/lib/manual-scroll-observation.ts`, `agent-chat-ui/src/components/manual-scroll-observation-activation.tsx`, `agent-chat-ui/src/app/layout.tsx`, and `agent-chat-ui/docs/manual-scroll-observation-capture.md`. The implementation is development-only and does not add production telemetry, upload, dashboard, PM workflow, or replay behavior. OpenSpec artifacts describe the current partial implementation and its uncompleted safeguards rather than claiming the originally envisioned UI or automated artifact lifecycle exists.
