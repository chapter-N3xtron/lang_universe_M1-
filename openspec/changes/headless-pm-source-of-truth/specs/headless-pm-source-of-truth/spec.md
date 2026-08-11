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
