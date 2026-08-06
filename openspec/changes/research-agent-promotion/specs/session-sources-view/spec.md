## Purpose

Provide an accessible future dashboard/visual-workspace contract for understanding Research activity, reviewing durable provenance and canonical reports, selecting safe presentation, and requesting evidence-bounded visual exploration without exposing unsafe execution detail.

## ADDED Requirements

### Requirement: Human-understandable Research workspace status

The future dashboard/visual workspace SHALL present human-understandable Research status, research brief/subquestions, progress, sources visited/read, retrieval failures and limitations, canonical report status, durable evidence/report artifacts, and sanitized execution history for the current session relationship. It SHALL distinguish observed retrieval status from model claims and SHALL not expose chain-of-thought, secret material, raw authentication data, or unsafe tool details.

#### Scenario: User reviews an active or completed Research run

- **WHEN** the user opens the Research workspace for an active or completed run
- **THEN** the workspace SHALL show available brief, subquestions, progress, source statuses, limitations, canonical report/artifact status, and sanitized history without presenting internal reasoning or sensitive execution material

#### Scenario: Retrieval fails or is limited

- **WHEN** an approved retrieval fails, is partial, or stops at a bound
- **THEN** the workspace SHALL display the recorded failure/limitation status without falsely presenting the source as read or the report as complete

### Requirement: Complete session source and canonical-report review

The session visual workspace SHALL list all saved session evidence and canonical Research reports, including artifacts not used in a visual concept map. Each evidence entry SHALL show its current session display name, immutable original title, source kind/status, retrieval time, truncation state when applicable, locator or provider identifier where safe, and visual/report usage. Each report entry SHALL show its artifact/status metadata, cited immutable evidence references, limitations, retrieval status, Research provenance, and source metadata needed to interpret citations. Web locators SHALL be available as safe clickable links.

#### Scenario: User opens sources with durable artifacts

- **WHEN** a session has saved Research evidence or reports and the user opens the workspace review surface
- **THEN** the view SHALL display the available durable metadata, citations, limitations, provenance, and associated visual usage

#### Scenario: User opens sources with no evidence

- **WHEN** a session has no saved Research evidence or reports
- **THEN** the view SHALL clearly report the empty state without implying that sources were lost or read

### Requirement: Safe style selection and presentation integrity

The future workspace SHALL offer human-facing report style selection with safe defaults after the renderer/service boundary is approved. It SHALL support separately configurable clean, accessible, professional work presentation and personal-interest/creative presentation. Every representation SHALL preserve canonical report content, citations, limitations, immutable evidence references/IDs, retrieval status, provenance, and source metadata; style SHALL NOT alter substance or Research authorship. Consistent branded/stylized output is intended, but final visual identity and branding are open decisions.

#### Scenario: User selects a report presentation style

- **WHEN** a user chooses an available report presentation style
- **THEN** the workspace SHALL identify the selected style and preserve the canonical report’s substantive and provenance fields with a safe default available when no choice is made

### Requirement: Accessible session-only display-name renaming

The Sources view SHALL let the user initiate a source display-name edit by keyboard or pointer, commit a non-empty name with Enter, cancel with Escape, and expose an accessible input name. Renaming SHALL change only the session-scoped display name; it SHALL NOT change immutable original title, locator, evidence identifier, content digest/version, provenance, report citation, or shared evidence body.

#### Scenario: User commits a new display name

- **WHEN** the user enters a non-empty replacement name and presses Enter
- **THEN** the view SHALL persist and render the replacement as the session display name while retaining immutable source provenance

#### Scenario: User cancels a rename

- **WHEN** the user presses Escape during a display-name edit
- **THEN** the view SHALL exit editing without changing the stored display name

### Requirement: Evidence-restricted visual concept-map request composition

The workspace SHALL allow the user or Jasper to select saved evidence and/or canonical-report evidence references for an approved visual concept map or other approved visual form. It SHALL compose the request with the permitted saved evidence identifiers so downstream grounding validation can enforce the restriction. Creating a visual from saved artifacts SHALL NOT require rereading the web.

#### Scenario: User maps selected evidence

- **WHEN** the user selects one or more saved evidence records or report evidence references and requests a visual concept map
- **THEN** the composed request SHALL identify only those selected saved evidence identifiers as permitted evidence

#### Scenario: User maps all saved session evidence

- **WHEN** the user makes no selections and requests a visual concept map
- **THEN** the composed request SHALL identify all saved session evidence as the permitted evidence set

### Requirement: Workspace accessibility and error behavior

The workspace SHALL expose semantic labeled source/report lists, discernible controls and selected-state labels, non-color-only loading/progress states, an alert for load failure, and keyboard-accessible style selection. It SHALL remain usable by keyboard and assistive technology without relying on hover-only instructions.

#### Scenario: Durable artifacts cannot be loaded

- **WHEN** saved session sources or reports cannot be loaded
- **THEN** the workspace SHALL present an accessible error alert and SHALL not display stale or fabricated metadata as current