## Context

See `proposal.md` for motivation and `specs/native-run-stream-reconnection/spec.md` for the behavior contract. Jasper is the sole user-facing assistant, while Coder executes only through Jasper's server-authorized delegation path. The change crosses the graph runtime, Agent Server transport/auth boundary, and browser stream lifecycle. Native checkpoints can recover graph state, but they do not by themselves retain or replay every SSE/custom event.

The implementation must preserve the existing approval-mode default and generic inferred-routing approval behavior. It must also fit the existing conversation surface rather than add a run dashboard, and it cannot depend on persistence-schema or Coder report-schema changes.

## Goals / Non-Goals

**Goals:**

- Make one durable Agent Server thread ID the join key for Jasper history, submissions, active-run lookup, and reconnection.
- Use native Agent Chat UI `useStream` and Agent Server run/thread streaming rather than a second chat transport or browser-owned execution loop.
- Reattach safely to existing work after remount, reconcile replay gaps from authoritative state, and avoid duplicate submissions.
- Define a server-side public event projection that permits Jasper messages and bounded Coder progress without leaking internal subgraph data.
- Keep connection lifecycle, run lifecycle, checkpoint recovery, and event replay explicit and independently testable.

**Non-Goals:**

- No dashboard, assistant picker, activity center, or broad conversation redesign.
- No new database/persistence schema, Coder report schema, MCP behavior, or deployment acceptance work.
- No attempt to make transient progress an audit log or durable transcript.
- No speech-specific behavior or tests.

## Decisions

### 1. Use the native Agent Server thread and run lifecycle end to end

The browser will retain the conversation's Agent Server `thread_id` through the existing conversation identity mechanism and pass it to native `useStream`. A submission creates a run on that thread; remount uses `reconnectOnMount` where supported, or a documented SDK-equivalent active-run lookup and join sequence. Reconnection joins an existing run and never resubmits the prior input.

The browser is only a stream consumer. Closing an `EventSource`, aborting a fetch, navigating away, or losing the network detaches that consumer but does not call run cancellation. The existing explicit cancel action remains the only browser action mapped to cancellation, subject to existing server policy.

Alternatives considered:

- Keep a custom application SSE/WebSocket chat endpoint: rejected because it duplicates Agent Server lifecycle semantics and makes replay/cancellation behavior diverge.
- Restart from the latest checkpoint on every reconnect: rejected because an original run may still be active and a second run could duplicate side effects.
- Couple request cancellation to run cancellation: rejected because browser connectivity is not a durable expression of user intent.

### 2. Reconnect by identifiers, then reconcile against authoritative state

The client tracks `thread_id`, the native `run_id` when available, and the latest transport event cursor only for the lifetime/retention rules supported by Agent Server. On mount it follows this order:

1. Resolve and authorize the durable Jasper thread.
2. Ask the native client/server lifecycle whether an active or resumable run exists.
3. Attach to that run/thread stream with native reconnect support; pass `Last-Event-ID` when the selected SSE endpoint supports it.
4. If the run completed during the race, or replay is unavailable/expired, reload thread state and converge by stable message/run identifiers.
5. Never synthesize missed progress events or append replayed chunks as duplicate messages.

The implementation documentation will record which installed Agent Server/SDK endpoint honors `Last-Event-ID`, its retention limits if defined, and the equivalent native cursor option if the SDK owns the header. The UI will not advertise exact replay when only state reconciliation is available.

Alternatives considered:

- Treat `thread_id` alone as an event cursor: rejected because thread identity locates state but says nothing about the last delivered event.
- Build a new durable event-log table: rejected because persistence-schema work is out of scope and native replay/state reconciliation is sufficient for this phase.

### 3. Separate checkpoint recovery from event replay

A checkpoint is the authoritative resumable graph state used by Agent Server. Event replay is a transport capability over a bounded event history. The reconnection path uses each for its actual guarantee:

- If cursor replay succeeds, consume events after the acknowledged cursor and deduplicate by native event/message/run identifiers.
- If cursor replay cannot succeed, load current thread/run state from Agent Server and continue from there.
- Transient progress that fell outside the replay window may be absent; it is not reconstructed from checkpoints and never promoted into transcript history.

This distinction will be stated in operational comments/docs near reconnection configuration so future changes do not assume PostgreSQL checkpoints imply SSE event retention.

Alternative considered:

- Reconstruct all stream events by diffing checkpoints: rejected because checkpoints represent state snapshots, not an ordered, complete event log.

### 4. Expose a single server-controlled public stream projection

The Jasper run requests only the native stream modes needed by the UI: user-visible Jasper message streaming plus custom progress events. Subgraph streaming is configured deliberately rather than inherited accidentally. Raw subgraph message/state/tool modes remain disabled for the browser path unless they pass through the same server-side public projection.

Coder reports and Coder model/tool events remain internal graph data. For user-visible progress, authorized Coder execution emits or is mapped to a bounded custom event containing only public lifecycle information such as an opaque delegation/run correlation, a coarse phase/status, and a short sanitized summary. The public projection allowlists event kind and fields, applies size/rate bounds, and drops unknown fields and unknown event kinds before transport. Coder completion enters the transcript only after Jasper creates its contextual user-facing message.

`useStream` handles Jasper message chunks as transcript data and handles approved custom progress through a separate non-transcript activity callback/component already within the chat surface. Replayed progress is idempotently updated, not appended as chat. This does not create a dashboard.

Alternatives considered:

- Stream every subgraph event and hide unwanted entries in React: rejected because sensitive data would already have crossed the security boundary.
- Disable all progress: rejected because bounded approved Coder progress is part of the requested user experience.
- Put progress in assistant messages: rejected because transient execution telemetry would pollute durable conversation history and could expose raw reports.

### 5. Enforce Jasper and Coder boundaries on the server

The client is configured with the fixed Jasper assistant/graph and has no assistant selector. Server authorization validates the caller's access to every requested thread and run and denies direct Coder assistant/graph creation, joining, or streaming. Coder can execute only as a server-side subgraph/delegation reached through Jasper after existing authorization and approval logic.

Replay cursors and guessed IDs grant no authority: authorization occurs before history, active-run metadata, or stream events are returned. Client filtering remains defense in depth, not access control.

Alternative considered:

- Rely on a hidden Coder option and client-side route checks: rejected because clients can modify requests and subscribe directly.

### 6. Leave approval semantics outside stream state

Approval remains graph/run state governed by the existing default and generic inferred-routing rules. A stream connect, reconnect, replay cursor, or mount is observational and cannot approve or resume an interrupt. Reconnection renders a pending interrupt through the existing approval flow. An approval command remains explicit and idempotent under the existing mechanism.

Alternative considered:

- Auto-resume after reconnect when work was previously approved: rejected because it can collapse a later pending approval boundary and change current routing semantics.

## Risks / Trade-offs

- [Native SDK and Agent Server versions differ in reconnection options] → Pin/verify the installed compatible APIs and document the native equivalent when `reconnectOnMount` or cursor handling is named differently.
- [A reconnect races with run completion and causes duplicate work] → Join by server run identity, never resubmit on reconnect, then reconcile authoritative thread state.
- [Subgraph/model events leak before UI filtering] → Restrict stream modes and perform allowlist projection before browser transport; test forbidden payload canaries at the wire boundary.
- [A malformed custom progress event carries report or secret data] → Apply server-side event/field allowlists, size bounds, sanitization, and fail-closed behavior.
- [Replay duplicates chunks or transient status] → Deduplicate with native stable identifiers and reduce progress into keyed current status rather than transcript append operations.
- [Replay retention is shorter than user expectations] → Fall back to authoritative state, disclose the distinction in implementation docs, and avoid claims of complete event recovery.
- [Disconnected work consumes resources unexpectedly] → Preserve existing server-side timeout, interrupt, authorization, and explicit cancellation policies; do not invent connection-based cancellation.

## Migration Plan

1. Verify and pin the native Agent Server and Agent Chat UI SDK capabilities used for thread/run streaming, active-run attachment, reconnect-on-mount, and event cursor handling.
2. Add the server-side Jasper-only authorization and public event projection before enabling custom/subgraph data on the browser stream.
3. Replace the Jasper conversation's legacy/parallel stream wiring with native `useStream`, durable `thread_id`, and non-submitting reconnect logic behind the existing Jasper surface.
4. Add focused tests for active disconnect/reconnect, completion races, replay and state-reconciliation paths, explicit cancellation, approval interrupts, server authorization, and forbidden-event leakage.
5. Roll back by disabling the new browser reconnect configuration and restoring the prior Jasper stream adapter; do not cancel already authorized server runs during rollback. No schema migration is required.
