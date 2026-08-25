## Purpose

Defines a future human-controlled integration boundary where self-hosted Plane remains authoritative for project-management records, self-hosted Temporal durably orchestrates explicitly bounded integration workflows, and Jasper/TanStack expose safe, attributable projections and links.

## ADDED Requirements

### Requirement: First local deployment foundation
The first implementation phase SHALL deploy Plane and Temporal as separate Docker services with their documented dependencies, named persistent volumes, trusted internal-only networks, deployment-specific environment secrets, pinned image references, and independent process-health and dependency-readiness checks. It MUST keep the LangGraph Agent Server disconnected and MUST NOT enable PM mutations, integration workers, dashboard projections, or production migration.

#### Scenario: Local foundation is started
- **WHEN** an operator starts the approved local Compose file with deployment-specific secrets
- **THEN** the Plane and Temporal service domains start in dependency order, internal dependencies have no public bindings, and only reviewed localhost UI or diagnostic bindings are available

#### Scenario: Foundation is accepted
- **WHEN** verification runs after startup
- **THEN** every selected image has tag and immutable digest evidence, dependency readiness is checked independently from application health, named volumes are present, and the evidence records that Agent Server integration is disconnected

### Requirement: Plane authority and human editing boundary
The future system SHALL treat self-hosted Plane as the source of truth for PM records and SHALL keep Plane's native browser UI available for complete human editing. Jasper, TanStack, LangGraph checkpoints, and Temporal workflow state MUST NOT silently become a competing PM database.

#### Scenario: Human opens the native PM UI
- **WHEN** a person follows a Plane link from Jasper or a TanStack projection
- **THEN** the native Plane browser UI opens with the authoritative record available for full human editing

#### Scenario: Projection or workflow is rebuilt
- **WHEN** a TanStack/Jasper projection or Temporal workflow is refreshed, retried, or rebuilt
- **THEN** it uses stable Plane references and bounded execution context, and does not replace or duplicate the authoritative Plane record

### Requirement: Temporal workflow boundary
Future integration operations SHALL use self-hosted Temporal only as a durable workflow and activity orchestration boundary. Temporal SHALL retain only the inputs, outputs, retry history, and bounded Plane identifiers needed for the workflow, and SHALL NOT be treated as authoritative for PM fields.

#### Scenario: Integration work is submitted
- **WHEN** the LangGraph Agent Server requests an approved Plane integration operation
- **THEN** the integration boundary starts an explicitly named, idempotent Temporal workflow with bounded payloads, a correlation identifier, and the Plane revision basis

#### Scenario: Workflow fails or is retried
- **WHEN** a Temporal activity fails or is retried
- **THEN** the system reports bounded status and preserves audit evidence without silently applying a stale or duplicate Plane mutation

### Requirement: Attributed and conflict-aware Jasper changes
The integration SHALL identify Jasper with a distinct least-privileged integration identity and SHALL make Jasper edits attributable, auditable, previewable, approval-gated where appropriate, and conflict-aware.

#### Scenario: Jasper proposes an edit
- **WHEN** Jasper prepares a Plane edit
- **THEN** the system presents the target, proposed change, integration identity, workflow correlation, and relevant revision/conflict information before applying it

#### Scenario: Concurrent human edit exists
- **WHEN** the Plane record changed after Jasper read it
- **THEN** the system detects the conflict and does not silently overwrite the human's newer change

#### Scenario: Approval is required
- **WHEN** an edit falls within a configured approval-gated class
- **THEN** the edit remains unapplied until the applicable human approval is granted

### Requirement: Lightweight projections and conversational navigation
TanStack/Jasper SHALL provide projections for lists, filters, lightweight tickets, links, timelines, node visualizations, and conversational explanation/prioritization, while preserving links to Plane records and distinguishing PM facts from Jasper explanation or prioritization.

#### Scenario: Person explores work
- **WHEN** a person uses a projection to filter or prioritize work
- **THEN** the view shows available Plane records, authoritative links, timeline/context relationships, and a clear distinction between PM facts and Jasper interpretation

#### Scenario: Person opens a ticket from a node or timeline
- **WHEN** a person activates a projected ticket, link, timeline item, or node
- **THEN** the system provides a stable link back to the corresponding authoritative Plane record

### Requirement: Persistence and trusted network boundaries
A self-hosted local evaluation SHALL persist Plane's supported datastores and object-storage data in named volumes or equivalent durable storage, and SHALL persist Temporal state in its selected supported backing database. Databases, brokers, object storage, Temporal frontend gRPC, and internal administration paths MUST remain on trusted internal networks unless a later reviewed design explicitly changes the boundary. Production SHALL separately document externalized dependencies, backups, restore, secret delivery, and ingress.

#### Scenario: Local services restart
- **WHEN** the local Compose services are stopped and started again
- **THEN** accepted persistence checks verify that Plane data, object-storage data, and Temporal workflow history remain available, without treating this as production recovery evidence

#### Scenario: Untrusted client attempts internal access
- **WHEN** a client outside the trusted integration network attempts to reach a database, broker, object store, Temporal frontend, or internal administration path
- **THEN** the network policy denies direct access and exposes only the reviewed application ingress

### Requirement: Configuration, secrets, and image provenance
Plane and Temporal configuration SHALL be supplied through environment/configuration mechanisms appropriate to the selected release, and deployment secrets MUST be generated per deployment, kept out of committed artifacts and logs, and never copied from samples. Every selected image SHALL have a recorded repository, exact version/tag, immutable digest, source URL, retrieval date, and upgrade notes before implementation is accepted.

#### Scenario: Deployment is prepared
- **WHEN** an operator prepares a local or production deployment
- **THEN** sample values are replaced with deployment-specific secrets, configuration is reviewed, and image provenance is recorded before startup

#### Scenario: Image changes
- **WHEN** an image is upgraded or replaced
- **THEN** the new digest, compatibility evidence, configuration changes, and rollback point are recorded before the change is enabled

### Requirement: Health and readiness evidence
The implementation SHALL define and test separate process-health and dependency-readiness checks for the selected Plane and Temporal versions. Temporal gRPC health SHALL NOT be accepted as proof that backing dependencies are ready, and no undocumented Plane endpoint SHALL be assumed as normative. Acceptance SHALL record startup ordering, failure behavior, and evidence for application services and dependencies.

#### Scenario: Services start
- **WHEN** the selected local or production topology starts
- **THEN** verification demonstrates process responsiveness and separately demonstrates required database, queue, object-storage, visibility, and workflow dependencies are ready

#### Scenario: A dependency is unavailable
- **WHEN** a required dependency is unavailable
- **THEN** readiness remains false or the integration is blocked with a bounded diagnostic, and no PM mutation is reported as successful

### Requirement: Agent Server integration and rollback
The LangGraph Agent Server SHALL interact with Plane and Temporal only through an explicitly defined integration boundary, using stable references, bounded payloads, authorization, idempotency, and correlation. Rollback SHALL disable new integration writes/workflows and preserve Plane records, audit evidence, checkpoint references, and completed Temporal history.

#### Scenario: Read-only integration is verified
- **WHEN** the future adapter is first tested
- **THEN** it verifies Plane links, bounded reads, identity attribution, Temporal status reporting, conflict handling, and restart behavior without mutating PM records

#### Scenario: Integration rollback is invoked
- **WHEN** a release is rolled back
- **THEN** new writes are disabled or safely drained according to the reviewed Temporal policy, existing authoritative Plane records remain intact, and verification confirms no checkpoint or PM reference was deleted

### Requirement: Cross-linking without checkpoint duplication
OpenSpec changes and agent runs SHALL link to Plane records through stable references, while LangGraph checkpoints and Temporal workflow state SHALL NOT duplicate the Plane database.

#### Scenario: OpenSpec change is linked
- **WHEN** an OpenSpec change or agent run is associated with a Plane record
- **THEN** the association stores a stable Plane identifier/link and preserves navigation in both directions where supported

#### Scenario: Checkpoint is inspected
- **WHEN** a LangGraph checkpoint or Temporal workflow is persisted or rebuilt
- **THEN** it may retain bounded Plane and workflow references needed for execution context, but not a copied PM record database
