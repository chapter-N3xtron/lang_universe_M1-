## Purpose

Define a truthful, machine-validated Coder-to-Jasper result contract and the concise spoken summary Jasper derives from it after delegated coding work returns.

## ADDED Requirements

### Requirement: Coder returns a versioned typed technical report
Whenever Coder returns control after a delegated task, the system SHALL provide Jasper exactly one strict `TechnicalReport` object with all of these required top-level fields: `version`, `completion_status`, `task_notes`, `changed_files`, `validation_evidence`, `blockers`, `remaining_authorization_needs`, `material_risks`, `provenance`, and `supporting_references`. `version` SHALL equal `"1.0"`; unknown versions and extra or missing fields SHALL be invalid. Array-valued fields SHALL be present even when empty.

The fields SHALL have these types and bounds:

- `completion_status`: one of `completed`, `partial`, `blocked`, `failed`, or `cancelled`.
- `task_notes`: at most 64 objects, each requiring `task`, `status` (`completed`, `incomplete`, `blocked`, `failed`, or `skipped`), and `note`.
- `changed_files`: at most 256 objects, each requiring repository-relative `path`, `change_type` (`added`, `modified`, `deleted`, or `renamed`), and `summary`.
- `validation_evidence`: at most 64 objects, each requiring `type` (`source_test`, `static_analysis`, `build`, `runtime_check`, `deployment_check`, or `manual_inspection`), `result` (`passed`, `failed`, `not_run`, or `inconclusive`), `description`, and up to 8 `reference_ids`.
- `blockers`: at most 32 non-empty plain-text entries.
- `remaining_authorization_needs`: at most 32 objects, each requiring `action` and `reason`.
- `material_risks`: at most 32 objects, each requiring `risk`, `impact`, and `mitigation`.
- `provenance`: an object requiring `producer` equal to `Coder`, `coding_session_id`, `thread_identity`, `workspace`, nullable `model`, and ISO-8601 `generated_at`.
- `supporting_references`: at most 16 objects, each requiring unique `id`, `kind` (`file`, `command_output`, `test_output`, `execution_manifest`, or `other`), `locator`, and `summary`.

Every `reference_id` SHALL resolve to an `id` in `supporting_references`. Text fields and references SHALL be concise, SHALL NOT contain raw internal reasoning or secrets, and SHALL use repository-relative locators where a repository-relative path exists.

#### Scenario: Completed task has no empty-field ambiguity
- **WHEN** Coder completes a task that changes files and passes source tests without blockers, authorization needs, or material risks
- **THEN** Coder returns a version `1.0` report with `completion_status` set to `completed`, populated task, file, and typed validation entries, and explicit empty arrays for the three absent concern categories

#### Scenario: Return with no changed files
- **WHEN** Coder performs analysis but makes no repository changes
- **THEN** the report contains an empty `changed_files` array and task notes that accurately describe the outcome

#### Scenario: Supporting references exceed the contract bound
- **WHEN** more than 16 candidate supporting references exist
- **THEN** Coder includes no more than 16 references selected for material relevance and does not evade the bound by embedding raw evidence in another field

### Requirement: Completion status reflects the whole report
Coder SHALL select `completed` only when all requested in-scope tasks are complete and no blocker or remaining authorization need prevents the requested outcome. Coder SHALL use `partial`, `blocked`, `failed`, or `cancelled` as applicable and SHALL record the material explanation in task notes and the corresponding blocker, authorization, risk, or failed validation fields. Empty changed-file or validation arrays SHALL NOT by themselves imply completion.

#### Scenario: Authorization is still required
- **WHEN** implementation is prepared but a requested action still requires human authorization
- **THEN** the report is not `completed` and identifies the action and reason in `remaining_authorization_needs`

#### Scenario: Validation fails after files change
- **WHEN** Coder changes files and a relevant validation command fails
- **THEN** the report uses a non-completed status, retains the changed-file entries, and records failed typed validation evidence rather than concealing the failure

### Requirement: Jasper consumes the report after Coder returns
After Coder returns, Jasper SHALL consume the validated `TechnicalReport` as the authoritative handoff input before producing the user-facing result. Jasper SHALL NOT bypass the report by directly relaying Coder's legacy plain-text completion message, and Coder's raw report serialization SHALL NOT be used as user-facing prose.

#### Scenario: Valid report replaces the plain-text bypass baseline
- **WHEN** Coder returns a valid report and also has internal or legacy assistant text available
- **THEN** Jasper derives the user response from the report and does not directly relay the legacy text

#### Scenario: Report says work is incomplete
- **WHEN** the report has `completion_status` set to `partial`, `blocked`, `failed`, or `cancelled`
- **THEN** Jasper's summary clearly states that outcome and includes the material reason without presenting the requested work as complete

### Requirement: Jasper produces a concise voice-friendly summary
Jasper SHALL transform the report into plain-English `voice_text` suitable for the existing browser sidecar speech path. The summary SHALL use no more than two short paragraphs, lead with the completion outcome, concisely cover material work and validation, and mention blockers, remaining authorization needs, or material risks when present. It SHALL NOT dump serialized report text, JSON, tables, raw command output, exhaustive file lists, or internal tool transcripts.

#### Scenario: Large successful report
- **WHEN** a valid completed report contains many task, file, and evidence entries
- **THEN** Jasper produces a concise plain-English synthesis rather than enumerating or serializing every report entry

#### Scenario: Material risk accompanies completion
- **WHEN** a report is otherwise complete but contains a material risk
- **THEN** Jasper includes that risk in the concise summary rather than omitting it to make the result sound unqualified

### Requirement: Validation claims preserve evidence type and limits
Jasper SHALL distinguish source tests, static analysis, builds, runtime checks, deployment checks, and manual inspection when describing validation. A passed `source_test`, `static_analysis`, or `build` entry SHALL NOT be described as proof that deployment succeeded. Jasper SHALL make a positive deployment claim only when the report contains relevant passed `deployment_check` evidence; adding deployed acceptance execution is outside this capability.

#### Scenario: Only source tests pass
- **WHEN** the report contains passed source-test evidence and no passed deployment-check evidence
- **THEN** Jasper may say the source tests passed but does not say or imply that the system was deployed or works in deployment

#### Scenario: Deployment check fails
- **WHEN** source tests pass but a deployment check fails
- **THEN** Jasper discloses the failed deployment check and does not allow the source-test result to conceal or override it

### Requirement: Invalid reports fail closed and visibly
If Coder's handoff is missing, malformed, over a bound, or uses an unsupported version, the system SHALL reject it as an authoritative completion report. Jasper SHALL give the user a concise plain-English statement that the coding result could not be verified, SHALL NOT claim completion, and SHALL NOT fall back to presenting unvalidated legacy completion text as fact.

#### Scenario: Unsupported report version
- **WHEN** Coder returns a report version other than `1.0`
- **THEN** Jasper states that the coding result could not be verified and makes no completion or deployment claim

#### Scenario: Reference does not resolve
- **WHEN** validation evidence cites a reference ID absent from `supporting_references`
- **THEN** the report is invalid and Jasper exposes the verification limitation without dumping the invalid report

### Requirement: Existing speech transport remains unchanged
This capability SHALL continue to emit the summary through the existing Jasper structured response and browser-sidecar speech architecture. It SHALL NOT add, replace, or modify text-to-speech transport.

#### Scenario: Summary is ready for speech
- **WHEN** Jasper finishes summarizing a valid or invalid Coder handoff
- **THEN** the plain-English summary is supplied through the existing `voice_text` response field with no new speech endpoint, server audio stream, or transport message
