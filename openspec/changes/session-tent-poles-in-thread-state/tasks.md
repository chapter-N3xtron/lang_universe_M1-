## 1. Approval and observed baseline

- [ ] 1.1 Obtain human approval for the exact authenticated action that confirms the complete tent-pole replacement, including an explicit empty list; model or tool output MUST NOT count as approval. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 1.2 Inventory, without mutation, current `chat_ui` state/checkpoint APIs, authoritative thread-ID handling, Store session `tent_poles`, `session_catalog.tent_poles`, close/detail behavior, fork behavior, and all legacy source/timestamp shapes.
- [ ] 1.3 Measure and document current precedence and disagreements between Store and table records; define the compatibility precedence needed for rollback rather than guessing it.

## 2. Thread-state contract

- [ ] 2.1 Define typed `TentPole` and `tent_poles` state contracts with exactly `id`, `content`, `priority`, and `approved_at`, unique IDs, timezone-aware timestamps, deterministic ordering, complete-list replacement semantics, and a maximum of 20.
- [ ] 2.2 Add contract tests proving absent state invokes legacy fallback, valid present state wins, present `[]` is authoritative, and present invalid state fails closed without exposing stale fallback.
- [ ] 2.3 Define an authenticated, idempotent state-update operation bound to the authoritative thread ID; prove a complete approved list creates readable checkpointed state and retries do not append or duplicate.

## 3. Same-thread isolation and Store promotion boundary

- [ ] 3.1 Provide workflows/tools a read-only value from their current graph state without any model/tool-supplied target thread, session, owner, namespace, key, or search argument.
- [ ] 3.2 Add isolation tests proving thread B cannot read thread A's tent poles, including same-owner and same-repository-binding cases; prove a fork reads only its own copied state and cannot query its parent.
- [ ] 3.3 Prove ordinary tent-pole approval/update performs no LangGraph Store write, update, index, or delete and does not mutate legacy Store records.
- [ ] 3.4 Design a separate installation-wide promotion operation with fresh explicit human approval over exact source and destination values; test rejection, abandonment, changed inputs, replay, and missing approval as zero-Store-write outcomes. Do not implement general promotion UI in this change. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## 4. Compatibility adapters

- [ ] 4.1 Change future detail/close adapters only as needed to read/write authoritative thread state while preserving the existing string-list compatibility response where required; do not make general UI changes.
- [ ] 4.2 Freeze `session_catalog.tent_poles` and legacy Store tent-pole data against new authoritative writes while retaining read-only fallback for state-absent threads.
- [ ] 4.3 Add regression tests for non-empty updates, approved clears, retries, reopen, close, disagreement handling, malformed state, missing legacy data, and the existing 20-item limit.

## 5. Reversible migration

- [ ] 5.1 Build a read-only inventory and dry run with checksums/backups that reports table/Store disagreements, duplicate or over-limit values, missing or untrustworthy approval timestamps, malformed records, and owner/thread mismatches; mutate nothing.
- [ ] 5.2 Define deterministic IDs, map table `position` to `priority`, preserve content, and use only evidenced approval timestamps; leave Store-only or ambiguous records on legacy fallback rather than inventing fields or attribution.
- [ ] 5.3 Obtain explicit human approval for each migration cohort and unresolved-record disposition before any state write. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 5.4 Write complete lists in resumable idempotent batches, then read back direct thread state and effective compatibility results and compare count, content, order, IDs, timestamps, isolation, and explicit-empty behavior.
- [ ] 5.5 Run a rollback drill that disables state reads/writes for the cohort and proves preserved Store/table fallback still returns the pre-migration values; stop on any mismatch.
- [ ] 5.6 Cut over reads only for verified threads. Keep fallback and every legacy Store/table record intact; table deletion, fallback removal, and destructive cleanup require a separate approved change.

## 6. Scope and release gates

- [ ] 6.1 Run focused contract, authorization, no-Store-write, compatibility, migration readback, and rollback tests against disposable fixtures only; do not touch real product data.
- [ ] 6.2 Confirm implementation review includes no deployment changes, table deletion, legacy record deletion, document linking, general UI work, existing-change edits, or unrelated changes.
- [ ] 6.3 Run `openspec validate session-tent-poles-in-thread-state --strict` and resolve every structural or specification failure; report planning validation separately from implementation completion.
- [ ] 6.4 Keep rollout blocked until omitted-versus-empty preservation, human approval, authoritative thread binding, migration readback, fallback parity, and rollback are all verified.

Governance reference: `GOVERNANCE_FRAMEWORK.md`.
