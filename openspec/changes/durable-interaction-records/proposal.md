## Why

The product currently has durable LangGraph execution state and related artifact/session concepts, but no single implementation-ready contract for reconstructing user-visible interaction structure across retries, branches, crashes, playback, and rebuilds. This change establishes LangGraph Store as the primary durable session-memory layer without creating a second interaction ledger, while keeping checkpoints authoritative for graph execution and PostgreSQL/frontend projections rebuildable.

## What Changes

- Define durable session, branch, turn, user/assistant container, attempt, reference, artifact/provenance, playback, status, event, and reconciliation records in LangGraph Store.
- Define deterministic namespaces, keys, envelopes, versions, lifecycle transitions, idempotency, late-event handling, retry/regenerate/branch/fork semantics, and crash recovery without assuming Store transactions, CAS, or checkpoint/Store atomicity.
- Correlate Store records to LangGraph thread/checkpoint/run/message/tool-call identities and state explicit message-retention assumptions.
- Define Store-to-PostgreSQL `session_catalog` projection/rebuild and frontend hydration/rebuild behavior, including sibling user/assistant containers, one-time bottom placement when a saved thread is reopened after its hydrated message window mounts, and the separate one-time top-anchored contract for new arrivals.
- Define playback segment, artifact revision, and provenance requirements; migration/backfill for existing sessions and legacy artifacts; authorization, local-owner boundaries, observability, backup/restore, repair, and deletion/restore policy.
- Add a sequenced implementation and validation plan with approval gates, disposable Store smoke tests, acceptance tests, and stop conditions.
- This is planning only: no application code, schemas, dependencies, databases, deployment configuration, or real product data will be changed by this OpenSpec change.
- The audit records a verified deployment fact: PostgreSQL-backed `AsyncPostgresStore` 3.1.0 with psycopg 3.3.3, `autocommit=False`, and pipeline mode rolled back an earlier delete when a controlled batch failed. That is a deployment/version-scoped Store batch observation, not a claim of Store CAS, expected-version, idempotency, transaction-ID, or checkpoint/Store atomicity APIs.
- Application revision/idempotency, late-event rejection, reconciliation, and explicit terminal failure remain required; LangGraph Store remains the durable authority and PostgreSQL remains only a rebuildable `session_catalog` projection.
- Observed facts, verified test facts, researched facts, inferred constraints, proposed design, and unresolved blocking decisions are explicitly separated in the design artifact. Missing retention, ownership, privacy, restore, API, test-target, and recovery-point decisions must not be guessed.
- Model attribution for this audit is recorded in `design.md` and `tasks.md` when available.

## Capabilities

### New Capabilities

- `durable-interaction-records`: Durable user-visible interaction structure and projections backed by LangGraph Store, correlated with authoritative LangGraph checkpoints.

### Modified Capabilities

- None. Existing changes are used as context; this proposal does not silently alter their requirements.

## Impact

The eventual implementation will affect LangGraph Store record writers/readers, checkpoint/run correlation, session catalog projection and rebuild jobs, frontend hydration/cache, playback/artifact presentation, migration tooling, authorization boundaries, and observability. It explicitly excludes a separate PostgreSQL interaction ledger and does not authorize implementation or data migration yet.

## Terminology boundary

The existing `workspace_id` field and Store/database keys remain compatibility
contracts for durable repository-path binding IDs; they are not visual workspace
identifiers. A session record may omit a repository binding. Artifacts remain keyed to
the producing thread/session, not to a repository binding. LangGraph runtime,
checkpoints, and Store are infrastructure rather than workspace entities. See
`openspec/TERMINOLOGY.md`.

## Model-use extension

This change also proposes durable sanitized model-use records linked to `workspace_id` where applicable, session/branch/turn/attempt/run identity, selected and actual provider/model, authority/source, profile/version, capability-verification reference, measured versus estimated metrics, retries/failures/fallbacks/escalations, projection/rebuild behavior, and privacy boundaries. Selection and evidence semantics remain in the two new model-selection changes.
