## Purpose

Defines a standard, authenticated MCP boundary for broad ordinary host execution from the container while preserving repository semantics, credential isolation, and host-enforced safety controls.

## ADDED Requirements

### Requirement: Native host execution uses authenticated Streamable HTTP MCP
The system SHALL expose one general-purpose native macOS MCP service over Streamable HTTP for active host shell and filesystem execution, and Docker Desktop clients SHALL address that service through `host.docker.internal`. The custom Custodian HTTP protocol SHALL NOT be used by the active execution path.

#### Scenario: Container establishes an MCP session
- **WHEN** the runtime container connects to the configured host execution endpoint with valid transport authentication
- **THEN** it establishes a Streamable HTTP MCP session through `host.docker.internal` and can discover the host execution capabilities

#### Scenario: Legacy protocol is unavailable to the active path
- **WHEN** an agent performs host filesystem or shell work after this phase is enabled
- **THEN** the request traverses MCP and does not invoke the Custodian custom HTTP protocol

### Requirement: MCP v1 dependency compatibility is enforced
The host service and container client SHALL use the official Python MCP SDK maintenance-v1 line pinned to `mcp>=1.28,<2`. The system SHALL retain compatibility with `langchain-mcp-adapters==0.3.2`, whose dependency contract requires `mcp<2`, and SHALL block migration to MCP SDK v2 until the adapter explicitly supports it and compatibility is verified.

#### Scenario: Dependencies are resolved
- **WHEN** host and container dependencies are installed from the project declarations
- **THEN** the resolved MCP SDK version is at least 1.28 and below 2

#### Scenario: Premature v2 upgrade is attempted
- **WHEN** a dependency change attempts to resolve MCP SDK version 2 or later while the adapter remains incompatible
- **THEN** dependency resolution or compatibility validation fails before deployment

### Requirement: Deep Agents backend behavior is preserved
The system SHALL provide an MCP-backed implementation of Deep Agents `SandboxBackendProtocol` using the official MCP client. The backend SHALL preserve Deep Agents' built-in filesystem operations and `execute` interface, including their expected result and error semantics. A LangChain `MultiServerMCPClient` SHALL NOT be presented as or substituted for this backend.

#### Scenario: Deep Agents performs filesystem work
- **WHEN** Deep Agents invokes a built-in filesystem operation through its backend interface
- **THEN** the backend translates the operation to the host MCP service and returns the interface-compatible result

#### Scenario: Deep Agents executes an ordinary command
- **WHEN** Deep Agents calls `execute` with an allowed ordinary shell command
- **THEN** the MCP-backed backend runs it at the checked repository context and returns a bounded interface-compatible execution result

#### Scenario: Additional MCP servers are configured
- **WHEN** the runtime uses `MultiServerMCPClient` for an additional typed broker-held MCP boundary
- **THEN** that client remains separate from the `SandboxBackendProtocol` implementation

### Requirement: Ordinary host work is broad rather than task-allowlisted
After a human explicitly supplies a task, the host service SHALL permit autonomous use of broad ordinary shell and filesystem capabilities needed to complete that task without requiring a narrow per-task command allowlist or confirmation for each ordinary operation. MCP SHALL be treated only as transport; all authorization and safety policy SHALL remain enforced by the host boundary.

#### Scenario: Explicit task authorizes autonomous ordinary work
- **WHEN** a human submits an explicit coding task associated with a checked repository root
- **THEN** the agent can autonomously perform the ordinary shell and filesystem sequence needed for that task within the host policy

#### Scenario: No explicit task exists
- **WHEN** no human task has initiated execution authority
- **THEN** the system does not start autonomous host mutations

#### Scenario: Unlisted ordinary tool is needed
- **WHEN** an ordinary non-privileged command is needed and it is not on a per-task command list
- **THEN** the service evaluates it under general host policy rather than denying it solely because it was not pre-enumerated

### Requirement: Credentials remain broker-held and unavailable to agents
The host boundary SHALL refuse requests to retrieve, enumerate, expose, or manipulate credentials, secrets, tokens, private keys, authentication stores, or macOS Keychain material. Transport credentials SHALL be supplied outside model-visible tool arguments and results. Compose preparation and GitHub publication SHALL remain separate typed broker-held boundaries, and agents SHALL NOT receive the credentials used by those boundaries.

#### Scenario: Agent requests Keychain access
- **WHEN** an agent requests a command or file operation that accesses macOS Keychain or another credential store
- **THEN** the host boundary denies the request without returning secret material

#### Scenario: Agent requests a sensitive credential file
- **WHEN** an agent attempts to read a recognized secret, token, private-key, or credential file
- **THEN** the host boundary denies access and returns only a sanitized refusal

#### Scenario: Authenticated MCP request is constructed
- **WHEN** the container authenticates to the host MCP service
- **THEN** the bearer token or equivalent transport secret is injected by trusted configuration outside model-authored MCP tool arguments and is not included in model-visible output

#### Scenario: Publication is requested
- **WHEN** an approved workflow prepares Compose material or publishes to GitHub
- **THEN** a typed broker-held boundary performs the credentialed action without disclosing credentials to the agent

### Requirement: Selected-repository defaults and explicitly authorized host paths are checked exactly
Repository work SHALL start in the exact selected repository root associated with the repository binding and SHALL NOT search for or substitute another checkout. When the explicit human task requires ordinary work elsewhere on the host, trusted task context MAY authorize the required absolute host paths without per-command approval. Model-authored paths or claims SHALL NOT create or expand that authority. The service SHALL canonicalize existing paths, safely resolve prospective mutation targets, reject unauthorized traversal and unsafe symlink behavior, and fail closed when task or repository context is absent, invalid, ambiguous, or changed. Sensitive-path, credential, protected-Git, destructive-operation, and privilege protections SHALL apply equally inside and outside the selected repository.

#### Scenario: Operation uses the selected repository default
- **WHEN** an operation targets a canonical path within the exact selected repository root
- **THEN** the service evaluates and performs it under the remaining host policies without substituting another repository

#### Scenario: Explicit task requires work elsewhere on the host
- **WHEN** trusted context shows that the human's explicit task requires an ordinary absolute host path outside the selected repository
- **THEN** the service evaluates that operation under the same path, credential, Git, destructive-operation, privilege, timeout, and redaction protections without requiring a new per-command gate

#### Scenario: Model attempts to expand host scope
- **WHEN** a model supplies an external path or approval claim not supported by trusted human-task context
- **THEN** the service denies the operation before reading, execution, or mutation

#### Scenario: Repository context is absent or stale
- **WHEN** repository-default work lacks a valid repository root or the checked root no longer matches the requested context
- **THEN** the service fails closed without searching for or substituting a broader or different repository

#### Scenario: Protected Git mutation is attempted
- **WHEN** an operation targets protected Git metadata or performs a denied history, credential-bearing remote, hook, configuration, force, or protection-bypassing mutation
- **THEN** the host boundary denies it before side effects occur

### Requirement: Host safety controls apply to every operation
The host service SHALL deny sensitive-file access, destructive host-wide actions, privilege escalation, and privileged operations. It SHALL validate commands, paths, environment, and mutations before execution; enforce operation timeouts; terminate timed-out process trees; bound stdout, stderr, listings, and file content; and redact recognized secrets from all returned data and errors.

#### Scenario: Destructive or privileged request is attempted
- **WHEN** an operation requests privilege escalation, protected system modification, or destructive host-wide behavior
- **THEN** the host boundary denies it before execution

#### Scenario: Execution exceeds its deadline
- **WHEN** a command runs beyond the configured timeout
- **THEN** the service terminates the process tree and returns a bounded timeout result

#### Scenario: Output is large or contains a recognizable secret
- **WHEN** command output, file content, a directory listing, or an error exceeds limits or contains recognizable secret material
- **THEN** the service truncates or bounds the response, redacts the sensitive material, and marks truncation without exposing the omitted content

#### Scenario: Mutation target changes during validation
- **WHEN** a checked mutation target cannot be proven to remain within policy at the point of mutation
- **THEN** the service fails closed and does not partially apply the mutation

### Requirement: Transport access is authenticated and network-restricted
Every MCP protocol request SHALL require a valid token or equivalent configured transport credential and SHALL validate the HTTP `Host` and `Origin` headers against explicit trusted values. Invalid, missing, malformed, or unexpected values SHALL be rejected before MCP method dispatch. The service SHALL bind only to the host interface required for Docker Desktop access and SHALL be protected by host firewall rules that restrict access to the intended local Docker-to-host path.

#### Scenario: Authentication is missing or invalid
- **WHEN** a client sends an MCP request without the configured transport credential or with an invalid credential
- **THEN** the service rejects it before method dispatch and emits no model-sensitive details

#### Scenario: Host or Origin is untrusted
- **WHEN** a request carries an absent, malformed, or unapproved `Host` or `Origin` value under the configured policy
- **THEN** the service rejects it before MCP method dispatch

#### Scenario: Unintended network peer connects
- **WHEN** a peer outside the permitted Docker-to-host route attempts to reach the service
- **THEN** binding and firewall policy prevent access or the service rejects the request

### Requirement: Operations expose health and idempotency behavior
The deployment SHALL expose a bounded health check that confirms service readiness without revealing credentials or host data. Mutating MCP operations SHALL accept or derive an idempotency identity, SHALL prevent duplicate side effects for retried identical requests, and SHALL reject reuse of an identity with conflicting inputs.

#### Scenario: Health is checked
- **WHEN** the trusted launcher or container probes service readiness
- **THEN** it receives a bounded healthy or unhealthy result without credentials, filesystem content, or execution capability details

#### Scenario: Identical mutation is retried
- **WHEN** an authenticated client retries the same mutation with the same idempotency identity and inputs
- **THEN** the service returns the recorded outcome without repeating the side effect

#### Scenario: Idempotency identity is reused with different input
- **WHEN** an authenticated client reuses a mutation identity for different operation inputs
- **THEN** the service rejects the conflict without applying the new mutation

### Requirement: Container-to-host deployment is verifiable
The deployed system SHALL include automated verification from the runtime container that checks name resolution and routing through `host.docker.internal`, authenticated Streamable HTTP MCP initialization, capability discovery, health, an allowed read, an idempotent allowed mutation in a disposable repository fixture, and representative policy denials. Verification SHALL fail if the active path falls back to Custodian.

#### Scenario: End-to-end verification succeeds
- **WHEN** the native service, firewall policy, and runtime container are configured correctly
- **THEN** the verification proves authenticated container-to-host MCP operation and expected allow and deny behavior

#### Scenario: Host route or policy is misconfigured
- **WHEN** routing, authentication, header validation, binding, firewall policy, repository checks, or host policy is incorrect
- **THEN** verification fails with bounded diagnostics and no credential disclosure

### Requirement: Custodian remains present for Phase 9 cleanup
This phase SHALL disable Custodian as the active execution transport but SHALL NOT physically delete Custodian implementation, launch, test, or documentation artifacts. Physical cleanup SHALL be deferred to Phase 9.

#### Scenario: Phase 7 scope is reviewed
- **WHEN** the Phase 7 implementation diff is inspected
- **THEN** active callers use MCP while Custodian artifacts remain available for Phase 9 removal or rollback
