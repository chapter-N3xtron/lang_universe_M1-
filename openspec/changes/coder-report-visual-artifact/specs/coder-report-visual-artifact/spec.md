## Purpose

Define a durable, inspectable Coder report artifact for the existing session visual board while preserving Jasper's separate, plain-language speech-friendly explanation.

## ADDED Requirements

### Requirement: Coder terminal results create a versioned report artifact

Whenever Coder returns a validated `TechnicalReport` to Jasper, the existing return path SHALL create exactly one `coder_report` visual artifact derived deterministically from that report. The artifact SHALL use a literal supported version, a stable artifact identifier, a title, and a source message identifier when one is available. It SHALL preserve the technical report outcome, task notes, changed-file records, validation evidence, blockers, remaining authorization needs, material risks, and provenance necessary for review.

The artifact SHALL NOT be assembled from unvalidated legacy assistant prose, and it SHALL NOT replace `TechnicalReport` as the authoritative Coder-to-Jasper handoff.

#### Scenario: Completed Coder return
- **WHEN** Coder returns a valid completed report with changed files and passed source tests
- **THEN** one `coder_report` artifact is attached to the session and retains the report’s changed-file and source-test evidence without claiming deployed success

#### Scenario: Invalid Coder report
- **WHEN** Coder's report is absent, malformed, or unsupported
- **THEN** no report artifact is created from the invalid data and Jasper follows the existing fail-closed report limitation behavior

### Requirement: Report artifacts retain safe bounded file-diff evidence

For every changed file in a report artifact, the artifact SHALL retain its repository-relative path, change type, added line count, removed line count, and a diff availability state. Where safe source evidence is available, it SHALL contain the bounded before/after content or patch information needed by the documented diff renderer.

The capture process SHALL operate only in the explicitly selected repository, SHALL redact sensitive content before persistence and browser delivery, and SHALL never fabricate before/after code. Binary, unavailable, redacted, or budget-excluded files SHALL remain represented with an explicit reason that a visual diff is unavailable. The complete serialized artifact SHALL remain at or below the existing 256 KiB artifact limit. Omitted content SHALL be disclosed in the artifact rather than silently dropped.

#### Scenario: Safe changed source file
- **WHEN** Coder modifies a safe text file in the selected repository
- **THEN** its report artifact entry exposes the relative path, `−removed +added` count, and a renderable bounded diff

#### Scenario: Sensitive or oversized diff
- **WHEN** a changed file’s diff is sensitive, binary, unavailable, or would exceed the artifact budget
- **THEN** the report lists the file and its availability reason, does not persist the unsafe content, and does not present invented or silently truncated code

### Requirement: Session visual board displays report artifacts with library-provided tabs and diffs

The session visual board SHALL recognize supported `coder_report` artifacts in addition to existing `react_flow` artifacts. Selecting a report artifact SHALL render a technical report view using `@radix-ui/react-tabs` and `@pierre/diffs/react` rather than a handcrafted tab or diff engine.

The default Report tab SHALL display the technical report itself: completion outcome, task notes, changed-file entries, typed validation evidence, blockers, remaining authorization needs, and material risks. Each changed file SHALL be selectable by a tab trigger showing its repository-relative path and `−removed +added` count. Selecting that trigger SHALL open the corresponding file’s code diff in a separate board tab when a safe renderable diff exists, or a clear unavailable-diff explanation otherwise.

The tabs SHALL support keyboard navigation and a visible selected state. The active diff SHALL use the library's virtualized rendering path so large bounded diffs do not require every file tab to render at once.

#### Scenario: Inspecting a changed file
- **WHEN** a person selects `src/example.py −3 +12` from a Coder report
- **THEN** the board opens that file’s own tab and shows its code diff without changing the chat transcript or invoking a model

#### Scenario: Reviewing a report with multiple files
- **WHEN** a report artifact includes several changed files
- **THEN** the person can return to the technical Report tab and independently select each file tab without losing report context

### Requirement: Jasper remains the plain-language and speech-friendly walkthrough

After Coder returns, Jasper SHALL continue to generate the user-facing explanation through the existing validated `JasperResponse.voice_text` path. It SHALL give a complete concise plain-language walkthrough of the typed report and distinguish completed, incomplete, blocked, failed, and cancelled outcomes and evidence limits.

The speech-friendly walkthrough SHALL NOT read raw diff content, code excerpts, tab labels, full file lists, or serialized artifact data. Creating or rendering a report artifact SHALL NOT add or alter any text-to-speech endpoint, server audio stream, browser speech transport, or approval behavior.

#### Scenario: Report artifact and voice explanation coexist
- **WHEN** Coder returns a report with a renderable diff
- **THEN** the board presents the inspectable technical report and diff while Jasper's existing `voice_text` gives the separate plain-language walkthrough

### Requirement: Saved report artifacts remain safely renderable across presentation changes

A saved supported report artifact SHALL retain a literal version and render independently of later visual layout changes. An unsupported artifact version SHALL show a concise visible compatibility limitation and SHALL NOT be interpreted as a code diff. Existing `react_flow` concept-map artifacts SHALL continue to render unchanged.

#### Scenario: Existing concept map
- **WHEN** a session contains a prior `react_flow` artifact
- **THEN** it remains selectable and renders through the existing concept-map renderer

#### Scenario: Unsupported report artifact version
- **WHEN** a session contains a `coder_report` artifact with an unsupported version
- **THEN** the visual board identifies the compatibility limitation and does not display arbitrary stored data as executable or trustworthy code-diff content
