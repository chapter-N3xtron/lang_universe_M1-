## Purpose

Provides a durable, reconstructible user-visible record of sessions and interactions while keeping graph execution authoritative in LangGraph checkpoints and avoiding a second interaction ledger.

## ADDED Requirements

### Requirement: Durable interaction record model
The system SHALL persist user-visible interaction structure in LangGraph Store using separate records for `session`, `branch`, `turn`, `user_container`, `assistant_container`, and `attempt`. A turn SHALL identify its session, branch, parent turn when applicable, user and assistant container IDs, active attempt ID, lifecycle status, timestamps, and schema version. Containers SHALL be siblings, not nested message-role aliases: the user container holds the submitted input and the assistant container holds the corresponding visible response/projection.

#### Scenario: Reopen a completed turn
- **WHEN** a client loads a completed turn by session and branch
- **THEN** it can resolve the sibling user and assistant containers, active attempt, status, and ordered references without reading a PostgreSQL interaction ledger

#### Scenario: Turn has multiple attempts
- **WHEN** a turn is retried or regenerated
- **THEN** the turn retains all attempt identities and marks exactly one attempt as active/current while preserving prior attempt outcomes

### Requirement: Deterministic namespaces, keys, and envelopes
Every Store record SHALL use deterministic namespaced keys derived from local-owner scope and immutable IDs: `lgsm/{owner_id}/session/{session_id}`, `branch/{branch_id}`, `turn/{turn_id}`, `container/{container_id}`, `attempt/{attempt_id}`, `run/{run_id}`, `checkpoint/{checkpoint_id}`, `message/{message_id}`, `tool_call/{tool_call_id}`, `artifact/{artifact_id}`, `artifact_revision/{artifact_id}/{revision_id}`, `playback/{segment_set_id}`, `event/{event_id}`, and `reconciliation/{reconciliation_id}`. The exact Store API namespace tuple SHALL be documented as `("interaction", "v1", owner_id, record_type)` (or the repository-equivalent existing Store namespace form) and SHALL NOT include secrets. Each value envelope SHALL include `record_type`, `schema_version`, immutable `id`, `owner_id`, `created_at`, `updated_at`, `status` where applicable, `revision`, and a sanitized `payload`; unknown fields SHALL be ignored for forward compatibility and schema versions SHALL be migrated explicitly.

#### Scenario: Repeated write of the same record
- **WHEN** the same deterministic key and equivalent revision are written more than once
- **THEN** the resulting record is equivalent and no duplicate logical record is created

#### Scenario: Cross-owner lookup
- **WHEN** a caller requests a record outside its authorized local-owner scope
- **THEN** the Store read returns not-found or authorization failure without revealing existence or values

### Requirement: Lifecycle and transition history
The system SHALL represent submit, processing, complete, error, cancel, retry, regenerate, branch, fork, crash/recovery, and delete/restore as explicit statuses/events with actor, reason, source event ID, timestamp, and correlation IDs. Legal transitions SHALL include `submitted→processing`, `processing→complete|error|cancelled`, `error→retrying|regenerating|deleted`, `complete→regenerating|branched|deleted`, `cancelled→retrying|deleted`, `retrying|regenerating→processing`, and `deleted→restored`; illegal or stale transitions SHALL be recorded as reconciliation issues and SHALL NOT overwrite a newer terminal state. A delete SHALL be a tombstone by default; restore SHALL be owner-authorized and policy-controlled, while physical purge and retention remain a separately approved operation.

#### Scenario: Crash during processing
- **WHEN** no completion event is observed before the configured recovery lease expires
- **THEN** reconciliation records the attempt as interrupted, retains checkpoint/run references, and makes an idempotent retry or explicit cancel available without fabricating completion

#### Scenario: Regenerate after completion
- **WHEN** the user explicitly regenerates a completed turn
- **THEN** a new attempt and assistant container revision are created, the prior attempt remains auditable, and the current turn points to the new attempt

### Requirement: Idempotent writes without transaction claims
Writers SHALL use deterministic IDs and record-level upsert/put semantics with monotonic `revision` and event IDs. They SHALL tolerate duplicate, reordered, and late events by accepting only the newest valid revision/status according to the transition rules, recording ignored events for audit/reconciliation, and never claiming cross-record transactions, compare-and-swap, or checkpoint/Store atomicity. A multi-record operation SHALL be recoverable by reconciliation from its event and reference metadata.

#### Scenario: Late completion after retry begins
- **WHEN** an old attempt emits completion after a newer retry is processing
- **THEN** the old attempt may be completed independently, but it cannot become the turn’s active attempt or overwrite the newer turn status

#### Scenario: Writer retries after timeout
- **WHEN** a Store write times out after the server may have accepted it
- **THEN** retrying the same deterministic key and payload is safe and produces one logical record

### Requirement: Checkpoint, run, message, and tool correlation
Each attempt SHALL retain references to LangGraph `thread_id`, `run_id`, checkpoint IDs/namespaces, message IDs, and tool-call IDs sufficient to correlate canonical graph execution, tools, branches, and resumability. Checkpoints SHALL remain authoritative for graph execution state and canonical messages; Store SHALL be authoritative for user-visible structure and relationships. Implementations SHALL document checkpoint retention/TTL, Store retention, message-ID stability, and the behavior when a referenced checkpoint or message is unavailable; Store records SHALL retain sanitized summaries/references rather than internal reasoning or credentials.

#### Scenario: Resume from a checkpoint
- **WHEN** execution resumes from a retained checkpoint
- **THEN** the existing attempt/run references are reused or linked and no second canonical message is invented by Store hydration

#### Scenario: Checkpoint expired
- **WHEN** a Store record references an unavailable checkpoint
- **THEN** the session remains structurally readable, the missing-reference condition is observable, and resume is refused or routed to an explicit recovery path

### Requirement: Artifact, revision, and provenance links
Turns and assistant containers SHALL link artifacts by immutable `artifact_id` and `revision_id`, with artifact type, title, lifecycle, content digest, creator/producer role, source references, provenance class (`user`, `generated`, `sourced`, `computed`, or `mixed`), and parent interaction/attempt. Revisions SHALL be append-only; a display projection SHALL identify the selected revision without rewriting prior provenance. Legacy visualizations, PDFs, saved pages, reports, research-pass reports, polls, and Perspective records SHALL remain distinguishable.

#### Scenario: Generated report is displayed
- **WHEN** an assistant container references a generated report
- **THEN** the UI labels it as generated and preserves its source/provenance links rather than presenting it as user-authored

#### Scenario: Artifact revision is replaced
- **WHEN** a new revision becomes current
- **THEN** the prior revision remains addressable and the new revision records its parent and content digest

### Requirement: Playback segment definitions
A playback segment set SHALL define deterministic ordered segment IDs, target container/message/artifact reference, segment kind, text or safe content reference, duration/ordering metadata, provenance label, and source revision. Segment sets SHALL be reproducible from Store records and SHALL never contain credentials, auth headers, private keys, or internal reasoning. A changed artifact revision SHALL create a new segment-set revision rather than silently changing a currently referenced set.

#### Scenario: Replay an assistant answer
- **WHEN** playback is requested for a completed assistant container
- **THEN** the system resolves ordered segments from the referenced revision and preserves provenance labels and missing-content status

#### Scenario: Playback source is deleted
- **WHEN** a referenced artifact or message is tombstoned
- **THEN** playback marks the segment unavailable and does not substitute unrelated content

### Requirement: Projection, hydration, and top anchoring
PostgreSQL `session_catalog` and the frontend SHALL be rebuildable projections/cache only. Projection consumers SHALL be idempotent, checkpointed by event/version, and able to rebuild by enumerating authorized Store records; projection lag or loss SHALL not alter Store authority. Frontend hydration SHALL reconstruct separate sibling user and assistant containers and their ordered turns from Store, with checkpoint canonical-message resolution where available. When a previously saved session/thread is reopened, the conversation SHALL perform one bottom placement only after the hydrated message window is mounted, so the latest saved content is initially visible. For each newly inserted user container and completed assistant container, the separate new-arrival behavior SHALL perform one top-anchoring action after insertion/layout settlement, then return full scroll control to the user without bottom-following or repeated repositioning. Neither behavior may reinstate removed bottom-lock/stream-following; no durable per-thread viewport position is introduced here, though a future explicit saved position may override the reopen default.

#### Scenario: Rebuild after projection loss
- **WHEN** the SQL catalog or frontend cache is empty or stale
- **THEN** a rebuild from Store restores the same authorized session/branch/turn/container relationships and selected statuses

#### Scenario: New turn settles
- **WHEN** a user or completed assistant container is inserted and its layout settles
- **THEN** it is positioned once at the top of the conversation viewport and later user scrolling is not overridden

#### Scenario: Reopen hydrated non-empty thread
- **WHEN** a saved session/thread is reopened and its non-empty hydrated message window is mounted
- **THEN** the conversation is positioned at the bottom once, showing the latest saved content, and does not repeatedly reclaim the viewport during processing or answer reveal

#### Scenario: Reopen edge states
- **WHEN** a session is empty, history is loading/errored, or a forked/reopened thread is hydrated
- **THEN** empty sessions receive no placement, loading/errors wait for successful hydration, and forked/reopened threads use the same one-time bottom default; reduced motion uses instant/no animation

### Requirement: Migration, authorization, backup, and reconciliation
Before rollout, the system SHALL provide a dry-run migration/backfill that maps existing sessions and legacy artifacts to deterministic IDs, records provenance confidence and unresolved links, and never claims missing history. Store records SHALL be scoped to the local owner and authorized session/branch access; logs and projections SHALL be sanitized. Backup/restore SHALL preserve namespaces, tombstones, revisions, and correlation IDs, and restore SHALL run reconciliation before serving writes. Reconciliation SHALL detect missing siblings/references, duplicate logical IDs, illegal transitions, projection gaps, orphaned artifacts, and checkpoint/Store divergence, emit repair records, and apply only idempotent record-level repairs.

#### Scenario: Legacy session has ambiguous artifact ownership
- **WHEN** backfill cannot determine the originating turn or provenance
- **THEN** it preserves the artifact as unresolved/legacy, reports the ambiguity, and does not invent an owner or relationship

#### Scenario: Restore contains partial records
- **WHEN** backup restore recovers a session but not all referenced records
- **THEN** the session is marked degraded, missing references are reported, and repair is required before destructive cleanup or normal write promotion

### Requirement: Deployment-scoped Store batch atomicity and application protocol

The implementation SHALL document the exact deployed Store/version/configuration used for any batch atomicity claim. For the verified deployment, PostgreSQL-backed `AsyncPostgresStore` 3.1.0 with psycopg 3.3.3, `autocommit=False`, and pipeline mode, a controlled batch failure rolled back an earlier delete in that batch. This SHALL be treated as deployment/version-scoped Store batch behavior only. The system SHALL NOT assume Store CAS, expected-version, idempotency, transaction-ID, or checkpoint/Store atomicity APIs. Application revisions, deterministic operation/event idempotency keys, late-event rejection, and reconciliation remain required across independent writes.

#### Scenario: Store batch fails after an earlier delete
- **WHEN** a controlled failure occurs after a delete in the same configured Store batch
- **THEN** the test records rollback for that deployment/version and the application still records a retry/reconciliation outcome without claiming a cross-system transaction

#### Scenario: Old revision arrives after a retry
- **WHEN** an event from an earlier application revision arrives after a newer revision is current
- **THEN** it is rejected as late, recorded for reconciliation, and cannot change current status or selected content

### Requirement: Application operation recovery and terminal failure

Every submission, reconnect, tool call, branch, fork, regeneration, and resume operation SHALL carry deterministic operation/revision/event identity. Interrupted writes and uncertain timeouts SHALL be retried only with the same identity, then reconciled by Store enumeration and checkpoint correlation. Duplicate submissions SHALL converge to one logical operation; unrecoverable attempts SHALL enter an explicit terminal-failed state with safe user-visible degradation rather than fabricated completion.

#### Scenario: Reconnect repeats a submission
- **WHEN** a client reconnect repeats a submission whose first write may have succeeded
- **THEN** the same application idempotency identity resolves the existing turn/attempt and does not create a duplicate logical turn

#### Scenario: Reconciliation cannot prove completion
- **WHEN** retries and scans cannot establish a valid completion or safe rollback
- **THEN** the attempt is terminal-failed, references and evidence are retained for repair, and no answer is invented

### Requirement: Artifact body ownership and shared-evidence protection

Artifact metadata, relationship, provenance, and revision records SHALL identify the approved body/content authority and SHALL NOT silently copy an artifact body into a competing interaction ledger. Deleting one interaction SHALL tombstone its relationship and protect shared evidence referenced by other authorized interactions; physical purge, retention, restore, and body deletion SHALL follow separately approved policy.

#### Scenario: Shared artifact is deleted from one turn
- **WHEN** an artifact is referenced by multiple authorized interactions and one interaction is deleted
- **THEN** only that relationship is tombstoned unless approved policy permits more, and the shared artifact body/provenance remains protected and addressable

### Requirement: Test-container mount hardening

Failure-injection and acceptance tests using containers SHALL run only against disposable fixtures, with non-privileged execution, isolated temporary storage/networking, and explicit mounts limited to test data. They SHALL reject host sockets, production volumes, repository secrets, ambient credentials, and unrestricted repository mounts before starting the test.

#### Scenario: Unsafe test target or mount is detected
- **WHEN** a test configuration cannot prove disposable storage and isolated mounts
- **THEN** the test fails closed without starting the container or touching data
