## Purpose

Defines the reproducible evidence required to accept Coder behavior across the real deployed services, host integration, disruptions, and authority boundaries.

## ADDED Requirements

### Requirement: Acceptance targets the identified deployment
The acceptance system SHALL verify that the tested frontend is served on port 3002 from this worktree and SHALL identify the live Agent Server, PostgreSQL, Redis signaling, worker processes, native macOS MCP host service, and the Temporal outer bridge when enabled. It MUST record component identity, build or source revision, configuration fingerprint with secrets removed, process or container identity, resource boundary, and observation time.

#### Scenario: In-scope deployment is identified
- **WHEN** acceptance begins against the deployed stack
- **THEN** the evidence identifies port 3002 and correlates every required component to this worktree and acceptance run
- **AND** it records whether the Temporal outer bridge is enabled or disabled

#### Scenario: Wrong frontend boundary is rejected
- **WHEN** the observed frontend is not the port-3002 instance built and served from this worktree
- **THEN** acceptance fails rather than using port 3001, a root `start.command`, or an uncorrelated process as substitute evidence

### Requirement: Evidence is typed by provenance
The acceptance system SHALL classify every observation as source evidence, container/build evidence, or deployed runtime evidence. A passing result MUST be supported by deployed runtime evidence for deployment behavior, and neither source inspection nor image/build success SHALL be treated as proof of live behavior.

#### Scenario: Evidence classes remain distinct
- **WHEN** the final evidence bundle is assembled
- **THEN** each assertion names its evidence class, producer, component identity, correlation identifiers, timestamp, and artifact location
- **AND** unsupported or mismatched evidence is reported as unknown or failed rather than promoted to deployed proof

### Requirement: Required services are refreshed within authorization
The acceptance procedure SHALL explicitly rebuild or recreate artifacts and restart the in-scope frontend, Agent Server API, workers, PostgreSQL and Redis connections or services as required, enabled Temporal bridge, and native MCP host service before or during verification. It MUST NOT deploy, recreate, restart, or otherwise disturb unrelated services.

#### Scenario: In-scope refresh is evidenced
- **WHEN** acceptance prepares the deployment and performs restart scenarios
- **THEN** typed evidence records each authorized build, recreation, restart, readiness check, and resulting identity
- **AND** the tested runtime is shown to consume the refreshed artifacts

#### Scenario: Unrelated service would be affected
- **WHEN** a lifecycle command resolves to a resource outside the enumerated acceptance boundary
- **THEN** the command is refused and the acceptance result records the scope violation without changing that resource

### Requirement: Coder completes deterministic repository work over multiple turns
The acceptance system SHALL direct Coder, only through Jasper, to complete a deterministic, non-trivial repository fixture whose expected mutations and verification results are known in advance. The work MUST require multiple conversation turns, MUST occur in this worktree, and MUST produce durable repository changes and machine-verifiable results rather than a simulated report.

#### Scenario: Multi-turn work succeeds
- **WHEN** the human supplies the fixture request and required follow-up information to Jasper over multiple turns
- **THEN** Coder performs exactly the expected repository mutations
- **AND** independent verification from a separate process confirms the expected content and checks
- **AND** Jasper reports the verified outcome without exposing an internal agent directly

#### Scenario: Report without repository proof
- **WHEN** an agent claims completion but the expected worktree mutation or independent verification is absent
- **THEN** acceptance fails the work item and Jasper reports the discrepancy

### Requirement: Work survives browser disconnect and rejoin
The deployed system SHALL preserve one authoritative conversation, work item, and run identity while the browser disconnects and rejoins during active Coder work. Rejoin MUST recover committed history and resume or observe the authoritative run without creating a replacement run or replaying committed mutations.

#### Scenario: Browser rejoins active work
- **WHEN** the port-3002 browser disconnects after acknowledged progress and later rejoins using the stable conversation identity
- **THEN** it reconciles from durable authority, continues to observe the same work item and run, and displays no duplicate accepted message or mutation

#### Scenario: Rejoin occurs after completion
- **WHEN** the browser rejoins after the run completed while disconnected
- **THEN** it renders the durable terminal result and Jasper summary once without starting another run

### Requirement: Work recovers across service interruptions
The deployed system SHALL be verified across separate Agent Server API, worker, relevant container, Redis signaling, and native macOS MCP host service interruption and recovery events. Durable PostgreSQL authority MUST survive transient signaling and process loss. If the Temporal outer bridge is enabled, its interruption and recovery MUST also be verified; if disabled, evidence MUST mark it not applicable and MUST NOT imply that it was tested.

#### Scenario: API or worker restarts during work
- **WHEN** the API or worker process is restarted after durable progress
- **THEN** the recovered deployment reconciles the same stable identifiers and reaches one truthful terminal outcome without duplicating committed work

#### Scenario: Redis signaling is interrupted
- **WHEN** Redis signaling is unavailable and later restored
- **THEN** transient delivery may pause, but PostgreSQL-backed authority remains intact and clients reconcile missed state without duplicate runs or mutations

#### Scenario: MCP host service is interrupted
- **WHEN** the native macOS MCP host service is stopped during an in-flight host operation and then restarted
- **THEN** the operation resolves through the recorded retry or failure policy under the same idempotency identity
- **AND** no duplicate repository mutation occurs

#### Scenario: Enabled Temporal bridge is interrupted
- **WHEN** the Temporal outer bridge is enabled and is interrupted and recovered during accepted work
- **THEN** outer workflow evidence correlates to the same authoritative work item and does not duplicate the inner Agent Server run or mutation

### Requirement: Separate process and resource boundaries are proven
Acceptance SHALL demonstrate that the browser, Agent Server API, worker, PostgreSQL, Redis, optional Temporal bridge, and native MCP host are separate processes or resources where designed. Evidence MUST come from boundary-appropriate observations rather than assuming separation from source topology.

#### Scenario: Boundary map is captured
- **WHEN** deployment identity evidence is collected
- **THEN** it records distinct process, container, host-service, network, and persistence identities and the communication edges exercised by the scenario

#### Scenario: Claimed boundary is not observable
- **WHEN** two required independent roles cannot be distinguished in deployed evidence
- **THEN** acceptance reports the boundary assertion as failed or unknown rather than inferring it

### Requirement: Stable identifiers and idempotency prevent duplication
Every acceptance request, conversation, work item, Agent Server thread and run, outer workflow when enabled, host operation, and repository mutation SHALL carry stable correlation and idempotency identifiers appropriate to its boundary. Reconnects, retries, redelivery, and recovery MUST converge on one logical run and at most one committed mutation for each intended mutation key.

#### Scenario: Same submission is redelivered
- **WHEN** an identical accepted request is redelivered before and after a disruption with the same idempotency key
- **THEN** the system returns or reconciles the existing logical result and does not create a second run or mutation

#### Scenario: Retry crosses host boundary
- **WHEN** a host operation response is lost and the same operation is retried
- **THEN** the MCP host deduplicates or returns the recorded result under the stable operation key and the repository reflects one committed effect

#### Scenario: Distinct authorized request is issued
- **WHEN** the human intentionally submits a distinct request with a new idempotency identity
- **THEN** the system may create a distinct run and records why it is not a duplicate

### Requirement: Cancellation propagates to every active boundary
An authorized cancellation SHALL be durably recorded against the stable work item and SHALL propagate to the active Agent Server run, worker activity, host operation, and enabled Temporal outer workflow. No new mutation SHALL commit after the cancellation barrier, and any operation that cannot be stopped immediately MUST report its actual state and reconciliation outcome.

#### Scenario: Cancellation during host-backed work
- **WHEN** the human cancels through Jasper while Coder has an active host-backed operation
- **THEN** the cancellation is correlated across all active boundaries
- **AND** post-cancel evidence proves no mutation committed after the barrier or truthfully identifies a race that had already committed

#### Scenario: Cancellation coincides with restart
- **WHEN** cancellation is durably accepted while an API, worker, container, or MCP service is restarting
- **THEN** recovered components observe the cancellation state before resuming work and converge on one non-running terminal authority state

### Requirement: Authority reconciliation is truthful
PostgreSQL-backed durable state SHALL be the authority for accepted conversation, work-item, run, cancellation, and terminal outcome records. Redis and browser state SHALL be treated as projections or signaling. After every disconnect or interruption, the system MUST reconcile UI and summaries to durable authority and MUST expose pending, failed, cancelled, unknown, or partially completed states without claiming success.

#### Scenario: Optimistic state conflicts with durable authority
- **WHEN** browser or signaling state indicates progress or completion that durable authority does not confirm
- **THEN** the deployed UI and Jasper summary adopt the durable status and identify the conflict

#### Scenario: Mutation committed before status delivery
- **WHEN** a repository mutation commits but terminal status delivery is interrupted
- **THEN** reconciliation uses stable identifiers and independent repository evidence to report the committed effect once without rerunning it

### Requirement: Credentials never reach agents
Provider credentials, service secrets, database credentials, and host credentials SHALL remain outside all agent-visible prompts, messages, tool arguments, tool results, graph state, checkpoints, event payloads, summaries, repository mutations, and acceptance artifacts. Verification MUST use redacted metadata, one-way fingerprints, and non-secret canaries designed for the credential boundary; it MUST NOT print or persist secret values.

#### Scenario: Credential isolation is audited
- **WHEN** a full acceptance run and all disruption scenarios finish
- **THEN** boundary instrumentation and artifact scans show that credential values and credential-boundary canaries did not enter any agent-visible channel
- **AND** the evidence contains only safe names, redacted metadata, or one-way fingerprints

#### Scenario: Credential material is detected
- **WHEN** credential material or a credential-boundary canary appears in an agent-visible channel or repository mutation
- **THEN** acceptance fails, output is quarantined and redacted, and Jasper reports a security failure without reproducing the material

### Requirement: Jasper is the sole human-facing agent
Only Jasper SHALL receive human conversation input and present agent-generated progress, questions, cancellation acknowledgements, and final results. Coder and other internal agents MUST remain behind Jasper. Jasper's statements MUST be derived from typed evidence and MUST distinguish observed fact, durable authority, failure, not-applicable status, and unknown state.

#### Scenario: Jasper summarizes successful evidence
- **WHEN** all required assertions have passing typed evidence
- **THEN** Jasper provides a concise human-facing summary that cites stable work and run identifiers, verified repository effects, disruptions exercised, and evidence provenance accurately

#### Scenario: Evidence is incomplete or contradictory
- **WHEN** required evidence is missing, stale, contradictory, failed, or not applicable
- **THEN** Jasper preserves those statuses and does not convert them into an unqualified success claim

#### Scenario: Internal agent output attempts direct presentation
- **WHEN** Coder or another internal agent emits progress or a result
- **THEN** the output is mediated and attributed through Jasper rather than displayed as a separate human-facing agent

### Requirement: Acceptance excludes unsupported claims
The acceptance plan MUST NOT require real-browser speech input or output testing. It MUST NOT use port 3001 or a root `start.command` as evidence for the deployed frontend or startup boundary.

#### Scenario: Browser interaction is exercised
- **WHEN** acceptance drives the port-3002 frontend through a real browser
- **THEN** it verifies typed text, visual state, disconnect, and rejoin behavior without making a speech acceptance claim

#### Scenario: Excluded evidence is supplied
- **WHEN** a result relies on speech behavior, port 3001, or a root `start.command` claim
- **THEN** that result is excluded from the acceptance verdict and reported as out of scope
