## Purpose

Defines a single reusable complete Coder graph contract whose schemas and compatibility guarantees can be consumed consistently by later standalone and parent-graph integrations.

## ADDED Requirements

### Requirement: Authoritative complete graph construction
The system SHALL expose one authoritative reusable construction boundary for the complete Coder graph, and every in-scope production path that needs a complete Coder graph SHALL obtain it from that boundary rather than reconstructing Coder topology from lower-level nodes.

#### Scenario: Production consumer obtains Coder graph
- **WHEN** an in-scope production consumer needs a complete Coder graph
- **THEN** it receives the graph produced by the authoritative construction boundary
- **AND** it does not independently assemble a parallel Coder graph

#### Scenario: Complete graph executes a coding request
- **WHEN** the authoritative graph receives a valid Coder request
- **THEN** it runs the existing Coder workflow from graph entry through its terminal output
- **AND** it returns the Coder result through the shared output contract

### Requirement: Shared graph schemas
The system SHALL define and reuse explicit shared schemas for Coder graph input, output, and complete internal state. The input contract SHALL carry messages, selected workspace, model selection, execution mode, thread identity, user identity, and coding-session identity as applicable. The output contract SHALL carry result messages, canonical workspace and execution manifest when available, coding-session identity, and coding status. The complete state SHALL support those input and output fields plus Coder user-interface events without requiring parent-graph-only fields.

#### Scenario: Standalone-compatible input
- **WHEN** a caller supplies a request conforming to the shared Coder input schema
- **THEN** the authoritative graph accepts the request without requiring Jasper-specific or Agent-Server-registration-specific state

#### Scenario: Parent graph exchanges state
- **WHEN** a parent graph maps compatible values into and out of the Coder graph
- **THEN** the shared input and output schemas provide the complete declared exchange boundary
- **AND** the parent does not need a private alternative Coder state definition

#### Scenario: Error output follows shared contract
- **WHEN** Coder rejects an invalid workspace or encounters an internal agent failure
- **THEN** its result conforms to the shared output schema
- **AND** it reports an error coding status without exposing sensitive provider details

### Requirement: Persistence-neutral compilation
The authoritative complete Coder graph SHALL compile without binding a concrete checkpointer or store. Its construction SHALL remain compatible with later runtime injection of persistence and with persistence inherited when the graph is embedded by a parent.

#### Scenario: Compile without persistence implementations
- **WHEN** the authoritative builder is called without a checkpointer and without a store
- **THEN** it returns a compiled, invocable complete Coder graph
- **AND** no concrete persistence implementation is captured by the builder

#### Scenario: Later composition remains possible
- **WHEN** a later standalone runtime or parent graph supplies persistence at its composition boundary
- **THEN** the Coder graph contract does not prevent runtime injection or parent inheritance

### Requirement: Tool and Custodian boundary compatibility
The authoritative graph SHALL preserve the current Coder tool inventory and native Custodian boundary. Built-in repository file operations, task-list support, and ordinary command execution SHALL retain their current availability by execution mode; broker-only Docker Compose and GitHub publication operations SHALL remain the four typed tools `custodian_compose_prepare_environment`, `custodian_compose_read`, `custodian_compose_change`, and `custodian_github_publish` in mutable modes. Native Custodian SHALL remain the sole filesystem and command boundary, and remote Git operations outside the approved publication tool SHALL remain unavailable.

#### Scenario: Read-only tool surface
- **WHEN** Coder runs in `read_only` mode
- **THEN** its Custodian backend is read-only
- **AND** no mutable typed Custodian boundary tools are added
- **AND** writing, editing, deleting, and command execution remain prohibited

#### Scenario: Mutable tool surface
- **WHEN** Coder runs in `approval` or `autonomous` mode
- **THEN** its Custodian backend permits the existing mutable operations
- **AND** the four current typed Custodian boundary tools are available with their existing responsibilities
- **AND** ordinary shell, Git, build, test, package, and host commands continue through the built-in execution tool and native Custodian

### Requirement: Execution mode and autonomy compatibility
The authoritative graph SHALL preserve the current `read_only`, `approval`, and `autonomous` semantics, including normalization of unsupported or absent direct Coder modes to `read_only`. Approval mode SHALL retain review interrupts for file writes, file edits, deletion, execution, Compose reads, and GitHub publication. Autonomous mode SHALL continue independently through authorized repository and host work without per-operation interruption except for GitHub publication, while honoring repository instructions, validation duties, destructive-command protections, and explicit-request requirements for commits and external publication.

#### Scenario: Approval mode interruption policy
- **WHEN** Coder runs in `approval` mode
- **THEN** writes, edits, deletions, execution calls, Compose reads, and GitHub publication retain their current human-review interrupts
- **AND** Compose environment preparation and requested Compose deployment changes retain their current non-interrupted behavior

#### Scenario: Autonomous mode interruption policy
- **WHEN** Coder runs in `autonomous` mode on explicitly authorized work
- **THEN** it continues the requested work without per-operation review
- **AND** GitHub publication still requires its current explicit request and approval boundary

#### Scenario: Unknown direct mode is safe
- **WHEN** the direct Coder graph receives an absent or unsupported execution mode
- **THEN** it applies `read_only` behavior

### Requirement: Credential refusal and non-disclosure compatibility
The authoritative graph SHALL preserve Coder's current refusal to read, modify, request, receive, or expose credentials and secrets. Broker-held Compose and GitHub values SHALL remain inside Custodian, generated Compose values SHALL not be returned to Coder, and Coder SHALL direct missing local Compose values through the preparation boundary rather than asking the human to reveal them.

#### Scenario: Compose needs a local value
- **WHEN** an authorized Compose operation reports a missing required local value
- **THEN** Coder uses the Custodian Compose environment preparation capability
- **AND** it does not ask the human to create or reveal the value
- **AND** no generated credential value is returned to Coder

#### Scenario: Publication requires credentials
- **WHEN** an explicitly requested private GitHub publication is performed
- **THEN** GitHub credentials remain held by Custodian
- **AND** Coder receives only the non-secret publication result

#### Scenario: Request attempts to access a secret
- **WHEN** work would require Coder itself to read, modify, or disclose a credential or secret
- **THEN** Coder refuses that credential access
- **AND** the authoritative graph does not weaken the existing Custodian protection

### Requirement: Report and result compatibility
The authoritative graph SHALL preserve current reporting behavior: task-list-derived progress reports at the existing 15-minute interval, replacement of the same live report while work continues, removal of that report after normal completion, a plain-English completion report, incomplete-task blocker status, deterministic execution-manifest reporting, a missing-final-result error, and sanitized failure reports.

#### Scenario: Long-running task reports progress
- **WHEN** a Coder run remains active across a 15-minute reporting boundary
- **THEN** it publishes or updates the live Coder progress report from the current task list
- **AND** subsequent intervals update that report rather than accumulating independent live reports

#### Scenario: Normal completion clears progress and reports result
- **WHEN** a Coder run completes normally with a final assistant message
- **THEN** any live progress report is removed
- **AND** the final response is a completion report with the execution manifest
- **AND** coding status is `blocked` when declared tasks remain incomplete and `completed` otherwise

#### Scenario: Missing or failed final result
- **WHEN** a run ends without a final assistant result or fails internally
- **THEN** Coder returns the corresponding sanitized failure report and `error` status
- **AND** provider-sensitive exception details are not disclosed
