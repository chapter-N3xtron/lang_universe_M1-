## Purpose

Defines a single Jasper-facing agent topology in which the complete authoritative Coder graph executes locally as a durable nested LangGraph subgraph with explicit state-boundary mapping.

## ADDED Requirements

### Requirement: Jasper locally embeds the authoritative Coder graph
The system SHALL compose the same complete authoritative Coder graph used by other Coder consumers as a genuine local compiled subgraph within Jasper. The Jasper-to-Coder path MUST NOT copy or independently reassemble Coder internals, invoke Coder as a sibling through a manual graph `ainvoke` handoff, or use a same-deployment `RemoteGraph`.

#### Scenario: Jasper delegates a repository task
- **WHEN** Jasper accepts a coding task for the selected repository and execution mode
- **THEN** the task enters the locally embedded authoritative Coder subgraph through a LangGraph edge in Jasper's graph
- **AND** no sibling top-level Coder node or same-deployment remote graph mediates the delegation

#### Scenario: Authoritative Coder behavior changes
- **WHEN** the authoritative Coder graph gains or changes an internal node, tool, or policy behavior without changing its published boundary
- **THEN** Jasper's embedded execution uses that same graph construction without requiring a duplicate Coder assembly to be updated

### Requirement: Jasper and Coder state are mapped explicitly
The system SHALL define an explicit input mapping from Jasper state to the Coder input schema and an explicit output mapping from Coder output to Jasper state. The mapping MUST account for differing schemas and message reducers, MUST pass only the Coder inputs required by the authoritative boundary, and MUST prevent Coder-internal state from being merged accidentally into unrelated Jasper channels.

#### Scenario: Coding input is prepared
- **WHEN** Jasper delegates a task
- **THEN** the Coder subgraph receives the delegated task as its input message context together with the selected workspace, model, execution mode, thread identity, user identity, and existing coding-session identity supported by the authoritative boundary
- **AND** Jasper-only response, visualization, routing, and session-projection fields are not treated as Coder state

#### Scenario: Coding output returns to Jasper
- **WHEN** the Coder subgraph completes, blocks, errors, or produces a resumable interruption
- **THEN** the output boundary maps the supported final Coder messages, coding status, coding-session identity, workspace, and execution manifest back to the corresponding Jasper channels
- **AND** message conversion preserves final-result attribution without replaying the delegated input or exposing internal tool transcripts as user-facing Jasper output

#### Scenario: Output mapping is extended by Phase 6
- **WHEN** a later change adds the Phase 6 typed Coder report contract
- **THEN** that contract can be added at the Coder-output mapping seam without replacing the local subgraph topology
- **AND** this capability does not prescribe the typed report's fields or semantics

### Requirement: Nested checkpointing inherits the parent runtime
The locally compiled Coder subgraph SHALL use the default `checkpointer=None`. It MUST NOT use `checkpointer=False` and MUST NOT bind a concrete saver, so the nested execution inherits the parent Agent Server checkpointer for each invocation and retains LangGraph interrupt and durability behavior.

#### Scenario: Coder interrupts for approval
- **WHEN** an operation in the nested Coder graph triggers an approval interrupt
- **THEN** the interrupt propagates through Jasper with its nested graph namespace intact
- **AND** resuming the same Jasper thread continues the interrupted nested Coder execution rather than starting a replacement run

#### Scenario: Parent execution is restored
- **WHEN** Agent Server restores a Jasper thread containing an incomplete or interrupted Coder subgraph execution
- **THEN** the nested Coder execution state is restored from the parent-injected checkpointer
- **AND** no application-selected Coder saver or secondary thread authority is consulted

#### Scenario: Graph construction is inspected
- **WHEN** Jasper's nested Coder graph is constructed outside a running Agent Server invocation
- **THEN** its compiled configuration remains persistence-neutral with `checkpointer=None`

### Requirement: Coder autonomy and tool behavior are preserved
Embedding Coder in Jasper SHALL preserve the authoritative Coder graph's autonomous agent loop, complete tool access, execution-mode rules, workspace and identity handling, approval interrupts, progress behavior, completion behavior, execution-manifest reporting, and sanitized failure behavior. Jasper MUST NOT replace Coder's loop with a single model call or a reduced tool set.

#### Scenario: Autonomous coding task runs
- **WHEN** Jasper delegates a task in autonomous mode
- **THEN** the embedded Coder may plan, inspect, edit, execute, and verify through the same authoritative tools and policy boundaries available to standalone Coder execution
- **AND** Jasper does not interpose per-step orchestration that removes Coder autonomy

#### Scenario: Approval-mode tool requires review
- **WHEN** the embedded Coder requests an operation governed by approval mode
- **THEN** the same authoritative interrupt policy pauses the nested run for human review

#### Scenario: Coder encounters a boundary error
- **WHEN** the authoritative Coder graph rejects a workspace, lacks a dependency, or fails internally
- **THEN** Jasper receives the authoritative sanitized status and final failure result through the output mapping

### Requirement: Jasper remains the sole user-facing agent
Users SHALL continue to address and resume Jasper only. Nested Coder execution SHALL remain an implementation of Jasper's delegated coding capability and SHALL NOT require a user-facing Coder selection, endpoint, registration, thread, or client workflow.

#### Scenario: User requests coding work
- **WHEN** a user asks Jasper to perform repository work
- **THEN** Jasper delegates internally and returns the resulting status or answer in the Jasper conversation
- **AND** the user is not required to address Coder separately

#### Scenario: User resumes an interrupted coding operation
- **WHEN** a user supplies a resume decision through the existing Jasper thread
- **THEN** the decision reaches the interrupted nested Coder execution without switching to a separately addressed Coder conversation
