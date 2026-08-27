## 1. Confirm Runtime Contracts

- [ ] 1.1 Verify the installed Agent Server API supports caller-stable thread and run identities with atomic existing-identity conflict behavior; record the supported request/read/cancel operations and stop implementation if they cannot satisfy idempotent start-or-reattach.
- [ ] 1.2 Identify the single authoritative Coder graph export and the existing Jasper graph registration path, confirming that the new entry can reference Coder without a copied wrapper or implementation fork.
- [ ] 1.3 Confirm the bridge can use the supported Agent Server client/API without adding or enabling the public-preview native LangGraph plugin or prerelease Deep Agents plugin.

## 2. Register and Protect the Coder Graph

- [ ] 2.1 Add the stable standalone Coder graph entry to Agent Server configuration while leaving Jasper independently registered and unchanged as the product-facing graph.
- [ ] 2.2 Add graph-resource authorization rules that permit the designated Temporal/service and focused-test identities while denying browser, normal-user, and unauthenticated direct Coder invocation before thread/run creation.
- [ ] 2.3 Filter or deny standalone Coder graph listing and metadata access for browser and normal-user identities, retaining direct metadata denial even when list filtering is active.
- [ ] 2.4 Add focused registration and authorization tests covering authoritative graph resolution, Jasper separation, authorized service access, direct denial, and normal-user non-enumeration.

## 3. Define Stable Bridge Identity

- [ ] 3.1 Define the activity bridge request/result contract for `operation_id`, `workflow_id`, `thread_id`, `run_id`, immutable request fingerprint, graph input, and terminal or unresolved outcomes.
- [ ] 3.2 Implement deterministic, API-compatible thread/run identity derivation from the stable workflow and operation key, excluding activity attempt numbers from identity generation.
- [ ] 3.3 Attach the complete correlation tuple and immutable fingerprint to Agent Server run metadata and structured bridge observations without logging credentials or sensitive graph input.
- [ ] 3.4 Add unit tests proving identical logical operations retain all four IDs across activity retries and reconnects, while distinct operation keys produce distinct identities.

## 4. Implement Activity Start, Reattach, and Observation

- [ ] 4.1 Implement the explicit Temporal activity adapter over supported Agent Server create, read, observe, and cancel APIs without running graph code inside the Temporal worker.
- [ ] 4.2 Implement create-or-reattach using the preassigned thread/run identities, equivalent existing-identity conflicts as success, and immutable tuple/fingerprint mismatches as non-retryable errors.
- [ ] 4.3 Return recorded terminal outcomes for repeated completed operations and prevent rerun under an existing operation identity.
- [ ] 4.4 Implement reconnectable run observation with activity heartbeats while preserving Temporal ownership of activity retries, timers, and outer scheduling.
- [ ] 4.5 Add tests for first start, lost create response, retried start, existing terminal run, reconnect, conflicting identity reuse, retryable transport failure, and terminal inner failure.

## 5. Propagate Cancellation

- [ ] 5.1 Implement the activity cancellation path that requests cancellation of the correlated nonterminal Agent Server run and performs a bounded authoritative status check.
- [ ] 5.2 Return distinct outcomes for confirmed cancellation, prior terminal completion, and unresolved cancellation delivery without rewriting an existing terminal state.
- [ ] 5.3 Add tests for running cancellation, repeated cancellation delivery, transport failure during cancellation, and completion racing with cancellation.

## 6. Reconcile Orphaned Operations

- [ ] 6.1 Implement repeatable reconciliation classification using the complete stable identity tuple and authoritative Temporal workflow and Agent Server run states.
- [ ] 6.2 Implement safe actions for reattaching an active operation, allowing the normal idempotent start path when no run was accepted, cancelling an ownerless nonterminal run, and recovering a disconnected terminal outcome.
- [ ] 6.3 Record incomplete, conflicting, or failed handoffs as actionable unresolved reconciliation results without guessing identities, cancelling unrelated work, or silently starting replacements.
- [ ] 6.4 Add tests for every reconciliation class, repeated reconciliation, malformed correlation, stale observations, and cancellation of an inner run whose outer owner is absent or terminal.

## 7. Verify Scope and Capability

- [ ] 7.1 Run focused integration tests proving the Temporal activity is the outer scheduler/retry/timer/cancellation owner and Agent Server remains the inner run/thread-state owner.
- [ ] 7.2 Verify product-facing agent discovery still exposes only Jasper and that no UI, Jasper embedding, persistence implementation, MCP, or deployment changes were introduced.
- [ ] 7.3 Verify dependency manifests and runtime configuration contain neither excluded preview plugin, then run the repository's applicable graph, authorization, bridge, and static checks.
