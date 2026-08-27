# Phase_4_Agent_Server_PostgreSQL_authority

## Why

Jasper and Coder currently risk split-brain conversation state because deployed Agent Server checkpoints can coexist with an orphaned Coder persistence manager and other orchestration state. The deployed Agent Server PostgreSQL checkpointer must become the sole durable authority for conversation threads and inner graph execution so restart and concurrency behavior are deterministic.

## What Changes

- Make the deployed Agent Server PostgreSQL checkpointer the sole authority for Jasper/Coder conversation thread state and all inner-run checkpoints.
- Require top-level Jasper and standalone Coder graphs to compile without application-supplied concrete savers or stores, allowing Agent Server runtime injection; require nested Coder execution to inherit the parent checkpointer rather than create or select another one.
- Retire production reads, writes, recovery, and arbitration through the orphaned Coder SQLite/PostgreSQL persistence manager while retaining its files and schema for Phase 9 deletion.
- Keep LangGraph Store as a separate long-term, cross-thread data boundary; checkpoints do not become a cross-session memory schema.
- Keep Redis limited to ephemeral signaling, coordination, and disposable delivery state; Redis cannot restore or arbitrate conversation or graph execution state.
- Constrain the Phase-2 Temporal bridge to outer workflow orchestration. Temporal may coordinate starts, retries, and correlation, but it cannot own, reconstruct, advance, or override the Agent Server inner execution cursor.
- Define authoritative behavior for process restart, same-thread concurrency, checkpoint progression, runtime identity propagation, and reconciliation when legacy or auxiliary systems disagree with Agent Server PostgreSQL.
- Exclude cross-session memory schema, MCP, UI reconnection, physical cleanup/deletion, and broad deployment acceptance.

## Capabilities

### New Capabilities

- `agent-server-session-persistence`: Defines Agent Server PostgreSQL checkpoint authority, graph checkpointer inheritance, restart and concurrency semantics, runtime identity, and reconciliation boundaries for Jasper/Coder sessions and inner runs.

### Modified Capabilities

- None. The repository has no existing main OpenSpec capability specifications.

## Impact

- Future implementation affects Jasper and Coder graph compilation, nested graph invocation, Agent Server deployment/runtime configuration, legacy Coder persistence call sites, Temporal bridge contracts, Redis usage, and focused persistence/concurrency tests.
- The change alters the production authority contract but does not authorize data deletion, Store schema design, UI reconnect behavior, MCP work, or broad deployed-system acceptance.
