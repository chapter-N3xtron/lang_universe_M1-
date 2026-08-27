## Context

See `proposal.md` for motivation and `specs/agent-server-session-persistence/spec.md` for normative behavior. The deployed architecture has an Agent Server PostgreSQL checkpointer, application graph construction paths capable of attaching concrete persistence, an orphaned Coder SQLite/PostgreSQL manager, Redis-backed signaling, and a planned Phase-2 Temporal bridge. Without an explicit ownership model, each can appear to be a recovery source.

Agent Server's runtime is the only layer positioned to order checkpoint writes and resume inner LangGraph execution across workers. A LangGraph Store serves a different lifetime and access pattern: long-term data can cross thread boundaries, whereas checkpoints describe one thread's execution lineage. Temporal operates one level above Agent Server and can durably retry an invocation, but cannot safely infer node-level completion from activity history.

## Goals / Non-Goals

**Goals:**

- Establish a single deployed checkpoint injection path controlled by Agent Server.
- Keep top-level graph definitions portable and free of application-owned concrete persistence resources.
- Preserve one checkpoint lineage through Jasper and nested Coder execution.
- Make restart, retries, same-thread contention, identity propagation, and authority conflicts deterministic and testable.
- Disable production behavior of the legacy Coder persistence manager without deleting its implementation or data.
- Preserve explicit lifetime boundaries among checkpoints, Store, Redis, and Temporal.

**Non-Goals:**

- Designing Store namespaces, schemas, retention, or cross-session memory behavior.
- Implementing MCP, UI stream reconnection, or browser hydration.
- Deleting legacy manager code, files, tables, dependencies, or migration assets; Phase 9 owns physical cleanup.
- Defining broad deployment, backup/restore, disaster-recovery, scale, or end-to-end acceptance criteria.
- Moving the Agent Server inner execution cursor into Temporal or adding a second checkpoint database.

## Decisions

### 1. Agent Server injects persistence into persistence-neutral top-level graphs

Jasper and standalone Coder graph factories will return graphs compiled without an application-created concrete saver or Store. The deployed Agent Server will bind its PostgreSQL checkpointer and separately configured Store through its supported runtime lifecycle. Graph import and construction must not open persistence connections or choose persistence from application environment variables.

This avoids duplicate connection pools, schema ownership, and saver lifecycles inside graph modules, and ensures every worker uses the same deployment authority. A custom application-level PostgreSQL saver was rejected because sharing a database engine does not guarantee sharing Agent Server's checkpoint namespace, ordering, or lifecycle. In-memory savers remain suitable only where an explicit non-deployed test harness supplies them; they are not a production fallback.

### 2. Nested Coder uses parent checkpointer inheritance

When Coder is embedded in Jasper, it will be compiled/configured as an inheriting subgraph rather than with a concrete saver. The parent thread identifier remains stable, while the LangGraph runtime's nested checkpoint namespace/lineage distinguishes Coder state. Application code will not derive a second Coder thread ID for the same nested execution or call the legacy manager around subgraph entry and exit.

Giving nested Coder a dedicated saver was rejected because it introduces a second commit boundary: Jasper could commit delegation while Coder does not, or vice versa. Passing parent state manually into a separately persisted Coder run was also rejected because it loses atomic lineage and makes restart reconciliation application-specific.

### 3. Thread identity names durable state; other identifiers correlate attempts

The Agent Server `thread_id` is the durable identity used to locate a Jasper conversation or standalone Coder thread. Nested Coder preserves that `thread_id`; runtime-managed checkpoint namespaces identify its position in the parent graph. An Agent Server run ID identifies an invocation/attempt, while Temporal workflow/activity IDs, request idempotency keys, and Redis message IDs are correlation metadata only.

Boundary adapters will validate that a resume or retry's declared thread identity agrees with its persisted/correlated mapping. They will fail closed on mismatch rather than remap based on timestamps, payload similarity, or a legacy session ID. This design rejects using a Temporal workflow ID as the checkpoint key because workflows and attempts can be retried, continued, or replaced independently from the conversation lifetime.

### 4. PostgreSQL commits define restartable progress

Only a checkpoint acknowledged as durably committed by Agent Server is resumable progress. After process loss, Agent Server reads the latest valid committed checkpoint for the stable thread and lets the graph runtime resolve pending work and nested position. Side effects after the prior commit may require existing idempotency controls when replayed; this phase does not claim exactly-once external effects.

A run must not report authoritative terminal success when its required final checkpoint commit failed. Process memory, emitted stream events, Redis delivery state, Temporal activity completion, and legacy Coder rows cannot prove a later cursor. Selecting the record with the newest timestamp was rejected because clocks and commit scopes differ and doing so creates split-brain recovery.

### 5. Same-thread mutation follows Agent Server ordering

All mutating invocations use Agent Server's thread/run concurrency controls. The chosen externally visible policy may queue/serialize contenders or return an explicit busy/conflict result, but it must produce one accepted checkpoint lineage and must not use silent last-write-wins. The bridge must not bypass this policy by creating a second identity for a retry. Different thread IDs remain independently schedulable.

An application Redis lock was rejected as the authority mechanism because lock eviction, partition, or restart could permit two writers and because Redis cannot validate checkpoint ancestry. Temporal workflow-ID uniqueness alone was rejected because calls can originate outside that workflow and Agent Server must defend its own thread boundary.

### 6. The legacy Coder manager becomes inert before deletion

Production graph and bridge paths will stop initializing and calling the orphaned Coder SQLite/PostgreSQL manager for reads, writes, dual-writes, cursor comparison, or recovery. Existing implementation, configuration artifacts, schemas, and data remain untouched so Phase 9 can remove them under a dedicated cleanup and rollback review.

No automatic data import is part of this phase. If a requested thread has only legacy state, the system reports that no authoritative Agent Server thread is resumable. Dual-write migration was rejected because it prolongs ambiguity, creates partial-write reconciliation, and contradicts the sole-authority goal.

### 7. Store, Redis, and Temporal have non-overlapping roles

- **Store:** runtime-managed long-term data boundary that may be queried across threads. It is injected separately from the checkpointer and never reconstructs a missing cursor. Schema and memory policy are deferred.
- **Redis:** ephemeral signal, wake-up, coordination, or disposable delivery state. Its contents may be lost and recreated; no checkpoint or conversation recovery depends on them.
- **Temporal:** durable outer orchestration for scheduling, retries, timeouts, and correlation. A Temporal retry calls Agent Server using the stable thread identity and lets Agent Server decide whether to resume, reject contention, or report terminal state. Temporal history may record an attempted activity but does not model LangGraph nodes or checkpoint payloads.

Duplicating checkpoint summaries into any of these systems for failover was rejected. Bounded correlation identifiers and terminal status references are allowed because they locate or explain work without becoming an alternate cursor.

### 8. Reconciliation is precedence-based, not data-merging

Authority checks follow a fixed matrix:

| Condition | Action |
|---|---|
| Valid Agent Server checkpoint exists; auxiliary state agrees or is absent | Resume from Agent Server PostgreSQL |
| Valid Agent Server checkpoint exists; auxiliary state differs or appears newer | Resume from Agent Server PostgreSQL; emit bounded discrepancy diagnostics if applicable |
| No Agent Server checkpoint exists; legacy/Store/Redis/Temporal state exists | Report absent/non-resumable authoritative thread; do not import |
| Agent Server checkpoint is corrupt, ambiguous, or bound to conflicting identity | Fail or quarantine; do not fall back |
| PostgreSQL is unavailable or commit fails | Keep run non-terminal/failed; do not claim durable success |

Diagnostics should include thread, run/correlation identifiers, authority source, operation, and reason without copying checkpoint payloads or secrets. Reconciliation does not mutate or delete legacy records.

## Risks / Trade-offs

- **[Risk] Existing sessions persisted only by the legacy manager stop resuming** → Make the authority cutover explicit, fail with a diagnosable non-resumable result, and require any future import to be separately designed and authorized.
- **[Risk] Removing graph-owned savers exposes tests that relied on implicit persistence** → Require test harnesses to inject an explicit test checkpointer/Store and add construction tests proving deployed graph factories remain persistence-neutral.
- **[Risk] Nested checkpoint namespaces or inheritance differ across the pinned LangGraph version** → Verify supported inheritance behavior with a focused nested interrupt/restart test before cutover; do not emulate inheritance through a second saver.
- **[Risk] A Temporal retry overlaps a still-running Agent Server run** → Preserve the same thread identity and handle the result through Agent Server's serialize-or-conflict contract rather than inventing a new thread.
- **[Risk] Replay after process loss repeats external side effects completed after the last commit** → Keep side-effect idempotency and result recording aligned with existing graph checkpoint boundaries; do not promise exactly-once effects in this phase.
- **[Trade-off] Fixed authority can discard apparently newer auxiliary state** → Prefer deterministic, auditable recovery over timestamp-based merging; surface discrepancies for operators without advancing from them.
- **[Trade-off] Leaving legacy assets physically present can confuse maintainers** → Mark configuration and code paths inactive and cover non-use with focused tests; defer deletion strictly to Phase 9.

## Migration Plan

1. Inventory deployed Jasper, standalone Coder, nested Coder, bridge, and startup paths that construct or call savers, Stores, or the legacy manager; establish focused tests that expose current authority choices.
2. Make top-level graph construction persistence-neutral and configure nested Coder for parent inheritance. Verify Agent Server supplies PostgreSQL checkpoints and a separate Store at runtime.
3. Remove production calls and initialization for the legacy Coder manager without deleting its code, configuration definitions, schema, or data.
4. Update Redis and Phase-2 Temporal bridge boundaries so only stable thread identity and bounded attempt/correlation metadata cross them; remove any inner-cursor inference.
5. Run focused restart, nested-resume, commit-failure, same-thread contention, identity-conflict, Redis-loss, Temporal-retry, and legacy-disagreement tests.
6. Cut over only after those focused checks demonstrate one PostgreSQL lineage. Broad deployment acceptance remains assigned to later phases.

Rollback restores the previous application paths only as an operational code rollback; it MUST NOT merge or backfill PostgreSQL from Redis, Temporal, Store, or legacy records automatically. Any rollback that would re-enable the legacy manager as production authority requires an explicit split-brain review and a defined single-writer boundary. Preserve all PostgreSQL and legacy data during rollback.
