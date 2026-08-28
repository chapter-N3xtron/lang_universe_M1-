# Phase 2 Coder Temporal execution

## Why

The authoritative Coder graph needs durable, independently runnable execution for unattended coding operations. The previously proposed Temporal Activity-to-Agent-Server bridge cannot meet its lost-response idempotency requirement because the supported Agent Server API does not accept a caller-assigned run ID.

Temporal's official LangGraph plugin avoids that unsupported cross-runtime bridge by running the Coder graph through Temporal Workflows and Activities. The user has explicitly chosen this public-preview plugin approach.

## What Changes

- Adopt Temporal's official public-preview LangGraph plugin for the authoritative Coder graph.
- Preserve one authoritative Coder graph definition while exposing its uncompiled `StateGraph` builder to the plugin and retaining the compiled form used by the supervisor.
- Preserve the supervisor's existing ability to route to and run Coder as a subagent.
- Register Coder under one stable internal Temporal graph name and execute its side-effecting Coder node as a Temporal Activity.
- Make Temporal authoritative for workflow identity, scheduling, retry policy, timeouts, cancellation, and durable task results.
- Use a stable operation identity as the Temporal Workflow ID and as Coder's stable `thread_identity` across retries.
- Keep Jasper as the only product-facing Agent Server graph; do not independently register Coder with Agent Server.
- Remove the unsupported Agent-Server run/thread correlation, authorization, reattachment, cancellation, and reconciliation work from this change.
- Keep product UI, Jasper routing, persistence implementation, MCP, and deployment outside this change.

## Capabilities

### New Capabilities

- `temporal-coder-execution`: Runs the authoritative Coder graph as an internal Temporal Workflow through the official LangGraph plugin.

### Modified Capabilities

- None.

## Impact

Future implementation affects Coder graph construction, backend dependencies, a Temporal Workflow and worker registration, internal invocation contracts, and focused tests. It does not add a product-visible agent, change Jasper behavior, add an Agent Server Coder registration, implement a custom HTTP bridge, change persistence, add MCP, or deploy the Temporal service.
