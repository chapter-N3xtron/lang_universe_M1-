## Purpose

Defines a protected, independently addressable registration for the authoritative Coder graph and a reliable service-only bridge from Temporal activities to Agent Server runs.

## ADDED Requirements

### Requirement: Independent authoritative Coder registration
The system SHALL register the authoritative Coder graph as a second Agent Server graph with a stable graph identifier independently addressable from the Jasper graph. The registration SHALL reference the same authoritative Coder graph definition used for Coder-focused behavior and SHALL NOT create a divergent duplicate implementation.

#### Scenario: Internal caller addresses Coder directly
- **WHEN** an authorized internal service caller submits a run to the stable Coder graph identifier
- **THEN** Agent Server starts or reattaches to a run of the authoritative Coder graph without routing the request through Jasper

#### Scenario: Jasper remains independently addressable
- **WHEN** a caller addresses the Jasper graph after Coder registration is enabled
- **THEN** Agent Server resolves Jasper independently and does not substitute or automatically invoke the standalone Coder registration

### Requirement: Jasper-only product exposure
The product UI and normal-user interfaces SHALL expose Jasper as the only directly selectable or invocable graph. The standalone Coder registration SHALL be reserved for focused authorized tests and internal service orchestration.

#### Scenario: Normal user views available agents
- **WHEN** a browser or normal-user identity requests the product's available agents or graph choices
- **THEN** Jasper is available and the standalone Coder graph is not presented

#### Scenario: Focused test invokes Coder
- **WHEN** a focused service-level test authenticates with an identity authorized for standalone Coder access
- **THEN** the test can address the Coder graph without making Coder available to normal users

### Requirement: Agent Server enforces Coder access policy
Graph registration SHALL NOT be treated as an authorization boundary. Agent Server authorization SHALL deny browser and normal-user identities from directly invoking the standalone Coder graph and SHALL deny or filter Coder enumeration and metadata disclosure on graph-discovery surfaces as appropriate. It SHALL permit Coder invocation only to the designated authenticated Temporal or internal service identity and explicitly authorized focused-test identities.

#### Scenario: Browser attempts direct invocation
- **WHEN** a browser or normal-user identity submits a request directly to the standalone Coder graph identifier
- **THEN** Agent Server denies the request before a Coder thread or run is created

#### Scenario: Normal user enumerates graphs
- **WHEN** a normal-user identity calls an allowed graph-listing or graph-metadata surface
- **THEN** the response does not disclose the standalone Coder registration or otherwise grant a path to invoke it

#### Scenario: Internal Temporal identity invokes Coder
- **WHEN** the designated Temporal service identity submits an authorized Coder request
- **THEN** Agent Server permits the request subject to the same input validation and run controls as other internal requests

#### Scenario: Unauthenticated caller attempts Coder access
- **WHEN** a caller without a valid internal identity invokes or requests metadata for the standalone Coder graph
- **THEN** Agent Server denies access without relying on graph-name secrecy

### Requirement: Explicit Temporal Activity bridge and ownership boundary
Coder orchestration SHALL use an explicit Temporal Activity-to-Agent-Server API bridge. Temporal SHALL own outer workflow scheduling, activity retries, durable timers, and workflow cancellation decisions; Agent Server SHALL own the inner Coder run lifecycle and thread state. Registration of the Coder graph SHALL NOT be represented as native Temporal integration.

#### Scenario: Temporal schedules Coder work
- **WHEN** a Temporal workflow reaches a Coder operation
- **THEN** a Temporal activity invokes Agent Server through the explicit bridge and Agent Server owns the resulting inner thread and run state

#### Scenario: Transient bridge failure occurs
- **WHEN** the activity loses its response or encounters a retryable transport failure
- **THEN** Temporal applies the outer activity retry policy while Agent Server remains authoritative for any inner run already accepted

#### Scenario: Inner run reports a terminal failure
- **WHEN** Agent Server reports that the Coder run failed terminally
- **THEN** the activity reports that outcome to the Temporal workflow without transferring outer retry or timer ownership to Agent Server

### Requirement: Stable correlated identifiers
Each bridged Coder operation SHALL have stable operation, Temporal workflow, Agent Server thread, and Agent Server run identifiers. The bridge SHALL transmit or durably correlate these identifiers so retries, reattachment, cancellation, status inspection, and reconciliation refer to the same logical operation. Once assigned, an identifier SHALL NOT be replaced merely because an activity attempt or client connection is retried.

#### Scenario: Activity retries after acceptance
- **WHEN** an activity attempt is retried after Agent Server may have accepted the start request
- **THEN** the retry uses the same operation, workflow, and thread identifiers and resolves the previously assigned run identifier if one exists

#### Scenario: Client reconnects to an existing run
- **WHEN** the bridge reconnects after losing a stream or polling response
- **THEN** it uses the stable thread and run identifiers to observe the same inner run

#### Scenario: Correlation is inspected operationally
- **WHEN** an operator or reconciler inspects either side of a bridged operation
- **THEN** the recorded correlation data identifies its operation, workflow, thread, and run counterparts without heuristic matching

### Requirement: Idempotent start or reattach
Starting a bridged Coder operation SHALL be idempotent by stable operation identity. Repeated equivalent start requests SHALL create at most one logical active Coder run and SHALL reattach to or return the existing run when it has already been accepted. Reuse of an operation identity with conflicting immutable inputs SHALL fail explicitly rather than starting different work.

#### Scenario: Start response is lost
- **WHEN** Agent Server accepts a start request but the activity does not receive the response and retries the same operation
- **THEN** the bridge returns or reattaches to the accepted run instead of creating a duplicate logical run

#### Scenario: Existing run is terminal
- **WHEN** a start-or-reattach request uses an operation identity whose run already completed
- **THEN** the bridge returns the recorded terminal outcome and does not rerun the operation

#### Scenario: Operation identity is reused with different input
- **WHEN** a request presents an existing operation identity with conflicting graph, thread, or immutable operation input
- **THEN** the bridge returns a non-retryable identity-conflict error and does not create another run

### Requirement: Cancellation propagation
A Temporal cancellation decision for a bridged Coder operation SHALL propagate through the activity bridge to the correlated Agent Server run. Cancellation delivery SHALL be idempotent, SHALL tolerate activity retries and already-terminal runs, and SHALL expose enough state for Temporal to distinguish confirmed inner cancellation, prior terminal completion, and an unresolved delivery failure.

#### Scenario: Running operation is cancelled
- **WHEN** Temporal cancels an outer workflow while its Coder run is nonterminal
- **THEN** the bridge requests cancellation of the correlated Agent Server run and reports the confirmed resulting state to Temporal

#### Scenario: Cancellation request is retried
- **WHEN** cancellation delivery is retried for the same operation and run
- **THEN** Agent Server does not create work or produce a contradictory terminal state and returns the current terminal or cancellation status

#### Scenario: Run completes before cancellation arrives
- **WHEN** the correlated run reaches a terminal state before the cancellation request is processed
- **THEN** the bridge reports that terminal state and does not rewrite it as cancelled

### Requirement: Orphan reconciliation
The system SHALL reconcile bridged operations whose Temporal workflow ownership and Agent Server run state no longer agree. Reconciliation SHALL use stable identifiers, SHALL be safe to repeat, and SHALL either reattach/recover the authoritative outcome, propagate required cancellation, or record an explicit unresolved failure for operator action; it SHALL NOT silently start unrelated replacement work.

#### Scenario: Outer workflow is active and inner run exists
- **WHEN** reconciliation finds an active Temporal operation with a correlated nonterminal Agent Server run but no current activity connection
- **THEN** it makes the existing run available for reattachment without starting a duplicate

#### Scenario: Inner run has no live outer owner
- **WHEN** reconciliation finds a nonterminal Coder run whose correlated Temporal workflow is cancelled, terminated, or absent
- **THEN** it idempotently requests inner-run cancellation and records the reconciliation outcome

#### Scenario: Inner run completed while outer state was disconnected
- **WHEN** reconciliation finds a terminal Coder run whose Temporal operation lacks the outcome
- **THEN** it recovers and correlates that terminal outcome for the outer workflow or records an explicit unresolved handoff failure

#### Scenario: Correlation is incomplete
- **WHEN** reconciliation cannot safely identify all counterparts of an orphan candidate
- **THEN** it records an actionable unresolved condition and does not guess, duplicate, or cancel unrelated work

### Requirement: Preview plugins remain excluded
This capability SHALL use the explicit activity bridge and SHALL NOT adopt the public-preview native LangGraph plugin or the prerelease Deep Agents plugin.

#### Scenario: Runtime dependencies are reviewed
- **WHEN** the Coder registration and Temporal bridge dependencies and configuration are validated
- **THEN** neither excluded preview plugin is required or enabled for this capability
