## 1. Approval gates and observed-baseline inventory

- [ ] 1.1 Obtain approval for the Store-as-relationship-authority decision, no-PostgreSQL-ledger boundary, local-owner authorization boundary, and separate sibling user/assistant containers. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 1.2 Inventory the existing LangGraph Store API methods, namespace conventions, checkpoint saver/thread/run identifiers, message/tool-call identity behavior, session catalog projection, frontend hydration, artifact records, and scroll paths; label every finding observed versus proposed. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 1.3 Obtain explicit values and owners for checkpoint TTL, Store/artifact/event retention, message-ID stability, delete/tombstone/restore, backup/restore, and physical-purge policy; stop if any value is unavailable. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## 2. Contract and disposable validation harness

- [ ] 2.1 Define and review the deterministic ID derivation and exact namespace/key adapter for `session`, `branch`, `turn`, `user_container`, `assistant_container`, `attempt`, `run`, `checkpoint`, `message`, `tool_call`, `artifact`, `artifact_revision`, `playback`, `event`, and `reconciliation`; include owner scope and schema/version envelopes. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 2.2 Implement contract-level tests for envelope validation, deterministic keys, schema-version handling, immutable IDs, monotonic revisions, bounded/sanitized payloads, and unknown-field compatibility; do not change production schemas or dependencies in this planning phase.
- [ ] 2.3 Create a disposable Store smoke-test profile that requires an independently verified non-production namespace/target, writes synthetic records only, exercises put/get/list/upsert behavior, verifies duplicate safety, and tombstones/deletes its own synthetic data; fail closed if target safety cannot be proven.
- [ ] 2.4 Run the smoke profile without printing environment files, secret values, credentials, auth headers, private keys, or raw Store payloads; record only API capability, pass/fail, latency class, and cleanup status.
- [ ] 2.5 Stop and obtain design approval if the current Store cannot provide the required record-level operations, deterministic namespace isolation, or safe disposable target; do not substitute a custom engine or PostgreSQL ledger. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## 3. Durable record writers and lifecycle

- [ ] 3.1 Implement session/branch/turn creation and separate sibling user/assistant container records with deterministic IDs, parent/fork links, local-owner checks, and sanitized event metadata. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 3.2 Implement attempt/run/checkpoint/message/tool-call reference records and submit→processing→complete/error/cancelled transitions, with legal-transition tests and explicit degraded states for missing references.
- [ ] 3.3 Implement retry, regenerate, branch, fork, crash/recovery, tombstone, and owner-authorized restore semantics; preserve prior attempts/revisions and prevent stale events from becoming current. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 3.4 Implement record-level idempotency for duplicate, reordered, late, and timeout-retried writes; test that no behavior relies on cross-record transactions, CAS, or checkpoint/Store atomicity.
- [ ] 3.5 Implement reconciliation scans and repair records for missing siblings/references, illegal transitions, duplicate logical IDs, orphaned artifacts, projection gaps, and checkpoint/Store divergence; repairs must be idempotent and must not infer authorship. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## 4. Artifacts, provenance, and playback

- [ ] 4.1 Implement immutable artifact/revision links carrying type, digest, producer role, provenance class, source references, parent interaction/attempt, selected revision, and legacy/unresolved markers where evidence is incomplete. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 4.2 Implement deterministic playback segment-set revisions and ordered segment records for messages/artifacts, including missing-content and tombstoned-source behavior; exclude credentials, protected paths, and internal reasoning. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 4.3 Add acceptance tests proving generated, sourced, computed, mixed, and user-authored materials remain distinguishable and that revisions/playback never launder provenance or authorship.

## 5. Checkpoint correlation and projections

- [ ] 5.1 Implement correlation updates from submit through completion for thread/run/checkpoint/message/tool-call references and document behavior when checkpoint/message retention expires; canonical graph messages remain checkpoint-authoritative. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 5.2 Implement idempotent Store-to-`session_catalog` projection with event/version cursor, lag/error metrics, authorized enumeration, and full rebuild that never becomes a second authority. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 5.3 Implement frontend hydration/cache rebuild from Store relationships plus checkpoint canonical-message resolution, rendering separate sibling user and assistant containers and degraded/missing-reference states. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 5.4 Implement and verify one-shot top anchoring after layout settlement for newly inserted user messages and completed assistant answers, followed by unrestricted user scroll; keep this separate from processing/reveal behavior and the removed bottom-lock/stream-following behavior; run separate live-browser checks for both arrival paths. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 5.5 Verify initial reopen placement only after the hydrated message window is mounted: bottom once for non-empty saved, forked, and reopened threads; no placement for empty sessions; defer during loading/history errors; use instant/no animation for reduced motion; do not add durable per-thread viewport storage. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 5.6 Add projection-loss, stale-cache, duplicate-event, checkpoint-expiry, and frontend rebuild acceptance tests; compare rebuilt output with direct Store hydration.

## 6. Migration, security, and recovery validation

- [ ] 6.1 Build a resumable dry-run backfill for existing sessions and legacy visualization/chart, PDF, saved-page/link, report/research-pass-report, poll, and Perspective artifacts using deterministic IDs; emit confidence and unresolved-link reports without inventing ownership/provenance. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 6.2 Obtain human review of the dry-run report, authorization/local-owner tests, retention/delete/restore behavior, and unresolved legacy records before any backfill write. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 6.3 Run authorization, enumeration isolation, sanitization, backup/restore, tombstone preservation, and restore-reconciliation tests; verify logs contain no secret values, auth material, private keys, or internal reasoning. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 6.4 Execute the approved backfill in resumable batches with reconciliation checkpoints, then verify Store-to-SQL and frontend rebuild parity; rollback only by disabling the new path, never by destructive rewrite. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## 7. Release gates and strict validation

- [ ] 7.1 Run `openspec validate durable-interaction-records --strict` and resolve every structural/spec failure; do not claim implementation completion from planning validation.
- [ ] 7.2 Run focused contract, lifecycle, idempotency, correlation, artifact/playback, projection/rebuild, migration dry-run, authorization, restore, and reconciliation tests; record exact pass/fail and skipped reasons.
- [ ] 7.3 Require approval gates for Store API compatibility, safe smoke target, retention/message assumptions, migration report, live-browser scroll verification, restore drill, and authorization boundary; stop rollout when any gate is absent or fails. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 7.4 Confirm no application code, schema, dependency, database, deployment configuration, real product data, or unrelated working-tree file was modified by the planning change; report blockers and observed/proposed distinctions before implementation begins.

## 8. Bounded plan-audit evidence and blocking decisions

- [ ] 8.1 Record the repository observations: current Store namespaces and `aget`/`aput` usage, checkpoint/thread-history rebuild path, PostgreSQL `session_catalog` projection boundary, existing artifact/session limitations, and the absence of an implemented turn/container/attempt/event authority. Label each item observed, not proposed completion.
- [ ] 8.2 Record the verified deployment/test fact: PostgreSQL-backed `AsyncPostgresStore` 3.1.0 with psycopg 3.3.3, `autocommit=False`, pipeline mode, and controlled batch failure rollback of an earlier delete. Scope the claim to that deployment/version/batch and do not generalize it to CAS, expected-version, idempotency, transaction-ID, or checkpoint/Store atomicity APIs.
- [ ] 8.3 Pin application-level revision and deterministic idempotency behavior for submissions, reconnects, retries, tools, branches, forks, regeneration, resume, and late events; define interrupted, reconciled, retryable, and terminal-failed outcomes and acceptance tests without relying on Store transactions.
- [ ] 8.4 Define checkpoint/Store correlation, message retention and ID stability, sibling user/assistant containers, playback segment revisions, artifact body ownership/provenance, shared-evidence deletion protection, and Store-to-session-catalog projection/rebuild semantics.
- [ ] 8.5 Define dry-run legacy migration and ambiguity preservation; obtain blocking decisions for authorization/privacy, retention, deletion/restore, backup/restore and recovery points, observability, and rollout ownership. Do not guess missing policy values.
- [ ] 8.6 Specify failure-injection/acceptance coverage for batch rollback, interrupted writes, duplicates, late events, reconnects, tools, branches/forks, regeneration/resume, checkpoint expiry, projection loss, migration ambiguity, provenance laundering, authorization/privacy, restore, and terminal failure.
- [ ] 8.7 Harden disposable test-container requirements: non-privileged user, isolated temporary network/storage, explicit fixture-only mounts, and fail-closed rejection of host sockets, production volumes, repository secrets, ambient credentials, or broad repository mounts.
- [ ] 8.8 Keep all implementation checkboxes unchecked until the blocking decisions and evidence gates are resolved; this plan audit must not claim implementation completion.

Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## Model attribution

Plan audit and documentation revisions: model ID unavailable in this runtime (deep-agent).
