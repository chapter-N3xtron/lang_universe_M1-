## Purpose

Defines internal durable execution of the authoritative Coder graph through Temporal's official LangGraph plugin while keeping Jasper as the only product-facing Agent Server graph.

## ADDED Requirements

### Requirement: Authoritative Coder graph reuse

The system SHALL provide one authoritative Coder `StateGraph` builder for both the existing supervisor-compiled path and the Temporal plugin registration. The supervisor SHALL retain its existing ability to route to and run Coder as a subagent. The system SHALL NOT copy, wrap, or fork the Coder implementation for Temporal.

#### Scenario: Supervisor runs Coder

- **WHEN** the supervisor routes a request to its existing Coder subagent
- **THEN** it runs the compiled form of the same authoritative builder used by Temporal

#### Scenario: Temporal registers Coder

- **WHEN** the Temporal worker starts
- **THEN** `LangGraphPlugin` registers the authoritative builder under the stable internal graph name `coder`

### Requirement: Official Temporal LangGraph plugin execution

Internal durable Coder execution SHALL use Temporal's official `LangGraphPlugin`. The Coder node SHALL run as a Temporal Activity, and the Workflow SHALL retrieve and compile the registered graph through the plugin's documented API. The implementation SHALL NOT depend on private plugin internals.

#### Scenario: Temporal runs Coder

- **WHEN** an internal caller starts a Coder operation
- **THEN** a Temporal Workflow invokes the registered `coder` graph and its Coder node executes as a Temporal Activity

#### Scenario: Plugin is incompatible

- **WHEN** the supported public plugin cannot register the authoritative graph or round-trip its real input and output
- **THEN** implementation stops and records the incompatibility instead of introducing custom plugin infrastructure

### Requirement: Temporal owns durable execution

Temporal SHALL own Workflow identity, scheduling, Activity timeout and retry policy, cancellation, replay, and completed task results for Temporal-triggered Coder operations. Agent Server SHALL NOT own or mediate those operations.

#### Scenario: Workflow replays

- **WHEN** Temporal replays a Coder Workflow after a worker restart
- **THEN** completed plugin task results remain durable and are not treated as new Agent Server runs

#### Scenario: Coder Activity fails transiently

- **WHEN** a retryable Coder Activity attempt fails
- **THEN** Temporal applies the configured Activity retry policy without claiming exactly-once side-effect execution

### Requirement: Stable operation identity

Every Temporal-triggered Coder operation SHALL have an immutable `operation_id`. The Temporal Workflow ID and Coder `thread_identity` SHALL both use that stable value across Workflow replay and Activity retry. Activity attempt numbers and Temporal Run IDs SHALL NOT replace the logical operation identity.

#### Scenario: Activity retries

- **WHEN** Temporal retries the Coder Activity
- **THEN** the retried Activity receives the same `operation_id` and `thread_identity`

#### Scenario: Operation identity conflicts

- **WHEN** a caller reuses an existing Workflow ID for conflicting immutable input
- **THEN** the request is rejected or addresses the existing operation according to an explicit Temporal Workflow ID policy rather than silently starting unrelated work

### Requirement: Honest at-least-once side-effect handling

The Coder Activity SHALL be treated as at-least-once execution. Automatic retries beyond one attempt SHALL NOT be enabled until focused tests show that re-entry after repository mutation safely resumes from current state and does not duplicate unsafe external effects.

#### Scenario: Attempt fails after repository mutation

- **WHEN** a Coder Activity attempt mutates the repository and then fails before returning
- **THEN** the configured retry behavior preserves the existing mutation, does not claim rollback or exactly-once execution, and follows the verified safe re-entry policy

#### Scenario: External publication is requested

- **WHEN** Coder requests GitHub publication
- **THEN** the existing typed broker-held publication boundary remains authoritative and this change does not make publication automatically retryable

### Requirement: Temporal cancellation propagation

A cancellation decision for a Coder Workflow SHALL propagate through the plugin to the running Coder Activity. The dedicated Temporal worker SHALL use the public Activity interceptor API and an explicit heartbeat timeout to heartbeat only the generated `coder.coding_agent` Activity, without changing or wrapping the authoritative Coder graph configuration. The reported result SHALL reflect the actual Temporal terminal state.

#### Scenario: Running Coder operation is cancelled

- **WHEN** the owning Temporal Workflow is cancelled
- **THEN** cancellation is delivered to the running Coder Activity through the plugin and no Agent Server cancellation is attempted

#### Scenario: Coder already completed

- **WHEN** cancellation arrives after Coder has completed
- **THEN** the existing completed result is preserved rather than rewritten as a new Agent Server state

### Requirement: Jasper-only Agent Server exposure

Jasper SHALL remain the only product-facing Agent Server graph. Temporal plugin registration SHALL NOT add Coder to Agent Server discovery or normal-user selection.

#### Scenario: Normal user views available agents

- **WHEN** a browser or normal-user identity views available product agents
- **THEN** Jasper remains available and no standalone Coder graph is presented

#### Scenario: Internal Temporal worker registers Coder

- **WHEN** the Temporal worker registers the `coder` graph with its plugin
- **THEN** that registration remains internal to the Temporal worker and does not alter Agent Server's graph manifest

### Requirement: Public-preview boundary is explicit

The system SHALL identify the official Temporal LangGraph plugin as public preview, pin and test a compatible version, and SHALL NOT adopt the separate prerelease Deep Agents plugin in this change.

#### Scenario: Dependencies are reviewed

- **WHEN** runtime dependencies are validated
- **THEN** the official LangGraph plugin is present with its preview status recorded and the prerelease Deep Agents plugin is absent
