## 1. Acceptance contracts and safety boundaries

- [ ] 1.1 Inventory the actual port-3002 frontend, Agent Server API, worker, PostgreSQL, Redis, optional Temporal bridge, and native macOS MCP host lifecycle and observation surfaces; document concrete process, container, host-service, network, and persistence identities without using port 3001 or a root `start.command`.
- [ ] 1.2 Define the acceptance-run manifest and append-only evidence schemas with explicit `source`, `container_build`, and `deployed_runtime` provenance, stable correlation fields, component identities, timestamps, redacted artifact references, and pass/fail/unknown/not-applicable statuses.
- [ ] 1.3 Implement concrete lifecycle target resolution and a fail-closed allowlist that permits rebuild, recreate, restart, interruption, and readiness operations only for the enumerated acceptance services and refuses commands that could affect unrelated resources.
- [ ] 1.4 Implement safe preflight checks for worktree identity and dirty-state digest, port-3002 origin, required service readiness, Temporal enabled/disabled status, available rollback/restore actions, and credential-redacted configuration fingerprints.
- [ ] 1.5 Add automated tests proving lifecycle selection rejects unrelated resources and broad ambiguous targets, evidence classes cannot substitute for one another, and excluded speech, port-3001, and root-`start.command` assertions cannot contribute to a passing verdict.

## 2. Deterministic repository-work fixture

- [ ] 2.1 Add an acceptance-owned, reversible repository fixture with a known initial tree, a non-trivial exact mutation target, a required second-turn input, deterministic checks, unique per-run paths, and an idempotent cleanup/restore contract.
- [ ] 2.2 Add stable request, conversation, work-item, Agent Server thread/run, optional workflow, MCP operation, and repository mutation identities plus a fixture mutation journal or precondition that deduplicates replayed effects.
- [ ] 2.3 Implement an independent verifier process, separate from the Coder worker and MCP mutation producer, that records expected-versus-actual hashes, diff shape, mutation cardinality, and deterministic check results as typed evidence.
- [ ] 2.4 Add fixture-level tests for the success oracle, divergent mutation failure, replay deduplication, intentional new-request identity, and cleanup that preserves evidence while restoring only acceptance-owned fixture state.

## 3. Controller, authority, and disruption instrumentation

- [ ] 3.1 Implement a checkpoint-driven controller that correlates each browser action, lifecycle action, authority observation, host operation, and repository observation to the acceptance manifest without relying on timing sleeps as the disruption trigger.
- [ ] 3.2 Add safe PostgreSQL authority queries and browser/Redis projection observations that can prove conversation, work-item, run, cancellation, and terminal-state reconciliation without exposing credentials or treating signaling as authority.
- [ ] 3.3 Add deterministic duplicate-delivery probes for human submission, reconnect cursor or event delivery, Agent Server run delivery, and lost MCP response retry, with authoritative cardinality assertions for one logical run and at most one intended mutation.
- [ ] 3.4 Add a durable cancellation-barrier scenario and observations for Agent Server, worker activity, MCP host operation, repository mutation order, and enabled Temporal workflow, including truthful handling of a mutation committed before the barrier.
- [ ] 3.5 Add independent disruption adapters and readiness checks for browser disconnect/rejoin, Agent Server API restart, worker restart, relevant application-container recreation/restart, Redis interruption/recovery, native macOS MCP host stop/restart, and enabled Temporal bridge interruption/recovery.
- [ ] 3.6 Add controller tests for checkpoint ordering, bounded recovery, restart-time cancellation, PostgreSQL-versus-projection conflict, optional Temporal not-applicable handling, and failure preservation rather than optimistic success.

## 4. Credential isolation and Jasper reporting

- [ ] 4.1 Implement trusted-boundary credential inventory and scanning that uses safe names, one-way fingerprints, and non-secret boundary canaries and never exports raw provider, service, database, or host secret values.
- [ ] 4.2 Scan agent-visible messages, prompts, graph/checkpoint state, tool arguments/results, events, summaries, admitted log excerpts, and repository diffs; quarantine and redact matches while emitting only safe typed failure metadata.
- [ ] 4.3 Implement the deterministic verdict builder that requires deployed evidence for deployed assertions, preserves contradictions and missing evidence as fail or unknown, and marks a disabled Temporal bridge not applicable rather than passed.
- [ ] 4.4 Constrain the human conversation surface to Jasper and generate Jasper's progress, questions, cancellation acknowledgement, and final summary from the redacted typed verdict projection while keeping Coder and other internal agents non-human-facing.
- [ ] 4.5 Add automated tests that Jasper cannot upgrade failed, unknown, contradictory, or not-applicable evidence; must report fixture effects, identifiers, disruption coverage, and provenance; and never quotes quarantined material or directly presents an internal agent.

## 5. Source and build verification

- [ ] 5.1 Run the acceptance harness's source-level tests and static/schema checks and record them only as source evidence; resolve failures before attempting deployed acceptance.
- [ ] 5.2 Execute the allowlisted build/rebuild steps for the frontend and required application artifacts from this worktree and record image/artifact identities, commands, and outcomes as container/build evidence.
- [ ] 5.3 Recreate or restart the in-scope frontend, Agent Server API, workers, required PostgreSQL/Redis service or connection boundaries, enabled Temporal bridge, and native macOS MCP host service; capture before/after identities and readiness without destructive database-volume recreation.
- [ ] 5.4 Prove from live identity and readiness observations that the deployed port-3002 frontend and each required service consume the refreshed artifacts; stop and preserve a failed verdict if correlation cannot be established.

## 6. Live deployed acceptance

- [ ] 6.1 Start a real typed-text browser session against port 3002, submit the deterministic fixture request only to Jasper, provide the required follow-up in a separate conversation turn, and record that Coder performs the real work while Jasper alone remains human-facing.
- [ ] 6.2 Disconnect and rejoin the browser during active work and after disconnected completion, verifying durable history, stable conversation/work/run identities, one rendered terminal result, and no duplicate accepted message, run, or mutation.
- [ ] 6.3 Execute separate checkpointed API, worker, and relevant container restart/recreation scenarios and verify each recovery reconciles the same authoritative work and terminal outcome across distinct process/resource identities.
- [ ] 6.4 Interrupt and recover Redis signaling while PostgreSQL remains authoritative, then verify missed-state reconciliation and absence of duplicate runs, events presented as new, or repository mutations.
- [ ] 6.5 Interrupt and recover the native macOS MCP host around an in-flight operation, suppress or lose the selected response, retry under the same operation key, and verify one committed repository effect from the independent oracle.
- [ ] 6.6 If Temporal is enabled, interrupt and recover the outer bridge and verify its workflow correlates to one inner Agent Server run and mutation; if disabled, record not applicable and make no claim that this scenario passed.
- [ ] 6.7 Redeliver the same accepted request across disruptions and issue one intentional distinct request, then verify stable IDs and authoritative cardinalities distinguish deduplication from legitimate new work.
- [ ] 6.8 Cancel a separate active fixture through Jasper while host-backed work and a service restart are in play; verify the durable barrier propagates to every enabled boundary and that no post-barrier mutation occurs or any pre-barrier race is reported truthfully.
- [ ] 6.9 Create or observe an optimistic projection conflict and a committed-mutation/status-delivery interruption, then verify the port-3002 UI and Jasper reconcile to PostgreSQL authority plus independent repository evidence without rerunning the mutation.
- [ ] 6.10 Run credential-isolation scans over the complete acceptance corpus and verify no credentials or credential-boundary canaries reached agents, repository mutations, summaries, or admitted artifacts; fail and redact on any match.

## 7. Verdict, restoration, and acceptance record

- [ ] 7.1 Assemble the immutable evidence ledger and machine verdict, cross-check every required spec scenario against deployed-runtime evidence, and retain source and container/build observations as distinct supporting classes only.
- [ ] 7.2 Verify Jasper's final human-facing summary against the machine verdict for exact fixture outcome, stable IDs, duplicate counts, cancellation result, authority reconciliation, disruption coverage, credential status, provenance, and Temporal pass/not-applicable status.
- [ ] 7.3 Confirm the browser record makes no real-browser speech claim and contains no port-3001 or root-`start.command` claim, then record any excluded observation as out of scope rather than acceptance evidence.
- [ ] 7.4 Capture final process/resource boundary identities and service health, restore the fixture and acceptance-owned temporary controls idempotently, and return only in-scope services to their documented desired state without deploying or disturbing unrelated services.
- [ ] 7.5 Publish the redacted machine and Jasper-facing acceptance reports with hashed evidence references; declare acceptance passed only when every required deployed assertion passes, otherwise preserve failed and unknown statuses with actionable evidence links.
