## Context

See `proposal.md` for motivation. Agent Server can host more than one named graph, but adding a graph entry only makes it addressable; it does not establish caller authorization or Temporal lifecycle semantics. The authoritative Coder graph must remain a single graph definition, Jasper must remain the sole product-facing agent, and the cross-runtime contract must tolerate retries and lost responses without creating duplicate work. The requirements are defined in `specs/independent-coder-registration/spec.md`.

This design spans Agent Server registration and authorization plus Temporal activity orchestration. Agent Server is authoritative for inner thread/run state. Temporal is authoritative for outer workflow scheduling, retries, timers, and cancellation intent.

## Goals / Non-Goals

**Goals:**

- Add one stable, independently addressable Agent Server registration that points to the authoritative Coder graph definition.
- Make standalone Coder access a resource-aware service authorization decision rather than relying on an undisclosed graph name.
- Define an explicit activity adapter with deterministic correlation, idempotent start-or-reattach, cancellation propagation, and repeatable orphan reconciliation.
- Preserve clear observability across operation, Temporal workflow, Agent Server thread, and Agent Server run identities.
- Make focused tests possible without adding Coder to normal product discovery or selection.

**Non-Goals:**

- Embedding Coder in Jasper or defining Jasper-to-Coder delegation behavior.
- Designing or migrating the persistence layer; this change only uses the authoritative state owned by each runtime and records the correlation contract required by later persistence work.
- Changing UI behavior, adding MCP, or defining deployment topology and rollout automation.
- Making graph registration itself a security control or a native Temporal integration.
- Adopting the public-preview native LangGraph plugin or prerelease Deep Agents plugin.

## Decisions

### 1. Register a second graph entry that imports the authoritative Coder graph

The Agent Server graph manifest/configuration will gain a stable Coder graph identifier whose target is the existing authoritative Coder graph export. Jasper remains a separate entry and no wrapper, fork, or copied Coder definition is introduced. A focused registration test will resolve the Coder entry and verify its identity separately from Jasper.

This gives internal tests and orchestration a direct target while preventing implementation drift. An alternative was to route every test and Temporal request through Jasper; that would test delegation behavior rather than Coder itself and would couple outer orchestration to Jasper. A second copied graph was rejected because it could diverge from the authoritative graph.

### 2. Enforce graph-resource authorization at Agent Server

Authentication establishes caller identity; authorization then evaluates the requested graph and operation before graph metadata is returned or a thread/run is created. The designated Temporal/service identity and explicit focused-test identity may invoke standalone Coder. Browser and normal-user identities are denied direct Coder operations. Discovery responses available to those identities omit Coder, and direct metadata lookup remains denied so filtering is not mistaken for name-based security.

The product-facing agent catalog continues to advertise only Jasper. This is defense in depth, not the primary authorization check. Stable service credentials and claim issuance are deployment concerns; the code contract consumes an authenticated service principal and does not place reusable service credentials in browser code.

Alternatives considered were an unlisted graph and network-only isolation. An unlisted graph is not an authorization boundary, and network location alone does not provide resource-level policy when identities share an Agent Server endpoint.

### 3. Use an explicit Temporal activity adapter

A conventional Temporal activity invokes the supported Agent Server API/SDK to create, inspect, wait for, and cancel an inner Coder run. The adapter does not run graph code in the Temporal worker and does not install a native integration plugin. The workflow controls activity retry policy, schedule-to-close/start-to-close timeouts, durable timers, and cancellation intent. The adapter reports Agent Server terminal state back to the workflow; it does not ask Agent Server to emulate Temporal scheduling.

While waiting, the activity periodically observes the correlated run and heartbeats its correlation and latest known state. A reconnect resumes observation of that run rather than submitting fresh work. Retryable transport errors remain activity failures; authoritative terminal graph failures are returned as operation outcomes according to the workflow contract.

The native LangGraph plugin and Deep Agents plugin were rejected because the named releases are preview/prerelease and would obscure the explicit ownership boundary required by this phase.

### 4. Derive a stable identity tuple per logical operation

The workflow assigns a stable `operation_id` from the Temporal `workflow_id` plus a workflow-defined operation slot/key, never from an activity attempt number. The bridge deterministically derives or otherwise preassigns the Agent Server `thread_id` and `run_id` from that operation identity before the first start request. IDs use a namespaced UUID-compatible derivation where API formats require UUIDs. Every request and run metadata record carries the complete tuple:

- `operation_id`
- `workflow_id`
- `thread_id`
- `run_id`
- immutable request fingerprint

A Temporal continue-as-new or activity retry carries the same tuple for the same logical operation. A genuinely new Coder operation receives a new operation slot and tuple. Logs and status results include the tuple but exclude credentials and sensitive input.

Random IDs generated only after a response were rejected because a lost create response would make safe reattachment ambiguous. Attempt-number-based IDs were rejected because they turn activity retries into duplicate runs.

### 5. Implement start as create-or-reattach with conflict detection

The adapter's start flow is:

1. Validate that the requested graph is the standalone Coder graph and compute the immutable request fingerprint.
2. Inspect the preassigned thread/run identity.
3. If the run exists, verify its operation metadata and fingerprint, then return its current state or reattach to it.
4. If it does not exist, create the thread idempotently and submit the run with the preassigned run identity and full correlation metadata.
5. If creation reports an already-existing identity, read and validate that run, treating an equivalent request as success.

A mismatch in graph, identity tuple, or immutable request fingerprint is a non-retryable identity conflict. Terminal runs are returned as terminal outcomes and are never restarted under the same operation identity.

This relies on Agent Server's stable resource identity/conflict semantics rather than introducing a second state database in this phase. A process-local deduplication map was rejected because it fails after worker restart and cannot support reconciliation.

### 6. Propagate cancellation as an idempotent state transition

On Temporal cancellation, the activity cancellation handler uses the stable tuple to request cancellation of a nonterminal Agent Server run. It then performs a bounded status check and reports one of: cancellation confirmed, run already terminal, or cancellation delivery unresolved. Repeated cancellation calls inspect and return current state; they do not create a thread or run. If the run completed before cancellation won the race, its existing terminal state is preserved.

Temporal remains owner of the outer cancellation decision even if delivery is temporarily unresolved. Swallowing activity cancellation without contacting Agent Server was rejected because it leaves expensive orphan runs. Treating every delivery timeout as confirmed was rejected because it hides unresolved inner work.

### 7. Reconcile by stable identity and explicit ownership state

A repeatable reconciliation operation compares Temporal workflow state with Agent Server thread/run state using the identity tuple. It classifies records as:

- active outer operation plus existing inner run: reattach or resume observation;
- active outer operation plus no accepted inner run: permit the normal idempotent start path;
- cancelled, terminated, or absent outer owner plus nonterminal inner run: request inner cancellation;
- terminal inner run plus missing outer outcome: recover the outcome to the owning workflow path or record a handoff failure;
- incomplete or conflicting correlation: quarantine as an actionable unresolved condition without guessing.

Reconciliation actions and outcomes are recorded with the tuple and are themselves idempotent. A replacement run is never created merely because a previous activity connection disappeared. Time-based guessing without identity correlation was rejected because it can cancel unrelated work.

### 8. Verify each boundary independently

Focused tests will cover graph resolution, Jasper/normal-user non-exposure, direct-access denial, authorized service invocation, equivalent retry reattachment, conflicting-operation rejection, reconnect, cancellation races, and each orphan classification. Tests will simulate a lost create response and an activity retry to prove that one logical run is used. Dependency/configuration checks will verify that neither excluded preview plugin is enabled.

End-to-end UI, persistence, MCP, and deployed acceptance tests remain in their dedicated phases.

## Risks / Trade-offs

- **[Risk] Agent Server create semantics do not accept or atomically conflict on a caller-supplied run identity** → Confirm the supported API contract before bridge implementation; if atomic stable identity cannot be provided, stop rather than substituting process-local deduplication, because the idempotency requirement would not be met.
- **[Risk] Discovery filtering is mistaken for security** → Test direct invocation and direct metadata lookup denial independently from list filtering.
- **[Risk] Activity cancellation races with normal completion** → Read the authoritative terminal state after the cancellation request and preserve an already-terminal result.
- **[Risk] Reconciliation could act on stale or malformed correlation data** → Require a complete, matching tuple and immutable fingerprint before automated action; quarantine ambiguous records.
- **[Risk] A second graph entry could drift to a different Coder implementation** → Resolve both focused tests and registration from the one authoritative graph export and reject copied wrappers.
- **[Trade-off] One thread per logical Coder operation favors simple idempotency and ownership over cross-operation thread reuse** → Keep cross-operation/session reuse for a later design that can preserve the same guarantees.

## Migration Plan

1. Add and verify the standalone Coder registration while keeping it unavailable to normal-user identities and product discovery.
2. Add authorization policy tests before enabling any internal caller.
3. Add the activity adapter and correlation contract, then exercise start/retry/reattach and cancellation against focused test identities.
4. Add reconciliation tests and operational result reporting.
5. Enable only the intended internal service path in the applicable environment through separate deployment work.

Rollback disables internal invocation and removes the Coder registration after allowing or cancelling correlated nonterminal runs. Jasper remains registered throughout. No persistence or data migration is part of this change.
