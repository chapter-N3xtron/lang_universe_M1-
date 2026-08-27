# Phase_8_Native_streaming_and_reconnection

## Why

The Agent Server and Agent Chat UI need a native, durable streaming contract so authorized runs remain active across browser disconnects and users can reconnect without confusing checkpoint recovery with replay of missed events. The user-facing stream must remain Jasper-centric while exposing only deliberately approved, bounded Coder progress.

## What Changes

- Use durable Agent Server thread IDs and the Agent Chat UI's native `useStream` integration for Jasper conversations.
- Make active runs and thread streams resumable after browser disconnects through `reconnectOnMount` or a documented native equivalent, using `Last-Event-ID` where the selected transport supports event replay.
- Keep authorized autonomous work running when a browser stream disconnects; disconnection alone is not a cancellation request.
- Define checkpoint durability and event replay as separate guarantees, including explicit fallback behavior when replay is unavailable or its retention window has expired.
- Stream Jasper messages and a bounded allowlist of approved Coder progress events while deliberately enabling and filtering subgraph/custom events.
- Prevent raw Coder reports, internal reasoning, tool payloads, credentials, secrets, and other internal events from entering the user transcript.
- Keep the UI fixed to Jasper and enforce Coder access on the server rather than exposing Coder as a selectable assistant or trusting client-side filtering.
- Preserve the current approval-mode default and generic inferred-routing approval behavior unchanged.
- Add no dashboard and no speech-specific tests.

## Capabilities

### New Capabilities

- `native-run-stream-reconnection`: Native Agent Server and Agent Chat UI streaming, durable thread/run reconnection, safe event projection, and disconnect semantics.

### Modified Capabilities

- None.

## Impact

Implementation will affect the Jasper Agent Server run/thread streaming boundary, Agent Chat UI stream configuration and transcript projection, server-side assistant authorization, and focused streaming/reconnection tests. It may use existing LangGraph/LangSmith Agent Server and SDK transport features, but excludes MCP, persistence-schema changes, Coder report-schema changes, broad UI redesign, deployment acceptance, dashboards, and speech tests.
