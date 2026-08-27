## Context

See `proposal.md` for motivation and `specs/deployed-coder-acceptance/spec.md` for normative behavior. This is a cross-boundary acceptance design: the port-3002 frontend is served from this worktree, while the Agent Server API and workers, PostgreSQL, Redis signaling, optional Temporal outer bridge, and native macOS MCP host have different lifecycle and evidence surfaces. Source presence, image contents, and live behavior are therefore different facts. The later apply phase is authorized to rebuild, recreate, and restart only these enumerated resources; this proposal phase performs none of those actions.

## Goals / Non-Goals

**Goals:**

- Produce a repeatable acceptance run whose assertions are linked to immutable deployment and correlation metadata.
- Exercise one deterministic repository fixture through multiple Jasper-mediated turns and controlled failures without allowing retries to multiply effects.
- Test recovery and cancellation at actual process, container, host-service, signaling, and persistence boundaries.
- Make the final verdict mechanically derivable from typed evidence and keep Jasper's human summary consistent with it.
- Prove credential isolation without copying credentials into the harness or evidence bundle.

**Non-Goals:**

- Broad production deployment, generalized chaos testing, load testing, or restarting unrelated resources.
- Revalidating every source-level unit test; source checks are prerequisites, not deployed acceptance.
- Real-browser speech testing, port-3001 verification, or startup claims about a root `start.command`.
- Treating disabled Temporal behavior as passed; it is explicitly not applicable.

## Decisions

### 1. Use a run manifest and append-only typed evidence ledger

Before lifecycle work, the harness creates an acceptance-run ID and a manifest enumerating the exact worktree revision and dirty-state digest, frontend origin, expected services, enabled optional components, allowed lifecycle targets, fixture identity, and safe configuration fingerprints. Every assertion references evidence records with a schema such as:

- evidence ID, acceptance-run ID, scenario and assertion ID;
- provenance class: `source`, `container_build`, or `deployed_runtime`;
- producer boundary and observed boundary;
- conversation, request, work-item, thread, run, workflow, host-operation, and mutation IDs where applicable;
- process/container/service identity and observation timestamp;
- redacted payload reference, result status, and reason.

The ledger is append-only for the run; a derived verdict cannot rewrite failed or unknown records. Large logs remain external with hashes and bounded excerpts, and secret scanning happens before excerpts are admitted.

**Why:** this prevents a build log or source assertion from silently standing in for live proof and gives Jasper a constrained source for summaries. **Alternative considered:** a narrative checklist was rejected because it cannot enforce provenance, correlation, or contradiction handling.

### 2. Gate acceptance on an allowlisted deployment refresh

The harness first resolves concrete lifecycle targets for the port-3002 frontend, Agent Server API and workers, PostgreSQL/Redis resources or their required connection lifecycle, enabled Temporal bridge, and native MCP launchd/service identity. It compares the resolved set with the manifest allowlist before issuing commands. It then records build/recreate/restart commands, exit status, before/after identities, readiness, and worktree/build correlation.

Database persistence is preserved while process or container restart behavior is exercised; destructive volume recreation is not implied. An unrelated target or ambiguous broad compose/project command fails closed. Native macOS MCP lifecycle commands are separately allowlisted because they execute outside the container boundary.

**Why:** stale containers are a common false-positive source, but broad stack operations exceed authorization. **Alternative considered:** inspecting image timestamps without recreation was rejected because that does not prove the deployed process consumes the intended build.

### 3. Use a deterministic, reversible acceptance fixture with an independent oracle

Apply will create a dedicated fixture isolated from product source behavior. Its request has a known initial tree, a multi-turn information dependency, exact expected file mutations, deterministic checks, and a cleanup/restore procedure. The browser supplies turn one to Jasper, waits for a durable question or checkpoint, then supplies turn two. Coder must use the real repository/MCP path. A separate verifier process that is neither the Coder worker nor MCP operation producer computes file hashes, diff shape, commit/effect count, and check results.

Each intended mutation has a stable mutation key and a journal/precondition so replay returns the prior result or detects divergence. The fixture is unique per acceptance-run ID while expected semantics remain fixed.

**Why:** a canned no-op can pass without proving repository authority, while arbitrary work is not repeatable. **Alternative considered:** asking Coder to describe a change without applying it was rejected because it provides no real repository proof.

### 4. Drive a fixed disruption matrix with durable checkpoints

A controller advances only after observing named durable checkpoints, making failure timing reproducible. At selected checkpoints it performs:

1. browser network disconnect, browser disposal if needed, and rejoin by stable conversation ID;
2. independent Agent Server API restart;
3. independent worker restart;
4. relevant application-container recreation/restart;
5. Redis signaling interruption/recovery while PostgreSQL remains authoritative;
6. native macOS MCP host stop/restart around a host operation;
7. Temporal outer bridge interruption/recovery only when the manifest says it is enabled.

The suite uses more than one fixture instance where mutually exclusive outcomes are required (for example successful recovery versus cancellation), but each instance uses the same deterministic fixture definition and unique stable IDs. Every disruption captures before/after boundary identities and readiness. Recovery is judged from PostgreSQL authority plus independent repository evidence, not from uninterrupted streaming.

**Why:** sleep-based disruption is nondeterministic and tends to miss the intended window. **Alternative considered:** killing the whole stack at once was rejected because it cannot attribute recovery behavior to separate boundaries.

### 5. Establish an identifier chain and deduplication assertions

The manifest defines relationships without assuming one ID serves every subsystem: acceptance run → human request/idempotency key → conversation → work item → Agent Server thread/run → optional Temporal workflow → MCP host operation → repository mutation key. Retries retain the boundary-specific stable key; intentional new requests receive new keys.

The controller deliberately repeats submissions, reconnect cursors, run delivery, and a host operation whose first response is suppressed. It then queries authoritative stores and the fixture oracle to assert one logical run per accepted request and one committed effect per mutation key. Cardinality and uniqueness evidence is collected before cleanup.

**Why:** UI appearance alone cannot establish exactly-once effects. **Alternative considered:** relying only on generated database IDs was rejected because retries may create fresh IDs before duplication is noticed.

### 6. Model cancellation as a durable barrier, not a UI event

A cancellation scenario records the authority timestamp/sequence and cancellation ID before disrupting or recovering components. Propagation evidence is gathered from the Agent Server run, worker, MCP operation, and enabled outer workflow. The independent oracle compares mutation journal positions with the barrier. If a mutation committed before the barrier but its notification arrived later, the verdict says so; if a mutation commits after the barrier, cancellation fails.

**Why:** claiming that a button click stopped work is not proof. **Alternative considered:** requiring instantaneous process death was rejected because some operations are not preemptible and truthful reconciliation is the stronger contract.

### 7. Treat PostgreSQL as authority and Redis/browser data as projections

At each disruption, the controller snapshots safe authoritative records and projection observations under the same identifier chain. On rejoin, it verifies that browser state and Jasper's status converge to durable records. Redis loss can delay events but cannot change the durable outcome. Repository evidence resolves the special case where a mutation committed before terminal status was persisted or delivered; idempotency then prevents replay.

**Why:** availability signals and optimistic UI state are not durable truth. **Alternative considered:** accepting the latest observed event as authority was rejected because events can be delayed, dropped, or replayed.

### 8. Verify credential isolation with safe boundary instrumentation

The acceptance harness never ingests raw secret values into reports. It inventories credential sources by safe variable/secret names and obtains one-way fingerprints inside the trusted credential boundary. Non-secret unique canaries are placed only at equivalent credential-injection boundaries. Instrumentation scans serialized agent inputs/outputs, tool envelopes, graph/checkpoint state, events, summaries, admitted log excerpts, and fixture diffs for canaries and, inside the trusted scanner only, secret fingerprints. Scanner output is boolean/location metadata with redaction, never matched values.

Any match quarantines the raw artifact, emits a redacted failure record, and prevents Jasper from quoting it. Access to the quarantine is outside agents.

**Why:** copying secrets into a test process to search for them creates the exposure being tested. **Alternative considered:** dumping environment and logs into the evidence bundle was rejected as unsafe.

### 9. Generate Jasper's summary from a constrained verdict projection

Only Jasper is connected to the human conversation surface. Internal agent events are stored as typed internal evidence and rendered to the human only through Jasper. A deterministic verdict builder groups required assertions as pass, fail, unknown, or not applicable and supplies Jasper a redacted projection. Jasper may improve wording but cannot change statuses or claim an untested optional component passed. A machine comparison checks that the rendered summary includes required failures, unknowns, fixture outcome, disruption coverage, and provenance distinctions.

**Why:** free-form agent summaries can omit caveats. **Alternative considered:** exposing Coder's stream directly was rejected because it violates the sole human-facing-agent boundary.

## Risks / Trade-offs

- **[Restart timing creates flaky scenarios]** → Use durable checkpoint triggers, bounded waits, explicit readiness probes, and preserve raw timing evidence.
- **[A lifecycle selector expands beyond scope]** → Resolve and compare concrete resource identities to the manifest allowlist before execution; fail closed on ambiguity.
- **[Acceptance fixture contaminates the worktree]** → Snapshot the initial state, isolate fixture paths, record exact diffs, and provide an idempotent cleanup/restore step that runs only after evidence capture.
- **[Database restart is confused with destructive recreation]** → Separate process/container lifecycle from persistent volume lifecycle and prohibit destructive volume operations.
- **[Optional Temporal status is misrepresented]** → Freeze enabled/disabled status in the initial manifest; disabled yields not applicable, never pass.
- **[Secret scanning itself leaks values]** → Run comparison inside a trusted boundary and export only redacted locations, booleans, and one-way fingerprints.
- **[A committed effect races cancellation]** → Record ordered barriers and mutation journal evidence and report the race truthfully rather than forcing a preferred narrative.
- **[Browser automation tempts speech claims]** → Limit browser assertions to typed text, visual state, network disconnect, and rejoin; explicitly label speech untested.

## Migration Plan

1. Add the isolated acceptance fixture, evidence schemas, controller, independent oracle, redaction scanner, and Jasper verdict projection without changing unrelated deployment behavior.
2. Add preflight discovery and allowlists for the concrete port-3002, container/process, datastore, optional Temporal, and native MCP boundaries.
3. Run source-level validation of the harness, then build/recreate/restart only enumerated services and capture container/build correlation.
4. Execute the deployed scenario matrix, preserving typed evidence before fixture cleanup.
5. Emit machine and Jasper-facing verdicts; acceptance passes only if every required deployed assertion passes and disabled optional assertions are marked not applicable.
6. On harness or deployment failure, stop further disruptive steps, preserve evidence, restore only fixture state and acceptance-owned temporary configuration, and return services to their documented pre-run desired state. Do not roll back or redeploy unrelated services.
