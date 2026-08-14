## Purpose

Define proposed human authority, stewardship, and transparent execution contracts for selecting and using models and providers.

## ADDED Requirements

### Requirement: Human-facing selection authority
The system SHALL treat the user’s explicit model/provider choice, or an explicitly approved profile choice, as the authority for selection within its stated scope. Jasper or another agent MAY recommend a choice, but SHALL NOT silently convert a recommendation into authorization.

#### Scenario: User selects a model
- **WHEN** a user selects a provider/model for a task or scope
- **THEN** the selection SHALL be retained as the governing choice until the user changes it or an explicit bounded policy says it expires

### Requirement: Approved agent-profile authority
An agent profile SHALL identify its owner/approver, version, allowed model/provider set, task scope, and expiry or revision boundary. A profile MAY supply defaults only where the user has approved that profile; it SHALL NOT override a more specific user selection.

#### Scenario: Profile conflicts with a user choice
- **WHEN** an approved profile and a current user selection differ
- **THEN** the more specific authorized user selection SHALL govern and the conflict SHALL be visible

### Requirement: Selection scope and precedence
Selection precedence SHALL be explicit and inspectable: explicit per-request user choice, explicit session/workspace choice, approved agent profile, authorized application default, then no selection. A broader scope SHALL NOT silently override a narrower scope, and `workspace_id` references SHALL retain their existing meaning.

#### Scenario: No applicable selection exists
- **WHEN** no authorized selection applies
- **THEN** the system SHALL report that selection is unresolved rather than inventing a provider/model

### Requirement: Local-first and cloud stewardship
Where local execution is available and verified for the task, local execution SHALL be preferred when consistent with the governing selection and task requirements. Cloud use SHALL require an authorized cloud-capable choice or policy, disclose the provider, and apply approved data, cost, region, and retention stewardship boundaries. Local-first SHALL NOT imply an unverified local capability.

#### Scenario: Local execution is unavailable
- **WHEN** the authorized local option cannot satisfy verified task requirements
- **THEN** the system SHALL report the limitation and offer only an explicit approved cloud option or an explicit failure

### Requirement: No silent provider or model switching
The system SHALL NOT silently switch provider, model, region, modality, or execution location. Any proposed alternative SHALL be presented as a proposed fallback and require the authorization defined by the applicable scope.

#### Scenario: Provider becomes unavailable
- **WHEN** the selected provider/model cannot be reached
- **THEN** the system SHALL preserve the selected identity, report the failure, and either await explicit retry/fallback authorization or terminate safely

### Requirement: Explicit failure, retry, fallback, and escalation
Each attempt SHALL expose a bounded status such as selected, starting, running, succeeded, failed, retryable, fallback-proposed, fallback-authorized, escalated, cancelled, or terminal-failed. Retries SHALL state whether they repeat the same provider/model and why; fallback and escalation SHALL identify the new authority and require approval where scope or stewardship changes.

#### Scenario: Retry is requested
- **WHEN** a retry is initiated
- **THEN** the system SHALL state whether it reuses the same selection and shall preserve the prior failure without fabricating continuity

### Requirement: User-visible identity and safe diagnostics
User-facing status and durable model-use records SHALL identify the selected and actual provider/model, profile/version or selection source, and relevant attempt outcome. Diagnostics SHALL expose safe identifiers, timing/resource summaries, and failure class while excluding credentials, auth headers, payloads, secrets, protected paths, and internal reasoning.

#### Scenario: Actual execution differs
- **WHEN** execution uses an identity different from the selected identity under an explicitly authorized fallback
- **THEN** the UI and record SHALL show both identities, the authorization/source, and reason for the difference
