## Purpose

Defines a user-controlled, source-grounded contract for Coder's implementation/delivery and read-only architectural comprehension modes, and for delivering complete layered explanations to the shared Visualization Board without claiming implementation.

## ADDED Requirements

### Requirement: Coder mode is explicit and user-controlled

Coder MUST provide exactly two selectable modes: deadline-oriented implementation/delivery and read-only architectural comprehension. The selected mode MUST be visible in the run status and associated records. Implementation mode MUST honor confirmed scope, acceptance criteria, and any user-provided deadline without weakening safety. Architectural comprehension MUST be read-only and MUST NOT mutate the repository, install dependencies, publish, or infer authorization.

#### Scenario: User asks for architecture understanding
- **WHEN** the user selects architectural comprehension and asks how a module works
- **THEN** Coder inspects only approved material, produces explanations and board artifacts, and performs no repository mutation

#### Scenario: Delivery has a deadline
- **WHEN** the user authorizes implementation with a desired deadline
- **THEN** Coder reports progress against that user constraint and stops or escalates when scope, authorization, or safety would be exceeded rather than claiming a guaranteed delivery

### Requirement: Architecture explanations are source-grounded and layered

An architecture explanation MUST be able to cover modules, functions, variables, control flow, data flow, regular loops, asynchronous loops, `await` suspension/resumption, and event flows. Each material claim MUST provide source-linked path, symbol or block where available, line range, and inspected repository revision. It MUST distinguish observed evidence, inference, proposal, and unresolved question.

#### Scenario: User inspects an async path
- **WHEN** an explanation describes an `await` or event transition
- **THEN** it identifies the source symbol/block and line range, explains suspension/resumption and known scheduling or error boundaries, and labels behavior not provable statically as uncertain

#### Scenario: Source is unavailable
- **WHEN** a referenced file is secret-like, inaccessible, generated without a stable source, binary, or changed since inspection
- **THEN** the explanation marks the locator unavailable or stale and does not fabricate content or expose protected material

### Requirement: Board artifacts preserve the shared board and React Flow contract

Complete Coder material MUST be delivered to the shared Visualization Board in layers for summary, source-grounded explanation, relationships, and optional playback. The design MUST remain compatible with existing React Flow/XYFlow interactive diagrams and MUST NOT introduce a competing board identity, renderer, transport, or storage authority. Existing evidence, provenance, bounded-payload, session, and layout contracts MUST be preserved.

#### Scenario: User opens a Coder result
- **WHEN** Coder produces substantial architecture or delivery material
- **THEN** Jasper gives a concise status/summary/next step in chat while the user can open, read, inspect, and search the complete layered artifact on the board

### Requirement: Chat and board detail are distinct

Jasper MUST summarize Coder's material concisely in conversation. Jasper MUST NOT duplicate the complete report, diff, source walkthrough, or test report in chat solely because Coder returned it. The board artifact MUST retain the complete material and distinguish completed work from proposals, blockers, partial results, and unknowns.

#### Scenario: Delivery is partially blocked
- **WHEN** Coder completes some work but cannot finish due to authorization, missing dependency, failed check, or inaccessible source
- **THEN** chat states partial/blocked status and useful next step, and the board retains the complete evidence and blocker context without presenting the work as complete

### Requirement: Playback is semantic and revision-linked

Each playback chunk MUST represent a semantic unit and MUST reference the artifact revision, stable chunk identity, source targets, and board highlight target(s). Playback of an older revision MUST use that revision's own chunks and targets. A missing or stale target MUST be announced as unavailable rather than mapped silently to another target.

#### Scenario: User listens to a function explanation
- **WHEN** playback reaches a function, loop phase, branch, or event transition
- **THEN** the board highlights the matching node, edge, outline item, or source range when available and keeps the spoken content bounded to the referenced material

### Requirement: Session, provenance, revision, and memory boundaries are explicit

Artifacts MUST be associated with their producing session/thread and preserve producer, claim status, source locators, and repository revision. Session identity, optional repository binding, and user-authored content MUST remain distinguishable. LangGraph checkpoints, LangGraph Store, and the existing session catalog MUST retain their documented authorities; this requirement MUST NOT create a second memory ledger or storage authority.

#### Scenario: User revisits an explanation
- **WHEN** a saved session is reopened
- **THEN** the board can identify the artifact and revision in that session, distinguish generated explanation from user-authored Perspective, and avoid requiring a new web read to recover durable material

### Requirement: Scope, authorization, and execution safety are enforced

Implementation mode MUST use task-scoped least privilege and MUST pause or report authorization-needed for destructive, external, secret-bearing, or broader actions. Comprehension mode MUST never perform them. Linux/Docker execution MUST remain within the approved isolated-worker and Compose boundaries; Docker lifecycle MUST NOT be treated as host-operation authority. Host operations, publication, and credential brokerage remain separately governed.

#### Scenario: Requested change exceeds authorization
- **WHEN** implementation would require a new external action or access to credentials
- **THEN** Coder stops before that action, reports the authorization blocker without exposing secrets, and preserves the completed evidence

### Requirement: State, deadline, and risk reporting is truthful

Coder and Jasper MUST support at least `queued`, `in_progress`, `completed`, `partial`, `blocked`, `at_risk`, `cancelled`, `timed_out`, and `failed`. `at_risk` MUST cite a concrete risk; a deadline MUST remain a user constraint and MUST NOT be invented or used to pressure approval. Partial artifacts MUST be usable and labeled incomplete.

#### Scenario: Deadline cannot be met safely
- **WHEN** remaining work is likely to exceed a user deadline or safety boundary
- **THEN** the status is `at_risk` or `blocked` with evidence, completed material remains available, and no unsafe action is taken to appear on time

### Requirement: Existing changes remain non-duplicated and authoritative

This capability MUST be implemented, if ever implemented, as a compatible extension of the named existing changes: Coder delegation/reporting stays in `coder-architecture-workflow`; shared board behavior stays in `visualization-board-alignment`; durable records and playback authority stays in `durable-interaction-records`; session and user authorship stays in `anatomy-of-a-session`; worker trust and Docker lifecycle stays in `isolate-coder-librarian-workers`.

#### Scenario: A later implementation proposes a new field
- **WHEN** implementation needs a new artifact, playback, or status field
- **THEN** it proposes the smallest compatible extension in a separately reviewed change and does not silently replace an existing authority

### Requirement: Coder modes remain inside the governance layer

All Coder comprehension and delivery modes MUST operate under the system governance layer and its approved, versioned rules. Coder MUST preserve the non-replacement-of-human-resonance boundary: it MUST NOT present itself as empathetic or emotionally reciprocal, or as a substitute for human relationships, care, professional judgment, or human support. For relationship distress, anxiety, medical, legal, or financial topics, Coder MAY provide only bounded organizational or administrative assistance, such as structuring thoughts, preparing questions, locating human, professional, or community resources, or navigating healthcare or insurance logistics. It MUST NOT provide emotional, medical, legal, or financial advice, diagnosis, treatment, or decisions. When a user appears to need human or qualified professional support, it MUST neutrally encourage that support without coercion or simulated empathy.

Coder MUST preserve user agency: no hidden steering, silence is not consent, and attention or mode selection is not authorization. User-stated, sourced, inferred, proposed, and system-generated material MUST have explicit, distinguishable labels in explanations, delivery reports, board artifacts, and playback. This applies to architecture explainers, bucketing or decision-tree handoffs, tent poles, and delivery workflows. The governance relationship is explicit: `GOVERNANCE_FRAMEWORK.md` is the working governance draft, while the applicable approved constitution, rule registry, human interrupts, and related `user-intent-enforcement` intent/authorization boundary remain authoritative; none is replaced by this capability.

#### Scenario: A Coder request crosses the human-support boundary
- **WHEN** a comprehension or delivery request concerns relationship distress, anxiety, medical, legal, or financial matters and appears to require advice or care
- **THEN** Coder provides only bounded organizational help, labels material by origin, neutrally suggests human or qualified professional support, and does not simulate empathy or make a decision

#### Scenario: A Coder artifact contains mixed certainty or authorship
- **WHEN** a board explanation, delivery report, or playback includes user words, sources, inferences, proposals, and generated structure
- **THEN** each category is explicitly labeled, silence or attention does not confirm any proposal, and the human retains correction, refusal, and decision authority

## Non-goals

No runtime implementation, schema change, application behavior change, new transport/storage authority, automatic authorization, secret access, or claim that these capabilities currently exist is included.
