## Context

The observed implementation has three relevant boundaries:

- `backend/src/chat_ui.py` defines checkpointed LangGraph `State`, but it currently has no tent-pole channel. Nodes receive state, configuration, and in some cases `Runtime`.
- `backend/src/session_catalog.py` describes checkpoints as conversation authority and the `session_catalog` schema as a rebuildable application projection. Nevertheless, its DDL includes `session_catalog.tent_poles`, and its Store merge preserves a legacy `tent_poles` field in `(owner_id, "sessions")` records.
- `backend/src/session_catalog_models.py` accepts up to 20 tent-pole strings. `backend/src/session_catalog_routes.py` reads detail values from the table; close writes strings to the Store session record and, only when the submitted list is non-empty, replaces table rows. Consequently, an empty submission can disagree between Store and table. Forking copies thread/checkpoint state through Agent Server but does not copy `session_catalog.tent_poles` rows.

`anatomy-of-a-session` defines sessions as Inquiry-oriented bodies of work and protects human attribution. This change narrows that context to already human-approved tent poles; it does not define Perspective, document associations, or presentation changes.

## Official LangGraph architecture basis

This design follows the current official documentation:

- [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) distinguishes checkpointers, which persist a thread's graph state as thread-scoped memory, from Store, which persists application-defined long-term data across threads.
- [Memory](https://docs.langchain.com/oss/python/langgraph/add-memory) describes short-term memory as part of graph state, keyed by `thread_id`, and long-term memory as Store data across conversations. It also documents inspection of current thread state and history.
- [Graph API: State and reducers](https://docs.langchain.com/oss/python/langgraph/graph-api#state) defines typed graph-state channels and default replacement semantics when no reducer is declared. Replacement semantics are required here so `[]` replaces prior tent poles rather than appending or being interpreted as missing.
- [Graph API: nodes](https://docs.langchain.com/oss/python/langgraph/graph-api#nodes) documents that nodes receive graph state and that `Runtime` can expose Store. This supports direct same-thread state reads while keeping Store promotion a different, approval-gated operation.
- [Graph API: graph migrations](https://docs.langchain.com/oss/python/langgraph/graph-api#graph-migrations) documents forward/backward compatibility for adding and removing state keys, while warning that renames and incompatible type changes can lose or disrupt saved state. The plan therefore adds one new key and retains legacy fallback rather than renaming or deleting old storage.

The architectural rule is therefore: checkpointed `tent_poles` is session/thread memory; LangGraph Store is not an automatic mirror and is used only for a separately approved installation-wide promotion.

## Goals / Non-Goals

**Goals:**

- Make human-approved tent poles authoritative structured state for exactly one LangGraph thread.
- Give workflows and tools in that thread a read-only view without accepting an arbitrary target thread ID.
- Retain the existing 20-item bound and preserve explicit empty-list intent.
- Keep all legacy records readable until migration readback and rollback are proven.
- Make migration reversible without destructive cleanup.

**Non-Goals:**

- No implementation, deployment, database mutation, schema/table deletion, or real-data migration is performed by this change.
- No deletion or rewrite of legacy Store records or `session_catalog.tent_poles` rows is authorized, even after verification; cleanup requires a later change.
- No document linking, artifact association, Perspective behavior, retention policy, general UI redesign, or unrelated API behavior is added.
- No automatic cross-thread memory, semantic indexing, model-selected promotion, or inferred human approval is allowed.

## Decisions

### 1. Use one replacement-valued thread-state channel

A future `State` contract will add `tent_poles: list[TentPole]` with no append reducer. A successful human-approved update replaces the complete list and creates a checkpoint in the authoritative `thread_id`. The field is bounded to 20 records.

Presence is semantically distinct from absence:

1. If the current thread-state snapshot contains a valid `tent_poles` key, that list is authoritative, including `[]`.
2. If the key is absent, the compatibility reader may resolve preserved legacy data according to the documented legacy precedence needed to match current behavior.
3. If the key is present but invalid, the reader fails closed and reports a migration/validation error; it does not silently reveal a stale legacy list.

A separate presence marker is unnecessary because checkpoint state can distinguish an omitted key from a present empty list. Implementations must test that the selected Agent Server/state API preserves this distinction.

**Alternative rejected:** append reducer. It would make clearing impossible and make retries duplicate records.

**Alternative rejected:** continue treating the table or owner Store session record as authority. Neither is inherently thread-state-scoped, and Store is designed for data that may span conversations.

### 2. Use a minimal structured record

Each state item has exactly these proposed business fields:

- `id`: non-empty, immutable, opaque identifier unique within the thread; migration IDs are deterministic from immutable legacy identity, not list position alone.
- `content`: non-empty human-approved text.
- `priority`: integer ordering value; lower values sort first, with `id` as a deterministic tie-breaker. Migration maps legacy `position` to `priority` without changing content order.
- `approved_at`: timezone-aware ISO-8601 timestamp recording the evidenced human approval time, normalized to UTC.

The complete list contains at most 20 unique IDs. Approval writes validate the complete replacement atomically at the graph-state update boundary. Ordinary model output, tool output, catalog projection writes, or Store records cannot manufacture approval.

Legacy data lacking trustworthy evidence for any required field remains legacy fallback and is reported as unresolved; migration must not invent an approval timestamp or human attribution.

### 3. Bind runtime reads to the executing thread

Same-thread nodes, subworkflows, and tools receive the already resolved `tent_poles` value from current graph state or a read-only derived input. The reader does not accept `thread_id`, `session_id`, owner namespace, Store namespace, or search query from model/tool arguments. It verifies the runtime/config authoritative thread identity before returning data.

A workflow in thread B cannot inspect thread A's tent poles, even when both have the same owner or repository binding. A copied/forked thread may only read values actually present in its own copied checkpoint state; it gains no ongoing reference to or read authority over its parent.

### 4. Separate thread approval from installation-wide promotion

Approving a thread tent pole authorizes only replacement of that thread's checkpointed state. It must not write, update, index, or delete LangGraph Store memory.

Promotion to installation-wide memory is a distinct operation with a fresh explicit human approval showing the exact source thread, tent-pole ID and content, destination Store namespace/key, installation-wide audience, and proposed write. Rejection, abandonment, changed content/target, or absent approval performs no Store write. The promoted Store item is a copy with provenance back to the source; later thread edits do not silently alter it. Designing the broader promotion UI or memory policy is outside this change.

### 5. Keep compatibility reads narrow and non-destructive

Existing Store session values and every `session_catalog.tent_poles` row remain unchanged. During migration:

- state present and valid: state wins;
- state absent: compatibility fallback remains available;
- state present as `[]`: return empty and do not consult fallback;
- state present but invalid: error/rollback signal, not fallback;
- new approvals: write state only, while compatibility response adapters may down-convert structured records to the existing string-list shape where required.

The SQL table is frozen legacy storage, not a write target for new authoritative changes and not a projection to be rebuilt from state under this change. Table deletion and legacy Store cleanup are expressly deferred.

### 6. Migrate only with evidence and reversible gates

The migration is resumable and per-thread:

1. Inventory and back up/checksum legacy Store and table records without mutation.
2. Dry-run resolution and report source disagreement, duplicate content, over-limit data, missing timestamps, malformed values, and owner/thread mismatches.
3. For unambiguous table rows, preserve content, map `position` to `priority`, derive deterministic IDs from stable owner/thread/source identity plus content, and use the row's evidenced `created_at` as `approved_at`. Correlated Store strings are comparison evidence, not a reason to rewrite Store.
4. Leave ambiguous or Store-only values unresolved and on fallback rather than inventing required fields.
5. Obtain human approval for the dry-run cohort, then write complete state lists in bounded batches using authoritative thread identity and idempotent deterministic values.
6. Read back through both direct thread-state inspection and the effective compatibility reader; compare count, content, order, IDs, timestamps, and explicit-empty behavior.
7. Hold a rollback window. On any mismatch, disable state writes/reads for the cohort and return to preserved legacy fallback. Do not delete checkpoint history, Store values, or table rows.
8. Promote state reads only for verified threads. Removing fallback or legacy storage requires a separate approved change after rollback verification.

No empty state list is synthesized merely because a thread has no table rows: that would suppress possible Store-only legacy data. An explicit empty list becomes authoritative only through a human-approved update or an independently evidenced migration case.

## Risks / Trade-offs

- **State presence may be collapsed by an adapter.** Prove omitted-versus-empty behavior before migration; stop rollout if it cannot be preserved.
- **Legacy Store and table values may disagree.** Report both, migrate only an approved unambiguous cohort, and leave the rest on fallback.
- **Checkpoint history contains earlier approved values.** This is expected thread-state history; retention/deletion policy is not changed here.
- **A tool could request another thread.** Do not expose a target-thread parameter and verify runtime authoritative identity.
- **A normal state update could accidentally write Store through existing projection code.** Add tests that ordinary approval/update causes zero Store tent-pole writes and preserves old Store records.
- **Forks copy historical state.** Treat copied state as the fork's own snapshot and prohibit parent lookups; broader fork policy is outside scope.

## Migration / Rollback Plan

The authoritative sequencing is dry-run → reviewed cohort → idempotent state write → direct/effective readback → rollback drill → limited read cutover. Rollback disables the new state path for affected cohorts and resumes preserved fallback. It never empties or deletes legacy records, drops `session_catalog.tent_poles`, or attempts a reverse destructive migration. New approvals must remain disabled during rollback if the system cannot safely represent them in the old string-only path.

## Open Questions

- Which existing authenticated close/review action is the approved mutation boundary, and how will it prove that the person—not a model or tool—approved the complete replacement without a general UI change?
- What exact legacy precedence reproduces deployed behavior when Store strings and table rows disagree? This must be measured and approved before migration.
- Which Agent Server state-update API and checkpoint metadata will be used for out-of-run human updates, and how will idempotency be demonstrated?
- Which legacy timestamp/source combinations constitute sufficient approval evidence? Unapproved cases remain fallback.

Governance reference: `GOVERNANCE_FRAMEWORK.md`.
