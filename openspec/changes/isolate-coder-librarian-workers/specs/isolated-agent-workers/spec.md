## Purpose

Separate Coder and Librarian capability execution from credential-bearing backend services while preserving useful agent behavior, grouped Docker lifecycle, truthful trust-domain reporting, and clear anti-coercive human understanding.

## ADDED Requirements

### Requirement: Credentialed orchestration and agent capabilities are separate

The system SHALL run the credential-bearing Agent Server control plane, Coder capability worker, and Librarian capability worker as three distinct services and process/container security boundaries. The Agent Server SHALL retain LangGraph orchestration, model invocation, checkpoints, Store access, and human-interrupt authority during this transitional phase, but SHALL NOT retain Coder shell execution, Coder repository filesystem tools, Librarian workspace filesystem tools, or Librarian untrusted-content processing. Worker requests and results SHALL use bounded typed contracts.

#### Scenario: Coder performs repository work

- **WHEN** a Coder run needs to inspect files, modify code, invoke local Git, execute a command, test, or build
- **THEN** that capability executes in the Coder worker and not in the credential-bearing Agent Server process or container

#### Scenario: Librarian processes a source

- **WHEN** Librarian reads an approved workspace source, processes an uploaded source, or analyzes bounded retrieved content
- **THEN** that capability executes in the Librarian worker and not in the credential-bearing Agent Server process or Coder worker

### Requirement: No agent worker receives raw credentials

Coder and Librarian workers SHALL NOT receive API keys, passwords, OAuth tokens, session cookies, SSH keys or agents, signing keys, authorization headers, credential-helper state, provider `.env` files, browser profiles, cloud configuration, Docker control, macOS Keychain access, macOS executor private state, GitHub configuration, or equivalent reusable authority through environment variables, mounts, images, build layers, command arguments, messages, graph state, logs, caches, or worker responses. Sensitive path filters SHALL be defense in depth and SHALL NOT be treated as the isolation boundary.

#### Scenario: Worker inspects its environment and filesystem

- **WHEN** adversarial Coder code or untrusted Librarian content inspects environment variables, process metadata, mounts, image layers, temporary files, caches, and accessible paths
- **THEN** it cannot recover an Agent Server, AI-provider, research-provider, GitHub, SSH, cloud, host-executor, or communication credential

#### Scenario: Worker asks the control plane for a credential

- **WHEN** a worker request, tool output, injected source, or model instruction asks for a raw credential or authorization header
- **THEN** the typed contract rejects or redacts it and no credential enters worker-visible state

### Requirement: Coder remains useful within an isolated execution boundary

Coder SHALL retain selected-repository reads, writes, edits, deletions, local Git operations, dependency commands, formatting, linting, tests, builds, and bounded shell execution according to its existing read-only, approval, or autonomous mode. Commands SHALL execute as a non-root user with an explicit minimal environment, bounded time and output, process-tree cancellation, resource controls, and no inherited service environment. Coder SHALL receive no host, remote-publication, policy-administration, or credential authority from this capability set.

#### Scenario: Authorized autonomous repository task

- **WHEN** the human selects autonomous Coder for a repository-local implementation task
- **THEN** Coder can complete and verify ordinary repository work in its worker without access to Agent Server credentials or macOS host execution

#### Scenario: Task requires external privileged authority

- **WHEN** Coder reaches GitHub publication, authenticated remote Git, macOS execution, Docker control, cloud deployment, or another absent trust domain
- **THEN** it reports the unavailable or separately approved capability and cannot obtain it from its worker

### Requirement: Coder workspace access is task-bound and enforceable

Each Coder worker request SHALL be bound to one canonical selected repository, execution mode, thread, run, task digest, deadline, and allowed operation set. Filesystem and shell confinement SHALL be enforced by the operating-system/container/sandbox boundary rather than prompt instructions or Deep Agents virtual paths alone. The worker SHALL NOT receive a broad home-directory mount, unrelated repository mount, backend source containing deployment secrets, or control-plane writable state. If enforceable task-bound confinement is unavailable, shell execution SHALL fail closed.

#### Scenario: Command attempts to leave the selected repository

- **WHEN** Coder uses an absolute path, parent traversal, symlink, subprocess, interpreter, package hook, or direct system call to reach a sibling repository or control-plane file
- **THEN** the worker boundary denies access and records a bounded policy result

#### Scenario: Confinement cannot be established

- **WHEN** deployment cannot prove that the selected workspace is the only writable task workspace visible to Coder
- **THEN** the Agent Server reports Coder shell unavailable rather than starting a falsely isolated autonomous run

### Requirement: Librarian has an independent least-privilege worker

The existing Research profile, referred to as Librarian in the human-facing trust posture, SHALL use a worker separate from Coder and SHALL preserve its profile identity, provenance, session relationships, evidence IDs, canonical reports, approved uploaded-source processing, saved-evidence reopening, and safe selected-workspace reads. Librarian SHALL have no general shell, local Git, package installation, Coder filesystem, or Coder process access. Workspace writes SHALL remain disabled in this change.

#### Scenario: Librarian reads approved material

- **WHEN** Librarian receives a bounded approved source or selected-workspace read request
- **THEN** its worker processes only that material and returns bounded provenance-preserving output

#### Scenario: Librarian attempts a write or command

- **WHEN** Librarian or untrusted source content requests a workspace mutation, command execution, package installation, or Coder operation
- **THEN** the worker denies it and does not silently delegate to Coder

### Requirement: Future Librarian writes do not require re-collapsing isolation

The Librarian worker contract SHALL permit a future versioned policy to add typed write operations with independently declared roots and authorization, but the deployed capability manifest for this change SHALL report all Librarian write operations unavailable. A future write grant SHALL require a separate reviewed change, trust-domain diff, human-visible risk explanation, and tests; container membership or file-read permission SHALL NOT imply write permission.

#### Scenario: Future feature proposes Librarian artifact creation

- **WHEN** a repository feature proposes allowing Librarian to save research artifacts
- **THEN** the system identifies the new `filesystem-workspace-artifacts:write` capability and does not activate it under the current read-only policy

### Requirement: Credentialed provider calls remain a disclosed transitional control-plane capability

Until credential brokers are implemented, model calls and existing authenticated research-provider calls SHALL remain in the Agent Server control plane. Workers SHALL receive only the bounded requests or provider results needed for their tasks and SHALL never receive provider credentials or reusable authenticated clients. The system SHALL identify this data flow as transitional and SHALL NOT describe it as a credential broker.

#### Scenario: Librarian uses credentialed web search

- **WHEN** Librarian requires an existing authenticated search provider
- **THEN** the control plane performs only the existing typed provider operation and supplies bounded non-secret results to Librarian for processing

#### Scenario: Worker requests a new authenticated provider action

- **WHEN** a worker requires a credentialed operation outside existing typed control-plane adapters
- **THEN** the request stops as unavailable pending a separate broker or capability change

### Requirement: Worker networking is separated and capability-scoped

Coder and Librarian SHALL use distinct internal network boundaries and SHALL NOT address one another. Worker egress SHALL be denied by default and enabled only for explicitly declared destinations and operations. Workers SHALL NOT reach Docker control, host gateways, local/private networks, cloud metadata services, control-plane administrative endpoints, macOS executor control endpoints, GitHub publisher control endpoints, or unrelated backend services. Network access SHALL NOT imply permission to transmit repository, conversation, personal, or work data.

#### Scenario: Coder attempts credential or host-service discovery

- **WHEN** Coder scans Compose services, host gateways, private address ranges, metadata endpoints, or executor ports
- **THEN** network policy denies the connection without exposing service metadata or credentials

#### Scenario: Librarian follows an unapproved destination

- **WHEN** retrieved content redirects or links to a destination outside Librarian's declared retrieval policy
- **THEN** the worker refuses the request or returns it for explicit review without contacting that destination

### Requirement: Backend services have one grouped Docker lifecycle

The Agent Server, Coder worker, and Librarian worker SHALL belong to one stable Docker Compose backend project and SHALL support grouped start, stop, recreate/restart, status, log discovery, and rollback through the operator launcher. Grouping SHALL NOT merge containers, filesystems, environments, networks, identities, or permissions. Configuration or image changes SHALL use recreate semantics rather than being represented as applied by a process-only restart.

#### Scenario: Operator restarts the backend group

- **WHEN** the operator invokes the documented backend restart/recreate action
- **THEN** all three services are reconciled as one project and per-service readiness is reported

#### Scenario: One worker is unhealthy

- **WHEN** Coder or Librarian fails readiness while the Agent Server is live
- **THEN** the group status identifies the exact unavailable capability and the UI does not represent the full backend as healthy

### Requirement: Restarts preserve durable graph truth without replaying mutations

Worker requests SHALL be idempotent and bound to thread, run, task, workspace, operation mode, deadline, and request digest. The Agent Server SHALL remain the authority for checkpoints, Store state, and human decisions. Worker restart, duplicate delivery, timeout, and cancellation SHALL NOT silently repeat a completed or uncertain mutation. Cancellation SHALL target only request-owned processes.

#### Scenario: Coder worker restarts during a write or command

- **WHEN** the worker loses process state before the control plane can verify completion
- **THEN** the task becomes explicitly uncertain or safely recoverable and is not silently rerun

#### Scenario: Librarian worker restarts after saving evidence

- **WHEN** the same evidence-processing result is delivered again
- **THEN** existing evidence identity and deduplication rules prevent false duplicate provenance

### Requirement: Runtime capability manifests are server-produced and verified

The system SHALL produce a typed capability manifest for the Agent Server, Coder, Librarian, macOS executor, and any configured privileged publisher. Each manifest SHALL identify runtime/container, security tenant, trust domains, allowed and denied capabilities, exact resource scope, network destinations, credential exposure, approval requirements, current health, and evidence timestamp. Deployment probes SHALL verify material claims. A model SHALL NOT authoritatively declare its own boundary.

#### Scenario: Manifest says Coder has no credentials

- **WHEN** Coder is offered as available
- **THEN** deployment checks confirm no prohibited environment, mount, image, process, or reachable credential source before the manifest reports `credential_exposure: none`

#### Scenario: Manifest and deployment disagree

- **WHEN** a mount, environment variable, route, image, or process capability exceeds the declared manifest
- **THEN** the affected agent fails closed and the human sees the mismatch without secret values

### Requirement: The trust-domain registry is comprehensive and extensible

The system SHALL maintain versioned stable identifiers for `governance-policy`, `identity-credential-custody`, `agent-orchestration`, `ai-model-compute`, `code-execution`, `filesystem-workspace-artifacts`, `source-control-hosting`, `research-web-network`, `software-supply-chain`, `host-machine`, `cloud-deployment`, `durable-data-memory`, `private-communications`, `productivity-collaboration`, `public-publishing`, `device-sensory-attention`, `physical-connected-devices`, `financial-commercial-legal`, `sensitive-high-impact-records`, `security-observability-audit`, `extension-integration-administration`, `cross-domain-transfer`, and `unclassified-authority`. Personal and work SHALL be separate security tenants. Domain, tenant, capability, resource scope, duration, and authorization SHALL be represented as distinct fields.

#### Scenario: Personal and work provider authority exists

- **WHEN** both personal and work AI or GitHub accounts are configured in a future deployment
- **THEN** they appear as separate tenants and no grant or data flow silently spans both

#### Scenario: A feature introduces unknown authority

- **WHEN** its action cannot be classified under a reviewed domain and capability
- **THEN** it is recorded as `unclassified-authority` and cannot execute until human review and a versioned registry update

### Requirement: The human has simple persistent access to the Trust Map

The interface SHALL provide a persistent, accessible Trust Map showing each agent/service, container/runtime, personal or work tenant, trust domains, allowed and denied capabilities, exact scope, network destinations, credential exposure, approval boundaries, health, and recent redacted receipts. The initial view SHALL use short plain-language summaries with technical details available on request. It SHALL distinguish verified deployment facts from policy intent, model inference, and unavailable information.

#### Scenario: Human inspects Coder

- **WHEN** the human opens Coder's Trust Map entry
- **THEN** it plainly states that Coder can read/write/execute only in its selected repository worker, cannot access raw credentials or the Mac host, and requires a separate boundary for external publication or host actions

#### Scenario: Service is degraded

- **WHEN** a worker, manifest probe, or policy check is unavailable
- **THEN** the map shows the uncertainty and affected capabilities rather than displaying a reassuring healthy state

### Requirement: Requests and proposed features disclose trust-domain impact

Before requesting authorization for a consequential action, and when analyzing a proposed repository feature that changes authority, the system SHALL present a Trust Impact Notice that separates the human's stated request from model inference and identifies affected domains and tenants, data read/written/executed/transmitted/deleted, source and destination for cross-domain transfer, acting worker or broker, any newly granted capability, affected people, material risks, side effects, reversibility, rollback limits, lower-authority alternatives, no-action outcome, approval scope/duration, and expected audit evidence. The notice SHALL be based on typed manifests and policy state rather than model assertion alone.

#### Scenario: Feature would add Librarian writes

- **WHEN** a proposed feature allows Librarian to create files
- **THEN** the notice identifies a new write capability, exact paths, data provenance, conflict and overwrite risks, required approval/policy change, and the option to retain read-only behavior

#### Scenario: Feature crosses personal and work tenants

- **WHEN** a proposed flow sends personal source material through a work provider or repository
- **THEN** the notice identifies both tenants, exact data transfer, destination, retention uncertainty, and a no-transfer alternative before authorization

### Requirement: Trust communication is anti-coercive

Trust Map and Trust Impact Notice presentation SHALL make declining, deferring, and inspecting details no harder than accepting. It SHALL NOT use preselected approval, countdowns, manufactured urgency, emotional loading, repeated persuasion, hidden consequences, bulk approval across domains, or degradation of unrelated service after refusal. Silence, inactivity, attention, previous approval, feature enthusiasm, and model confidence SHALL NOT create authorization. Changed material fields SHALL invalidate prior authorization.

#### Scenario: Human declines a capability change

- **WHEN** the human rejects or defers a proposed trust-domain expansion
- **THEN** no expansion occurs, the prior safe capability remains available where technically possible, and the interface does not pressure reconsideration

#### Scenario: Approved request changes

- **WHEN** its tenant, domain, capability, scope, destination, data, duration, side effects, or rollback limits change
- **THEN** prior approval is invalid and a new neutral review is required

### Requirement: Existing privileged boundaries remain separate

The Coder and Librarian migration SHALL NOT expose macOS executor control, signing material, native confirmation state, GitHub publisher credentials, remote Git authority, SSH authority, Docker control, or privileged host files to either worker. Existing signed host receipts and future publisher receipts MAY return through bounded control-plane verification without transferring privileged authority.

#### Scenario: Coder receives a macOS receipt

- **WHEN** a separately approved host operation completes
- **THEN** Coder may receive the verified redacted receipt but cannot call or control the executor directly

### Requirement: Frontend containerization remains future work

The backend Compose project SHALL use stable service discovery and lifecycle structure that can accept a separately reviewed frontend service later, but this change SHALL NOT add a frontend container, share backend credentials with the frontend, or grant the frontend worker authority.

#### Scenario: Backend group is deployed

- **WHEN** this change is released
- **THEN** the existing frontend may connect through its documented endpoint while remaining outside the backend Compose group

### Requirement: Release evidence proves isolation and retained usefulness

Release SHALL require source tests, built-image inspection, deployed mount/environment/network/process probes, adversarial credential discovery and exfiltration attempts, worker restart/replay tests, and separately approved functional canaries. Coder canaries SHALL cover repository read, write, local Git, command, test, and build behavior. Librarian canaries SHALL cover workspace read, bounded retrieval-result processing, uploaded-source processing, evidence provenance, and write/execute denial. Test fixtures containing fake credential markers SHALL prove non-exposure without printing real secret values.

#### Scenario: Source tests pass but deployment is stale

- **WHEN** code-level tests pass without rebuilt worker images and deployed probes
- **THEN** the system reports source validation only and does not claim deployed isolation

#### Scenario: Isolation passes but useful behavior regresses

- **WHEN** workers cannot complete their required canaries
- **THEN** release remains blocked rather than declaring security success from disabled functionality

### Requirement: Rollback never silently restores credential-plus-shell colocation

Rollback SHALL preserve durable LangGraph and Store data while returning to the most recent known credential-isolated deployment. If no safe isolated deployment is available, Coder and Librarian SHALL remain unavailable with a clear explanation. Automated rollback SHALL NOT restore a container combining reusable credentials with Coder shell or Librarian untrusted-content capabilities.

#### Scenario: New worker deployment fails

- **WHEN** release checks cannot establish isolation or useful behavior
- **THEN** the backend remains stopped or returns to a previously verified isolated version and does not silently start the old monolithic deployment
