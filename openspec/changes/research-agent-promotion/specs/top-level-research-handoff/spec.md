## Purpose

Define a visible, bounded Jasper–Research lifecycle in which Research owns autonomous in-depth research without granting hidden authority or exposing unsafe execution detail.

## ADDED Requirements

### Requirement: Visible top-level Research ownership and session relationship

The system SHALL expose Research as an independently addressable top-level LangGraph specialist and SHALL preserve its durable relationship to the originating session. Jasper SHALL assign or reopen Research work when authorized, introduce the transition, receive the final Research result, and provide a Jasper-authored synthesis when Research was Jasper-delegated. Direct selection of Research SHALL remain available and SHALL record Research's completed result without an unnecessary Jasper synthesis.

#### Scenario: Jasper delegates a research request

- **WHEN** Jasper determines that external evidence materially improves correctness or the user explicitly requests Research
- **THEN** the system SHALL route the bounded task to top-level Research, retain the delegation/session relationship, return Research's final result to Jasper, and record the completed turn after Jasper's response

#### Scenario: User selects Research directly

- **WHEN** the user directly selects Research for a request
- **THEN** the system SHALL run Research as the top-level specialist and record its final result without fabricating a Jasper synthesis

#### Scenario: Jasper reopens a saved research result

- **WHEN** Jasper reopens a durable Research report or selected saved evidence for the same session
- **THEN** the system SHALL retain the Research/session relationship and reuse the durable artifact without repeating web calls

### Requirement: Authorized bounded in-depth research workflow

Research SHALL own autonomous in-depth research and MAY use a bounded Open-Deep-Research-style internal process: clarify or refine the task only where authorized; create a research brief; plan and decompose subquestions; research across approved web and scholarly/reference-library providers with bounded potential parallelism; reflect on evidence gaps; perform bounded follow-up research; compress working context; and generate a canonical structured cited in-depth report. The process SHALL honor configured authorization scope, provider approvals, budgets, concurrency limits, and stop conditions; the specific governance policy values remain unresolved.

The official Open Deep Research repository (<https://github.com/langchain-ai/open_deep_research>) is a reference fact and candidate for either selective adaptation or possible use as Research’s core internal architecture integrated with the existing LangGraph Store/session evidence layer and Jasper access paths. License, version/compatibility, security, governance, and integration review SHALL precede any decision. This requirement does not claim adoption, installation, code copying, or implementation completion.

#### Scenario: Research runs an authorized multi-question inquiry

- **WHEN** an authorized Research request requires in-depth investigation
- **THEN** Research SHALL retain an inspectable brief and subquestions, conduct only bounded approved-provider research, identify material evidence gaps and limitations, and return a canonical structured cited report

#### Scenario: Research reaches a budget or stop condition

- **WHEN** a configured budget, rate, concurrency, or stop condition is reached
- **THEN** Research SHALL stop or degrade according to the applicable policy, preserve completed durable artifacts where safe, and report the limitation without claiming the inquiry is complete

### Requirement: Bounded and traceable handoff

A Jasper-initiated handoff SHALL preserve only the explicit research task, selected model, selected workspace identity, durable thread identity, user identity, saved evidence/report references, and the matching assistant tool-call and tool-result message pair needed to trace the delegation. The system SHALL preserve the returned final Research message with Research provenance and SHALL not expose Research internal reasoning or raw tool transcript as the visible result.

#### Scenario: Delegation records necessary context

- **WHEN** Jasper transfers a task to Research
- **THEN** the receiving Research run SHALL have the bounded handoff context and an inspectable matching tool-call/result pair

#### Scenario: Research returns a result or recoverable failure

- **WHEN** Research completes, blocks, or encounters a recoverable provider failure
- **THEN** the outer lifecycle SHALL retain a final Research-provenance result for Jasper or the direct-selection surface without publishing internal reasoning or unsafe tool transcript

### Requirement: Read-only Research authority

Research SHALL be limited to approved web and scholarly/reference-library research, explicitly selected page reads, saved-evidence/report reopening, analysis of supported user-provided extracted uploads, and discovery/reads of safe files in the selected repository path. Research SHALL NOT modify files, execute commands, crawl sites, access host files outside the selected workspace, or read secrets, credentials, environment files, private keys, authentication headers, or Git internals. It SHALL NOT receive a generic unrestricted tool surface.

#### Scenario: Research reads approved evidence

- **WHEN** Research needs an approved external, uploaded, saved, or selected-workspace source
- **THEN** it SHALL use the corresponding read-only bounded capability and retain the source status needed to distinguish the evidence type

#### Scenario: Research is asked to access protected material or mutate

- **WHEN** a Research request would write, execute, crawl, leave the selected workspace, or access protected material
- **THEN** the system SHALL deny the operation and retain no protected content in the visible response, execution history, or evidence record

### Requirement: Jasper presentation, provenance, and evidence-grounded visuals

Jasper SHALL preserve Research provenance while introducing and receiving Research work. Jasper MAY present a saved canonical Research report or create an approved visual concept map or other approved visual form from selected saved evidence and/or cited canonical-report evidence references without rereading the web. Jasper SHALL NOT claim a Research report as Jasper-authored work. Every research-derived visual claim SHALL pass evidence-grounding and citation validation, and TTS SHALL not speak raw URLs.

#### Scenario: Jasper presents a saved report

- **WHEN** Jasper presents a selected saved canonical Research report
- **THEN** the presentation SHALL preserve Research authorship/provenance and SHALL not invoke a new web read solely to recreate already saved support

#### Scenario: Jasper creates a visual from a saved report

- **WHEN** Jasper creates an approved visual concept map from a selected durable report and its evidence references
- **THEN** the visual SHALL cite valid selected saved evidence IDs and SHALL not invoke a new web read solely to recreate already saved support

#### Scenario: Delegated answer includes citations and narration

- **WHEN** Jasper synthesizes a completed Research result
- **THEN** the visible answer and visual references SHALL preserve usable Research provenance while audio omits raw URLsRLs