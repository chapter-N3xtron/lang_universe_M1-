## Purpose

Defines a future human-controlled integration boundary where a self-hosted project-management engine remains authoritative while Jasper and TanStack expose safe, attributable projections and links.

## ADDED Requirements

### Requirement: PM authority and human editing boundary
The future system SHALL treat the self-hosted PM engine as the headless source of truth for PM records and SHALL keep its native browser UI available for complete human editing. Jasper and TanStack projections MUST NOT silently become a competing PM database.

#### Scenario: Human opens the native PM UI
- **WHEN** a person follows a PM link from Jasper or a TanStack projection
- **THEN** the native PM browser UI opens with the authoritative record available for full human editing

#### Scenario: Projection is rebuilt
- **WHEN** a TanStack/Jasper projection is refreshed or rebuilt
- **THEN** it is derived from PM authority and does not replace or duplicate the authoritative PM record store

### Requirement: Attributed and conflict-aware Jasper changes
The integration SHALL identify Jasper with a distinct integration identity and SHALL make Jasper edits attributable, auditable, previewable, approval-gated where appropriate, and conflict-aware.

#### Scenario: Jasper proposes an edit
- **WHEN** Jasper prepares a PM edit
- **THEN** the system presents the target, proposed change, integration identity, and relevant revision/conflict information before applying it

#### Scenario: Concurrent human edit exists
- **WHEN** the PM record changed after Jasper read it
- **THEN** the system detects the conflict and does not silently overwrite the human's newer change

#### Scenario: Approval is required
- **WHEN** an edit falls within a configured approval-gated class
- **THEN** the edit remains unapplied until the applicable human approval is granted

### Requirement: Lightweight projections and conversational navigation
TanStack/Jasper SHALL provide projections for lists, filters, lightweight tickets, links, timelines, node visualizations, and conversational explanation/prioritization, while preserving links to authoritative PM records and avoiding unsupported claims of PM authority.

#### Scenario: Person explores work
- **WHEN** a person uses a projection to filter or prioritize work
- **THEN** the view shows the available PM records, their authoritative links, timeline/context relationships, and a clear distinction between PM facts and Jasper explanation or prioritization

#### Scenario: Person opens a ticket from a node or timeline
- **WHEN** a person activates a projected ticket, link, timeline item, or node
- **THEN** the system provides a stable link back to the corresponding authoritative PM record

### Requirement: Cross-linking without checkpoint duplication
OpenSpec changes and agent runs SHALL be able to link to PM records through stable references, but LangGraph checkpoints SHALL NOT duplicate the PM database or become the PM system of record.

#### Scenario: OpenSpec change is linked
- **WHEN** an OpenSpec change or agent run is associated with a PM record
- **THEN** the association stores a stable PM reference and preserves navigation in both directions where supported

#### Scenario: Checkpoint is inspected
- **WHEN** a LangGraph checkpoint is persisted or rebuilt
- **THEN** it may retain bounded PM references needed for execution context, but not a copied PM record database

### Requirement: Sandboxed Plane and Temporal architecture
The proposed integration SHALL be evaluated first in a sandboxed, self-hosted environment. Plane SHALL be the human PM and prioritization layer for PM records, status, approvals, and native human editing. Temporal SHALL be the durable scheduling and orchestration layer for timers, retries, workflow state, and execution history. LangGraph SHALL remain the execution/runtime boundary, and Jasper, Coding, Research, and Librarian SHALL retain their existing specialist and reporting boundaries. This requirement records an authorized proposal, not an implemented deployment.

#### Scenario: Proof of concept is started
- **WHEN** an implementation begins evaluation
- **THEN** it uses isolated infrastructure, synthetic or explicitly approved data, constrained least-privilege access, observable boundaries, and teardown/rollback evidence before any production connection

#### Scenario: A system boundary is queried
- **WHEN** a PM, orchestration, agent, or repository record is read or changed
- **THEN** the operation uses the owning system and does not create a competing authority in another system's checkpoints, Store, projection, or PM records

### Requirement: Single trigger and dispatcher boundary
The integration SHALL use one small, authenticated trigger/dispatcher boundary for approved cross-system events rather than a chain of separate point-to-point adapters. The dispatcher SHALL validate scope and authorization, assign correlation and deterministic idempotency identifiers, and start or signal the appropriate Temporal workflow or LangGraph handoff.

#### Scenario: Event is delivered more than once
- **WHEN** the same trigger is retried, replayed, or delivered out of order
- **THEN** idempotency and revision checks converge without duplicate PM records, workflow starts, mutations, or OpenSpec intent

#### Scenario: Human approval is absent
- **WHEN** a requested operation requires approval and approval is not recorded
- **THEN** the dispatcher does not mutate Plane, repository/issue records, OpenSpec artifacts, Temporal-owned state, or agent-owned records

### Requirement: Authority, integration, and decision gates
OpenSpec SHALL remain authoritative for development intent within each repository. Plane MAY mirror OpenSpec change, artifact, and task references for prioritization but SHALL NOT silently rewrite or supersede them. Repository/issue integration SHALL evaluate GitHub and GitLab using the documented community OpenSpec extension, API/webhook and authentication surface, least-privilege security, idempotency/concurrency behavior, operational weight, and Plane integration fit; the lighter-weight option SHALL be selected only after evidence is recorded. The final provider choice is unresolved by this change.

#### Scenario: PM status conflicts with repository intent
- **WHEN** a Plane projection disagrees with a repository-local OpenSpec artifact
- **THEN** the repository-local OpenSpec artifact remains authoritative and the discrepancy is surfaced for explicit resolution

#### Scenario: Provider selection is reviewed
- **WHEN** GitHub and GitLab are compared for the repository/issue boundary
- **THEN** the review records the extension evidence, Plane fit, security/authorization, event/retry, concurrency, maintenance, and deployment-cost criteria without claiming a final choice prematurely

### Requirement: Explicit ownership and safety controls
The integration SHALL define ownership, actor attribution, approval, revision/conflict handling, concurrency limits, cancellation, failure/reconciliation, and least-privilege security for every cross-system operation. Credentials, protected paths, raw authentication material, and internal reasoning MUST NOT be stored in PM records, Temporal/LangGraph state, OpenSpec artifacts, logs, or telemetry.

#### Scenario: Concurrent human edit exists
- **WHEN** a human changes a Plane or repository record after an agent read it
- **THEN** stale-revision/conflict detection prevents silent last-writer-wins overwrite and requires explicit resolution or approval

#### Scenario: A stage fails
- **WHEN** a trigger, workflow, or projection fails after a partial result
- **THEN** the system records bounded sanitized reconciliation state, permits safe retry or cancellation, and preserves the owning authority without creating a duplicate source of truth

### Requirement: Staged proof of concept before production
The integration SHALL progress through explicit stages: architecture/threat-model review; isolated read-only Plane/Temporal connectivity; one synthetic-data dispatcher path; approval, idempotency, concurrency, replay, security, and failure tests; and only then a separately authorized limited pilot. Production deployment or migration requires a later approved change.

#### Scenario: Proof-of-concept evidence is incomplete
- **WHEN** a stage lacks authorization, security, ownership, or replay/concurrency evidence
- **THEN** the next stage and all production writes remain blocked

### Related model-use reference boundary
PM projections may carry sanitized references to authorized agent runs and durable model-use records, including stable record IDs and selected/actual identity where approved. They SHALL not become a competing authority for model selection or duplicate model-use payloads; selection behavior belongs to `../model-selection-and-stewardship/` and durable records to `../durable-interaction-records/`.
