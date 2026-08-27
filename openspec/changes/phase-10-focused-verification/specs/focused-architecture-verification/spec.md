## Purpose

Defines narrow, deterministic verification and evidence classification for the architecture and trust boundaries introduced across phases 1–9.

## ADDED Requirements

### Requirement: Verification evidence is classified by execution layer
The verification workflow SHALL classify every result as exactly one of unit/mocked, graph/integration, container, or deployed evidence. Each result MUST identify the claim, command or probe, execution target, fixture identity, outcome, and evidence location. Unit/mocked or source-only results MUST NOT be represented as container or deployed validation, and container results MUST NOT be represented as deployed validation.

#### Scenario: Source test result is recorded
- **WHEN** a check runs against imported source with mocks or in-process substitutes
- **THEN** its evidence is classified as unit/mocked and makes no container or deployed claim

#### Scenario: Real graph is exercised in-process
- **WHEN** a compiled graph runs with real graph routing and controlled local dependencies
- **THEN** its evidence is classified as graph/integration and identifies any dependency that remains substituted

#### Scenario: Runtime services are exercised in containers
- **WHEN** a probe runs through the containerized service boundary and its configured infrastructure
- **THEN** its evidence is classified as container and records the service and container configuration identity

#### Scenario: A deployed endpoint is probed
- **WHEN** a check runs against an explicitly identified deployed environment
- **THEN** its evidence is classified as deployed, while final deployed acceptance remains outside this capability

### Requirement: Authoritative graph identity is verified
The focused suite SHALL prove that the configured assistant identity resolves to the intended authoritative graph and that supported invocation paths do not silently select a legacy or duplicate graph implementation. The check MUST fail deterministically for an unknown or obsolete graph identity.

#### Scenario: Configured assistant resolves to the authoritative graph
- **WHEN** the graph/integration check invokes the configured assistant identity
- **THEN** the observed graph identity and entry behavior match the single expected authoritative graph

#### Scenario: Obsolete graph identity is requested
- **WHEN** the check requests a removed or unknown graph identity
- **THEN** invocation fails explicitly rather than falling back to another graph

### Requirement: Registration and authentication are verified as separate controls
Verification SHALL independently prove graph registration and request authentication. Registering a graph MUST NOT establish caller identity or authorization, and valid authentication MUST NOT make an unregistered graph invocable.

#### Scenario: Registered graph receives an unauthenticated request
- **WHEN** a request targets a registered graph without valid authentication
- **THEN** the request is rejected by the authentication boundary

#### Scenario: Authenticated request targets an unregistered graph
- **WHEN** a valid caller targets an unregistered graph identity
- **THEN** the request is rejected as unregistered without weakening authentication

#### Scenario: Registered and authenticated invocation succeeds
- **WHEN** the authoritative graph is registered and the caller presents valid authentication and authorization
- **THEN** invocation reaches that graph under the authenticated caller identity

### Requirement: Genuine subgraph inheritance and interrupts are graph-tested
Graph/integration verification SHALL invoke Coder through Jasper as a compiled child subgraph rather than by directly calling or mocking the child. It SHALL prove that the child receives inherited parent runtime context and persistence scope, that an interrupt is surfaced through the parent, and that resuming the same thread continues the interrupted child without starting an unrelated run.

#### Scenario: Jasper invokes the genuine Coder subgraph
- **WHEN** a deterministic Jasper route delegates a fixture task to Coder
- **THEN** graph trace evidence shows parent-to-child subgraph execution with inherited thread and tenant context

#### Scenario: Child interrupt is resumed through the parent
- **WHEN** the Coder subgraph interrupts at a deterministic fixture boundary and the same thread is resumed with an answer
- **THEN** execution continues from the interrupted child state exactly once and returns through Jasper

#### Scenario: Resume uses the wrong thread
- **WHEN** a resume payload is sent under a different thread or tenant identity
- **THEN** it cannot continue the original interrupted child execution

### Requirement: Agent Server PostgreSQL authority is container-verified
Container verification SHALL prove that Agent Server and its configured PostgreSQL persistence are authoritative for thread, checkpoint, run, and interrupt state covered by phases 1–9. Evidence MUST cross a service restart boundary and MUST fail if the authoritative PostgreSQL dependency is unavailable rather than silently succeeding through a legacy application-owned persistence path.

#### Scenario: State survives an Agent Server restart
- **WHEN** a deterministic run reaches a persisted checkpoint or interrupt, Agent Server is restarted, and the same authorized thread is resumed
- **THEN** the run continues from PostgreSQL-backed state without recreating the thread through a parallel store

#### Scenario: PostgreSQL authority is unavailable
- **WHEN** the configured PostgreSQL persistence is unavailable during an operation that requires durable state
- **THEN** the operation reports a persistence failure and does not fall back to obsolete application-owned thread or checkpoint storage

### Requirement: Memory and RAG tenant boundaries are verified positively and negatively
Verification SHALL use at least two deterministic tenant identities with colliding document names, memory keys, and query text. A tenant SHALL retrieve its own authorized memory and RAG content, and MUST NOT observe, cite, mutate, or delete another tenant's content through direct lookup, semantic retrieval, thread reuse, or crafted filter input.

#### Scenario: Tenant retrieves its own colliding fixture
- **WHEN** tenant A stores memory and documentation fixtures using keys and text also used by tenant B
- **THEN** tenant A receives only tenant A's authorized content and provenance

#### Scenario: Cross-tenant retrieval is attempted
- **WHEN** tenant A queries by tenant B's known identifier, colliding semantic text, reused thread identifier, or crafted filter
- **THEN** no tenant B content, metadata, count, or citation is disclosed

#### Scenario: Cross-tenant mutation is attempted
- **WHEN** tenant A attempts to update or delete tenant B's known memory or document identifier
- **THEN** tenant B's content remains unchanged and the operation is rejected or returns no authorized match

### Requirement: Typed Coder reports and Jasper summaries are verified
Verification SHALL validate successful, blocked, failed, and authorization-required Coder outputs against the typed report contract. Jasper SHALL consume the typed report and produce a contextual summary that preserves material status, changed files, validation outcomes, blockers, and authorization needs without exposing a raw report dump or falsely describing incomplete work as complete.

#### Scenario: Completed typed report is summarized
- **WHEN** Coder returns a valid completed fixture report
- **THEN** Jasper's summary connects the result to the active request and includes material changes and validation status without reproducing the raw report

#### Scenario: Non-success report is summarized
- **WHEN** Coder returns a valid blocked, failed, or authorization-required fixture report
- **THEN** Jasper preserves that status and its impact without claiming completion

#### Scenario: Malformed report is received
- **WHEN** Coder output omits required typed fields or uses an invalid state transition
- **THEN** validation fails explicitly and Jasper does not present the output as a valid completed report

### Requirement: MCP backend parity and security are verified
For every supported MCP backend, the focused suite SHALL run the same deterministic capability contract and compare normalized results. It MUST verify equivalent tool discovery, allowed invocation, errors, cancellation or timeout behavior where supported, and security enforcement for authentication, tenant scope, tool allowlists, argument validation, and secret redaction.

#### Scenario: Supported backends execute the parity fixture
- **WHEN** the same allowlisted deterministic MCP tool fixture runs through each supported backend
- **THEN** normalized tool metadata, result, and error semantics satisfy the same contract

#### Scenario: Unauthorized or disallowed invocation is attempted
- **WHEN** a caller lacks valid authentication, tenant scope, or tool permission
- **THEN** every backend rejects the invocation before tool side effects occur

#### Scenario: Malicious arguments or secret-bearing error occurs
- **WHEN** a request supplies invalid traversal-style arguments or a backend fixture raises an error containing a sentinel secret
- **THEN** every backend rejects or safely handles the request and no result, log evidence, or client error exposes the sentinel secret

### Requirement: Stream disconnect and rejoin are verified at the run boundary
Graph/integration and container checks SHALL deterministically disconnect a stream after a known event while allowing the run to continue, then rejoin by stable run and thread identity. Rejoined delivery SHALL preserve event ordering, avoid duplicate committed events, include the terminal outcome, and enforce the original caller and tenant boundary.

#### Scenario: Client rejoins a continuing run
- **WHEN** a client disconnects after a recorded event cursor and rejoins the same authorized run
- **THEN** the client receives the remaining ordered events and one terminal outcome without restarting the run

#### Scenario: Rejoin repeats the last acknowledged cursor
- **WHEN** the client rejoins using the last acknowledged event position
- **THEN** deduplication semantics prevent duplicate committed content in the reconstructed result

#### Scenario: Another tenant attempts to rejoin
- **WHEN** a different tenant supplies the known run and thread identifiers
- **THEN** no stream event or run existence detail is disclosed

### Requirement: Obsolete references are proven absent
The focused suite SHALL maintain an explicit list of forbidden obsolete graph identities, routes, persistence owners, adapters, configuration keys, imports, and runtime references removed by phase 9. Deterministic repository and effective-configuration checks MUST report zero executable references, except for narrowly documented historical or migration allowlist entries that cannot be loaded as runtime configuration.

#### Scenario: Forbidden runtime reference is absent
- **WHEN** the zero-match checks scan the defined source, configuration, container, and entrypoint surfaces
- **THEN** every forbidden executable reference has zero non-allowlisted matches

#### Scenario: Obsolete reference is reintroduced
- **WHEN** a forbidden fixture reference appears in an executable or effective-configuration surface
- **THEN** the check fails with the exact reference and location

### Requirement: Verification remains focused and deterministic
The verification plan SHALL map each phase 1–9 claim to the narrowest sufficient positive and negative checks, fixed fixture identities, controlled timing, and bounded retries. It MUST NOT require real-browser speech-to-text or text-to-speech verification, broad unrelated backend or frontend suites, live model nondeterminism, or deployed final acceptance.

#### Scenario: Focused suite is selected
- **WHEN** phase-10 verification is run
- **THEN** only the mapped architecture checks and their declared prerequisites execute

#### Scenario: Browser audio or unrelated suite is proposed as required evidence
- **WHEN** a check requires real-browser speech input, speech output, or an unrelated broad suite
- **THEN** it is excluded from phase 10 and does not block this capability's result

### Requirement: Planning and changed-file quality gates are explicit
The change artifacts SHALL pass strict OpenSpec validation. During later implementation, lint and type checks SHALL run for changed implementation and verification files where an applicable checker exists, and evidence SHALL distinguish a skipped inapplicable checker from a passing result. These quality gates MUST NOT be described as deployed validation.

#### Scenario: OpenSpec artifacts are validated
- **WHEN** the phase-10 change is reviewed as ready
- **THEN** strict OpenSpec validation succeeds for `phase-10-focused-verification`

#### Scenario: Verification implementation changes typed or linted files
- **WHEN** later phase-10 implementation modifies files covered by configured lint or type tooling
- **THEN** the applicable checks run against those changed files or the narrowest supported containing target and their evidence is recorded at the correct layer
