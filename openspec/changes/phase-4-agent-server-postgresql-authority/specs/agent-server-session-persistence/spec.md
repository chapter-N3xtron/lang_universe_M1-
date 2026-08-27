## Purpose

Defines one durable authority for Jasper/Coder conversation state and inner graph progress while preserving clear boundaries for long-term Store data and outer orchestration.

## ADDED Requirements

### Requirement: Agent Server PostgreSQL is the sole checkpoint authority
In a deployed Agent Server environment, the system SHALL use the Agent Server-managed PostgreSQL checkpointer as the sole durable authority for Jasper and Coder conversation thread state, checkpoint history, pending graph work, and the inner execution cursor. Application-owned databases, local files, Store records, Redis values, and Temporal workflow state MUST NOT arbitrate or replace that authority.

#### Scenario: An auxiliary system disagrees with PostgreSQL
- **WHEN** an auxiliary or legacy system contains state that differs from the latest committed Agent Server PostgreSQL checkpoint
- **THEN** the system continues from the PostgreSQL checkpoint and does not merge, prefer, or advance from the conflicting state

#### Scenario: Authoritative persistence is unavailable
- **WHEN** a run cannot read or durably commit its required Agent Server PostgreSQL checkpoint
- **THEN** the run fails or remains non-terminal without reporting durable success and without falling back to another persistence system

### Requirement: Runtime-managed top-level graph persistence
Top-level Jasper and standalone Coder graphs SHALL be compiled without an application-supplied concrete checkpointer or concrete Store. In deployed execution, Agent Server SHALL supply the runtime-managed checkpointer and, where needed, the separately configured Store.

#### Scenario: Agent Server loads a top-level graph
- **WHEN** Agent Server loads Jasper or standalone Coder for deployed execution
- **THEN** the graph accepts runtime-managed persistence without constructing, selecting, or embedding an application-owned saver or Store

#### Scenario: A top-level graph is inspected for custom persistence
- **WHEN** the deployed top-level graph construction paths are validated
- **THEN** no concrete SQLite, PostgreSQL, in-memory, or other custom saver or Store instance is attached by application graph code

### Requirement: Nested Coder inherits parent checkpoint authority
Coder invoked as a nested graph within Jasper SHALL inherit the parent run's checkpointer and thread context. It MUST NOT create, attach, select, or directly address a second checkpointer, and its checkpoints SHALL remain distinguishable within the parent thread's nested checkpoint lineage.

#### Scenario: Jasper invokes nested Coder
- **WHEN** Jasper enters the nested Coder graph
- **THEN** Coder executes under the same Agent Server thread and inherited checkpointer with a nested checkpoint namespace or lineage managed by the graph runtime

#### Scenario: Nested Coder resumes after interruption
- **WHEN** a Jasper thread resumes from a committed checkpoint inside or adjacent to nested Coder execution
- **THEN** the runtime derives Coder's resumable position from the inherited parent checkpoint lineage rather than a Coder-owned persistence manager

### Requirement: Restart recovery uses the latest committed checkpoint
After an Agent Server process or worker restart, the system SHALL recover a Jasper or Coder thread from its latest valid committed PostgreSQL checkpoint. Work after that commit SHALL be treated as uncommitted and permitted to re-execute; state from Redis, Temporal, process memory, or the legacy Coder manager MUST NOT be used to infer a later cursor.

#### Scenario: Worker stops after a checkpoint commit
- **WHEN** a replacement worker resumes the same thread after the prior worker stopped
- **THEN** execution continues from the latest committed Agent Server PostgreSQL checkpoint without requiring the prior process or its local state

#### Scenario: Worker stops before a checkpoint commit
- **WHEN** a worker performs work but stops before the resulting checkpoint is durably committed
- **THEN** recovery starts from the preceding committed checkpoint and does not claim the uncommitted step as completed

### Requirement: Same-thread concurrency has one ordered writer
The system SHALL preserve one authoritative ordered checkpoint progression for each thread. Concurrent mutating runs for the same thread MUST be serialized by the Agent Server runtime or one MUST receive an explicit busy/conflict outcome; they MUST NOT both advance independent cursors or resolve by silent last-write-wins. Runs for different threads SHALL remain independently executable.

#### Scenario: Two requests mutate one thread concurrently
- **WHEN** two requests attempt to advance the same Jasper or Coder thread at overlapping times
- **THEN** Agent Server serializes them against one checkpoint lineage or rejects one explicitly before it creates a competing lineage

#### Scenario: Two different threads run concurrently
- **WHEN** requests advance distinct thread identifiers
- **THEN** same-thread ordering requirements do not force those threads into a shared execution lock

### Requirement: Checkpoint progression is monotonic and commit-based
Every successful state transition SHALL derive from the authoritative thread's accepted checkpoint lineage and SHALL become resumable only after its successor checkpoint is durably committed. Retries SHALL resume or deduplicate against that lineage and MUST NOT manufacture progress from an outer retry count, signal sequence, or legacy revision.

#### Scenario: A step reports a result before its checkpoint commits
- **WHEN** durable checkpoint commit for the state transition fails
- **THEN** the transition is not treated as resumable committed progress and the run does not report authoritative completion for it

#### Scenario: An invocation is retried
- **WHEN** an outer caller retries an invocation with the same authoritative thread identity
- **THEN** Agent Server determines the next inner action from the committed checkpoint lineage rather than restarting from an auxiliary cursor

### Requirement: Runtime identity is stable and bounded
The Agent Server thread identifier SHALL be the durable conversation and checkpoint identity for a Jasper or standalone Coder session. A nested Coder invocation SHALL retain that thread identifier and use runtime-managed nested lineage identity. Run, attempt, correlation, Temporal workflow, and Redis signal identifiers SHALL remain bounded metadata and MUST NOT substitute for, remap, or independently advance the thread's execution identity.

#### Scenario: Identity is propagated into nested execution
- **WHEN** Jasper invokes Coder within a thread
- **THEN** the invocation preserves the Agent Server thread identifier and correlation context while the runtime assigns the nested checkpoint lineage

#### Scenario: A caller presents conflicting identities
- **WHEN** a request or resume attempt maps one run to inconsistent thread identities across its Agent Server and bridge metadata
- **THEN** the system rejects or quarantines the attempt without reading from or writing to an ambiguous checkpoint lineage

### Requirement: Legacy Coder persistence is retired from production authority
Production Jasper and Coder paths SHALL NOT read, write, dual-write, recover from, compare-and-select, or reconcile through the orphaned Coder SQLite/PostgreSQL persistence manager. Its physical files, tables, and implementation MAY remain inert until Phase 9 cleanup, and their presence MUST NOT imply operational authority.

#### Scenario: Legacy state exists for an active thread
- **WHEN** a legacy Coder persistence record exists for a thread that also has Agent Server checkpoints
- **THEN** production execution ignores the legacy record and uses only Agent Server PostgreSQL for checkpoint decisions

#### Scenario: Only legacy state exists
- **WHEN** a requested Agent Server thread has no authoritative PostgreSQL checkpoint but matching legacy Coder state exists
- **THEN** the system reports the authoritative thread as absent or non-resumable and does not silently import or resume the legacy state

### Requirement: Store remains a separate long-term data boundary
LangGraph Store SHALL remain separate from checkpoint persistence and SHALL be the boundary for approved long-term data intended for access across threads. Store data MUST NOT determine the inner execution cursor, substitute for missing checkpoints, or be treated as conversation-thread state. This capability SHALL NOT define a cross-session memory schema.

#### Scenario: A run accesses long-term data
- **WHEN** Jasper or Coder needs approved cross-thread long-term data
- **THEN** it accesses the separately configured Store without changing which system authoritatively resumes the current thread

#### Scenario: A checkpoint is missing
- **WHEN** Store contains related long-term records but Agent Server PostgreSQL has no checkpoint for the requested thread
- **THEN** Store records are not used to reconstruct or invent the thread execution cursor

### Requirement: Redis is ephemeral signaling only
Redis SHALL be used only for ephemeral signaling, coordination, or disposable delivery state. Redis data MUST NOT be required to recover conversation state, checkpoint history, or the inner execution cursor, and loss or eviction of Redis data MUST NOT alter the committed PostgreSQL lineage.

#### Scenario: Redis is flushed during an interrupted run
- **WHEN** all Redis signal state is lost and the thread is resumed
- **THEN** durable recovery remains based on the Agent Server PostgreSQL checkpoint, with only ephemeral signals requiring recreation or redelivery

### Requirement: Temporal owns only outer orchestration
For the Phase-2 bridge, Temporal SHALL own outer workflow orchestration such as scheduling, retries, timeout policy, and correlation, while Agent Server SHALL exclusively determine and persist the inner graph execution cursor. Temporal MUST NOT copy checkpoints, model node-level progress as an alternate cursor, or direct Agent Server to a cursor derived from workflow history.

#### Scenario: Temporal retries Agent Server execution
- **WHEN** an outer Temporal workflow retries a timed-out or failed Agent Server invocation
- **THEN** it invokes Agent Server with the stable thread and bounded correlation or idempotency metadata and lets Agent Server resume from PostgreSQL

#### Scenario: Temporal history appears ahead of Agent Server
- **WHEN** Temporal workflow history records an attempted activity beyond the latest committed Agent Server checkpoint
- **THEN** the bridge treats the Agent Server checkpoint as authoritative for inner progress and does not advance it from Temporal history

### Requirement: Authority conflicts fail closed and are observable
The system SHALL reconcile authority by fixed precedence: valid Agent Server PostgreSQL checkpoint state wins, while all auxiliary state is non-authoritative. Missing, corrupt, ambiguous, or identity-conflicting authoritative state SHALL produce an explicit failure or quarantine outcome with identifiers and reason suitable for diagnosis; reconciliation MUST NOT silently merge payloads, choose the newest timestamp across systems, or mutate legacy data.

#### Scenario: PostgreSQL checkpoint data is invalid
- **WHEN** the authoritative checkpoint cannot be validated or unambiguously associated with the requested thread
- **THEN** execution does not continue and emits a diagnosable failure without falling back to legacy, Store, Redis, or Temporal state

#### Scenario: A non-authoritative record is newer
- **WHEN** an auxiliary record has a later timestamp or revision than the valid PostgreSQL checkpoint
- **THEN** reconciliation records or exposes the discrepancy as needed but neither selects that record nor mutates the authoritative cursor from it
