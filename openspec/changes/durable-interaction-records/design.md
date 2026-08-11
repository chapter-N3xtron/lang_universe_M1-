## Context

See `proposal.md` and `specs/durable-interaction-records/spec.md`. The related OpenSpecs establish an Inquiry-oriented session and artifact provenance boundary, durable Research evidence/report references in LangGraph Store, explicit Coder/Research reporting boundaries, and a proposed one-shot top-anchoring interaction. The current product decision adds a general interaction-memory layer but keeps graph execution semantics separate.

### Observed implementation (not a completion claim)

- Existing work uses LangGraph checkpoints for graph execution and Store namespaces for selected evidence/session records.
- Existing session/catalog and frontend behavior are projections or presentation paths, not an approved interaction authority contract.
- Existing UI work records top anchoring as proposed and requiring live-browser verification for both user-message and assistant-answer arrival.
- The current implementation record does not establish verified initial bottom placement for a reopened saved thread after hydration, nor a durable per-thread viewport-position feature.
- Related changes distinguish generated, sourced, computed, and user-authored artifacts and prohibit exposing secrets, protected workspace content, or internal reasoning.

### Proposed behavior

The Store contract, IDs, envelopes, lifecycle, reconciliation, projection, migration, and validation below are proposed by this change and are not implemented by it.

## Goals / Non-Goals

**Goals:**

- Make Store the durable authority for user-visible structure and relationships while checkpoints remain authoritative for execution, canonical messages, tools, branches, and resumability.
- Make every operation retry-safe without pretending Store provides transactions, CAS, or atomic checkpoint/Store writes.
- Make SQL/frontend rebuilds, migrations, playback, provenance, and repair testable.

**Non-Goals:**

- No separate PostgreSQL interaction ledger; `session_catalog` is only a rebuildable query projection.
- No custom storage engine, dependency change, database migration, deployment change, or application implementation in this change.
- No new retention, sharing, cross-owner access, physical purge, or authorship policy beyond explicit boundaries and approval gates.
- No storage of secrets, credentials, auth headers, private keys, chain-of-thought/internal reasoning, or raw protected paths in records or telemetry.

## Decisions

### 1. Store is the relationship authority; checkpoints are execution authority

The record graph is written to existing LangGraph Store APIs using deterministic namespaced keys. Checkpoint references are links, not duplicated execution state. This preserves resumability and canonical message/tool semantics while allowing the user-visible session to survive projection loss.

**Alternative rejected:** a new PostgreSQL interaction ledger, because it would create competing authority and duplicate the Store-backed durable boundary.

### 2. Use explicit sibling containers and immutable attempt/revision identity

A turn owns separate user and assistant containers; attempts represent execution attempts and regenerate/retry history; artifact revisions and playback segment sets are append-only. This makes partial writes and replay understandable without relying on implicit role inference.

**Alternative rejected:** one mutable transcript blob, because it cannot represent late events, provenance, partial recovery, or rebuild-safe relationships.

### 3. Deterministic keys plus monotonic revisions, not transactions

A writer computes IDs from immutable owner/session/branch/turn/attempt/run inputs and writes records independently. Event IDs make retries deduplicable; revision/status guards reject stale updates at the application protocol level. The design explicitly treats cross-record operations as eventually consistent and repairs them by scanning Store.

**Alternative rejected:** assumed compare-and-swap or multi-record transactions, because current Store capabilities do not support that guarantee.

### 4. Event/reconciliation metadata is first-class but sanitized

Every transition carries source event, actor, reason, correlation IDs, and timestamps. Repair records describe gaps and proposed/applied repair actions. Observability exposes counts, latency, lag, and failure classes, not content secrets or internal reasoning.

**Alternative rejected:** reconstructing history only from logs, because logs are lossy, harder to authorize, and unsuitable as durable authority.

### 5. Rebuild projections rather than dual writes to authority

A projection worker consumes Store records/events idempotently into `session_catalog`; a full rebuild enumerates authorized Store namespaces and recreates rows. Frontend cache follows the same rule and hydrates sibling containers, then uses checkpoint messages only for canonical message content.

**Alternative rejected:** treating SQL or frontend state as authoritative, because either loss would make recovery impossible and would conflict with the product decision.

### 6. Reopen placement is distinct from new-arrival anchoring

After frontend hydration mounts a non-empty saved thread's message window, the proposed default is one bottom placement so the latest saved content is visible. This does not follow processing or assistant-answer reveal, reclaim the viewport after the user scrolls, or reinstate removed bottom-lock behavior. New user messages and completed assistant answers retain the separate proposed one-time top positioning after layout settles. Empty sessions have no placement target; loading/history errors wait for successful hydration; forked/reopened threads use the same default; reduced motion uses instant/no animation. A future explicit durable per-thread viewport position may override the default only if separately introduced, and this change does not introduce it.

**Alternative rejected:** using one scroll rule for both reopen and new arrivals, because initial restoration and newly arriving content have different user-intent and timing semantics.

### 7. Migration is dry-run first and ambiguity-preserving

Existing sessions and legacy artifacts are mapped only where identity/provenance is evidenced. Ambiguous records retain legacy/unresolved status and a report. Backfill is resumable by deterministic keys; rollback disables new reads/writes and leaves existing records intact.

### 7. Recovery and deletion are conservative

A crash creates an interrupted/reconciliation state, not a fabricated answer. Tombstones hide records from normal projections while preserving references for audit/restore. Physical purge, retention, sharing, and cross-device policy require a separate approval gate.

## Record and key contract

The implementation must maintain the exact record types and IDs in the spec: `session_id`, `branch_id`, `turn_id`, `user_container_id`, `assistant_container_id`, `attempt_id`, `run_id`, `checkpoint_id`, `message_id`, `tool_call_id`, `artifact_id`, `artifact_revision_id`, `segment_set_id`, `segment_id`, `event_id`, and `reconciliation_id`. IDs are immutable, opaque, deterministic identifiers; human titles are payload fields. Namespaces use owner scope plus record type, with schema/version envelope fields. A concrete adapter must document the repository’s existing Store tuple shape before coding and must not invent a new backend.

## Correlation and retention contract

At submit, write the turn/containers/attempt/event with known request and branch identity, then associate run/checkpoint/message/tool references as they become known. Completion is a series of independently retryable writes followed by a status event. The design must record the chosen checkpoint TTL, Store retention, artifact retention, and message-ID stability before rollout; if a canonical message expires, retain safe metadata and mark hydration/resume degraded rather than recreating it.

## Projection/reconciliation algorithm

1. Consume events/records by deterministic key and highest valid revision.
2. Ignore duplicates; record stale/illegal events.
3. Recompute each turn’s relationship invariants (one current attempt, both sibling container links when applicable, valid parent branch).
4. Resolve checkpoint/message/tool/artifact references without fetching protected content.
5. Upsert SQL/frontend projection state and a projection cursor.
6. Periodically enumerate Store and compare expected relationships, writing repair records.
7. Apply only approved, idempotent repairs; never infer authorship, delete shared evidence, or overwrite newer records.

## Validation strategy and stop conditions

Validation must include strict OpenSpec validation, static contract tests for key/envelope/transition rules, duplicate/reordering/late-event tests, checkpoint-expiry and projection-rebuild tests, migration dry-run fixtures, authorization/sanitization tests, restore/reconciliation tests, and live-browser verification of both one-shot scroll arrival paths. A disposable Store smoke test may create and delete/tombstone synthetic records only in an isolated test namespace; it must first prove the configured Store target is non-production and must not print environment values, headers, tokens, or record payload secrets.

Stop implementation at any gate if Store API semantics differ from the assumed record-level upsert/read/list behavior, if owner authorization cannot be demonstrated, if checkpoint/message retention is unknown, if migration ambiguity would require invention, if no safe disposable namespace exists, if a required approval is absent, or if any test would touch real product data.

## Risks / Trade-offs

- [Independent writes expose partial relationship graphs] → deterministic keys, explicit degraded states, reconciliation scans, and repair records; no atomicity claim.
- [Store growth from attempts/events/revisions] → bounded payloads, retention approval, summary references, and measured namespace/index costs before rollout.
- [Checkpoint expiry breaks canonical replay] → documented TTL compatibility, degraded-reference handling, and explicit recovery paths.
- [Projection lag makes SQL/UI briefly stale] → show status/lag, rebuild cursors, and never promote projections to authority.
- [Backfill misattributes legacy data] → dry-run, confidence/unresolved states, human gate, and no inferred ownership/provenance.
- [Scroll behavior appears correct in automation but fails in-browser] → separate live-browser checks for user and assistant arrivals; this change is not complete until both pass.

## Migration Plan

1. Approve this contract, owner boundary, deletion/restore policy, retention values, checkpoint/message assumptions, and Store namespace adapter.
2. Build disposable contract fixtures and Store smoke checks; stop on any unsafe target or unsupported API guarantee.
3. Implement record writers/readers and reconciliation behind disabled entry points; verify idempotency and authorization.
4. Implement projection/rebuild and frontend hydration/scroll behavior; run acceptance and live-browser checks.
5. Run migration dry-run and review unresolved/legacy report; approve only then run resumable backfill.
6. Enable a limited rollout with reconciliation and projection lag monitoring; rollback by disabling the new path, preserving records and tombstones.
7. Require restore drill and retention/deletion review before general availability.

## Evidence classification and deployment/persistence audit

The plan distinguishes evidence classes and must preserve that distinction in implementation reviews:

- **Observed repository facts:** `backend/src/session_catalog.py` writes owner-scoped Store records through `aget`/`aput`, uses namespaces such as `(owner_id, "sessions")`, `(owner_id, "workspaces")`, and `(owner_id, "session-artifacts", thread_id)`, and writes PostgreSQL `session_catalog` tables as an application projection. `backend/scripts/rebuild_session_catalog.py` rebuilds through public Agent Server Store APIs and checkpoint/thread history. The current catalog model is session/thread-oriented and does not establish the proposed turn/container/attempt/event authority.
- **Verified test/deployment facts:** the deployed persistence path is PostgreSQL-backed `AsyncPostgresStore` 3.1.0 with psycopg 3.3.3, configured with `autocommit=False` and pipeline mode. A controlled batch-failure test rolled back an earlier delete in the same batch. This proves atomicity only for that deployment/version-scoped Store batch behavior; it does not prove application-level CAS, expected-version, idempotency, transaction-ID, or checkpoint/Store atomicity.
- **Researched facts:** the inspected public Store usage exposes record-level get/put/list behavior used by the repository, while the required CAS/expected-version/idempotency/transaction-ID guarantees are not exposed as a contract that this plan may rely on. The exact adapter surface and batch API must be pinned to the deployed package and tested without exposing connection details or payloads.
- **Inferred constraints:** because Store batch atomicity is deployment/version scoped and cross-system writes remain separate, application revisions, deterministic idempotency keys, late-event rejection, reconciliation, and explicit terminal failure states are required. A batch rollback must not be generalized into a durable interaction transaction.
- **Proposed design:** LangGraph Store remains the only durable interaction authority; PostgreSQL `session_catalog` remains a rebuildable projection. Application revision/idempotency metadata, checkpoint/Store correlation, sibling containers, playback revisions, provenance ownership, and repair records are proposed contracts, not implementation completion.

### Deployment-scoped batch boundary

The implementation plan SHALL record the exact deployed Store version/configuration alongside every atomicity test and SHALL treat batch atomicity as scoped to that deployment and batch, not as a portable Store guarantee. No design may depend on Store CAS, expected-version, idempotency, transaction-ID, or checkpoint/Store transaction APIs because their absence is a verified capability constraint. Application revision checks, deterministic operation/event IDs, and late-event rejection therefore remain mandatory even when a batch is available. A failed batch is a terminal/reconciliation input: retry only with the same operation identity, reconcile partial cross-system effects, and surface an explicit terminal failure when recovery cannot prove safety.

### Write/retry/reconciliation coverage

The plan must cover interrupted writes, timeout retries, duplicate submissions, reconnects, tool calls, branches, forks, regeneration, resume, and late events. Each operation has an application revision and idempotency key; an old revision cannot become current. Checkpoint/run/message/tool references are correlated as they become available, and message retention/ID stability are recorded before rollout. Reconciliation distinguishes pending, interrupted, retryable, reconciled, and terminal-failed states rather than fabricating completion.

### Container, playback, and evidence ownership

User and assistant containers are separate siblings. Playback segment sets are immutable revisions tied to a source message/artifact revision. Artifact body ownership and provenance are explicit: Store may own durable relationship metadata and safe summaries, while the body owner remains the approved artifact/content authority. Shared evidence cannot be physically deleted or rewritten merely because one interaction is deleted; tombstones, authorization, retention, restore, and provenance checks protect shared references.

### Projection, migration, recovery, and test safety

Store-to-session-catalog projection is idempotent and fully rebuildable from authorized Store enumeration; catalog loss never promotes SQL to authority. Legacy migration is dry-run, deterministic where evidence permits, and preserves ambiguity as unresolved rather than guessing. Backup/restore must preserve namespaces, tombstones, revisions, and correlation IDs and must reconcile before writes resume; recovery-point and retention assumptions are blocking inputs. Observability records sanitized operation/revision/event IDs, lag, retries, rollback/failure classes, reconciliation age, and terminal failures without content secrets or internal reasoning. Failure-injection and acceptance tests must cover batch rollback, interrupted/late writes, duplicates/reconnects, tools/branches/forks/regeneration/resume, replay, provenance, projection rebuild, migration ambiguity, authorization/privacy/deletion/restore, and recovery points. Test containers must mount only disposable fixture storage, run as a non-privileged user, use a private temporary network/namespace, and never receive host sockets, repository secrets, production volumes, or ambient credentials.

## Blocking decisions

The following are unresolved and must remain blockers rather than guessed values: exact checkpoint and message TTL/ID-stability contract; Store and event/artifact retention; ownership and body-storage policy for each artifact class; authorization, privacy, sharing, deletion, physical purge, and restore semantics; backup scope and recovery-point/recovery-time assumptions; exact deployed AsyncPostgresStore batch/API adapter surface; safe non-production Store target and test-container runtime/mount policy; and the approval owner for legacy ambiguity resolution and rollout. The plan is not implementation-complete until each blocker has an owner, evidence, and an explicit decision.

No application implementation or deployment change is claimed by this planning audit.

## Open Questions

See **Blocking decisions**. Exact values and API guarantees remain approval-gated inputs; the plan must not silently choose them during implementation.

## Model attribution

Plan audit and documentation revisions: model ID unavailable in this runtime (deep-agent).

Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## OpenSpec plan-audit status

Documentation-only audit completed; implementation tasks remain unchecked and the change is not claimed complete.

Exact checkpoint TTL, Store retention, message-ID stability, artifact body ownership, recovery-point assumptions, and repository-specific Store adapter method names must be decided and evidenced before implementation.
