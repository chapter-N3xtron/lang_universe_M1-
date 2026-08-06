## Purpose

Define bounded, durable, provenance-preserving Research evidence and authoritative canonical report artifacts that can be safely reopened across a session and its forks without repeating retrieval or treating discovery metadata as proof that a page was read.

## ADDED Requirements

### Requirement: Bounded immutable content-versioned evidence records

The system SHALL store each eligible saved Research evidence body as an immutable, bounded, content-versioned record in the existing durable LangGraph Store boundary and SHALL retain lightweight references in session/checkpoint state. Each durable record SHALL preserve a stable evidence identifier; source/provider identifier or URL/locator; source kind and retrieval status; bounded retrieved/extracted content; retrieval timestamp; content hash/version; provenance; truncation state; and metadata required to evaluate the source. Checkpoints SHALL contain only bounded working context, resumable run state, and lightweight references.

#### Scenario: Evidence exceeds the retention bound

- **WHEN** retrieved or extracted evidence exceeds the configured body-size bound
- **THEN** the system SHALL retain only the bounded body and mark the durable record as truncated

#### Scenario: Evidence is recorded for a session

- **WHEN** Research saves eligible evidence while operating in a durable session
- **THEN** the durable body and required metadata SHALL be stored through the existing Store boundary while session/checkpoint state retains only its lightweight reference

### Requirement: Evidence status and source-type integrity

The system SHALL distinguish an unopened search result, explicitly read page, supported extracted upload, safe selected-workspace file, partial retrieval, and retrieval failure. The system SHALL NOT represent a search snippet, failed retrieval, or unavailable page as a read page.

#### Scenario: Web search returns discovery results

- **WHEN** Research saves a web-search result without opening its URL
- **THEN** the saved source SHALL be identified as snippet-only evidence rather than a visited/read page

#### Scenario: Explicit page read succeeds or fails

- **WHEN** Research explicitly reads a selected URL
- **THEN** the system SHALL save a visited/read-page record only when usable page content is returned; otherwise it SHALL preserve the failure or partial status without mislabeling the URL as read

### Requirement: Authoritative canonical cited report artifacts and offline reopen

The system SHALL save each completed or bounded-partial in-depth report as an authoritative canonical accessible text/structured report artifact in the existing LangGraph Store boundary. A canonical report artifact SHALL identify its report/version identity, session relationship, status, research brief and subquestion summary, generated timestamp, structured cited content, cited immutable evidence identifiers, limitations, retrieval status, Research authorship/provenance, and source metadata needed to interpret citations. The system SHALL permit reopening a canonical report and its cited saved evidence without repeating web calls.

#### Scenario: Research completes an in-depth report

- **WHEN** Research completes an in-depth investigation with cited saved evidence
- **THEN** the system SHALL persist a canonical structured report artifact that cites valid durable immutable evidence identifiers

#### Scenario: A saved report is reopened

- **WHEN** a user or Jasper reopens a durable report
- **THEN** the system SHALL retrieve the saved canonical report and its cited evidence references without invoking a new web retrieval

### Requirement: Rendered representation integrity and renderer boundary

Any rendered representation of a canonical report SHALL preserve its content, citations, limitations, immutable evidence references/IDs, retrieval status, provenance, and source metadata. Presentation style SHALL NOT alter substance. An eventual Research-owned renderer/service SHALL consume saved canonical report/evidence references only; SHALL retain Research authorship/provenance; SHALL NOT access secrets, raw authentication material, unsupported local paths, protected workspace material, or the web; and SHALL NOT introduce attribution laundering. Renderer implementation, templates, output formats, printable/exportable PDF, dependencies, visual identity, branding, artifact-storage lifecycle, and export/open/download authorization are open decisions.

#### Scenario: A representation is requested

- **WHEN** an authorized representation of a saved canonical report is requested
- **THEN** it SHALL resolve only saved canonical report/evidence references and preserve every required substantive and provenance field

#### Scenario: A renderer requests prohibited input or access

- **WHEN** the renderer/service is asked to access a secret, raw auth material, unsupported path, protected workspace material, or the web
- **THEN** the system SHALL deny the request without incorporating protected content into the representation, logs, or durable artifacts

### Requirement: Deduplication, version preservation, reuse, and forks

The system SHALL reuse a previously saved immutable body when an identical source kind, locator, and bounded content digest is encountered. Changed content SHALL receive a distinct version identity. Saved evidence and canonical reports SHALL be reopenable without another web request, and forked sessions SHALL inherit references to existing immutable bodies and report artifacts without copying those bodies.

#### Scenario: Identical evidence is encountered again

- **WHEN** Research saves evidence with the same source kind, locator, and bounded content digest as an existing record
- **THEN** the system SHALL reference the existing immutable record rather than create a duplicate body

#### Scenario: Fork reuses inherited artifacts

- **WHEN** a session is forked after Research has saved evidence or reports
- **THEN** the fork SHALL retain usable inherited references to the existing durable artifacts without duplicating their bodies

### Requirement: Grounded Research visuals

The system SHALL permit a research-grounded visual concept map or other approved visual form only when every research-derived claim cites valid saved evidence identifiers, either directly or through a canonical report's validated evidence references. The system SHALL reject or withhold a research-grounded visual when adequate saved evidence is unavailable, and SHALL identify proposed, inferred, user-defined, and observed claims distinctly from researched claims.

#### Scenario: Visual has complete evidence citations

- **WHEN** Jasper requests a research-grounded visual from selected saved sources or a saved canonical report
- **THEN** every research-derived claim SHALL reference valid permitted saved evidence identifiers

#### Scenario: Visual has missing or invalid evidence

- **WHEN** a research-derived visual claim lacks a valid permitted saved evidence identifier
- **THEN** the system SHALL not publish that visual as grounded research