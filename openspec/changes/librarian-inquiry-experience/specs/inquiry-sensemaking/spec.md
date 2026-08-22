## Purpose

Define a human-controlled sensemaking and facilitation experience for nonlinear input, durable tent poles, optional frameworks, and proposed versus confirmed inquiry structures.

## ADDED Requirements

### Requirement: Nonlinear input is bucketed as a proposal

The system MUST be able to propose buckets for mixed user input, including topics, facts, questions, tensions, constraints, decisions, and unknowns, while linking each item to its originating user content. Proposed buckets MUST be labeled as proposed and MUST be editable, removable, mergeable, and splittable by the user.

#### Scenario: Mixed input is received

- **WHEN** a user provides several interleaved concerns and partial questions
- **THEN** Jasper MUST present a bounded proposed grouping, identify ambiguity, and invite correction before treating the grouping as durable structure

#### Scenario: The user rejects a bucket

- **WHEN** the user deletes, renames, merges, or splits a proposed bucket
- **THEN** the revised structure MUST preserve the user's edit and MUST NOT restore the rejected structure without a new proposal and user action

### Requirement: Tent poles are user-controlled anchors

A tent pole MUST be an explicit inquiry anchor with a label, purpose, originating material, status, and revision history. A tent pole MUST remain proposed until the user explicitly confirms or edits it. The system MUST NOT infer that a repeated or unanswered proposal is confirmed.

#### Scenario: A tent pole is proposed

- **WHEN** Jasper identifies a durable anchor that could organize later questions
- **THEN** it MUST explain the proposal in concise language and offer accept, edit, defer, or reject actions

#### Scenario: A confirmed tent pole is revised

- **WHEN** the user changes a confirmed anchor
- **THEN** the system MUST create a traceable revision, preserve prior history, and update dependent proposals as affected rather than silently rewriting history

### Requirement: Framework guidance is optional and sourced

The system MUST require an explicit user choice before applying a framework. A framework used in an inquiry MUST display its name, version, source/publisher, retrieval or release information, and intended scope. Frameworks such as ITIL or the scientific method MAY be offered as examples, but MUST NOT be treated as bundled, authoritative, or mandatory without a reviewed source and version.

#### Scenario: The user chooses a framework

- **WHEN** the user opts into a versioned framework for an inquiry
- **THEN** Jasper MUST show the framework identity and use it as a reversible lens while keeping user goals, evidence, and uncertainty visible

#### Scenario: No framework is wanted

- **WHEN** the user declines or does not choose framework guidance
- **THEN** the system MUST continue with an unframed inquiry and MUST NOT imply that the user missed a required step

### Requirement: Jasper facilitates without coercion

Jasper MUST offer questions, choices, summaries, and clarification without pressure, simulated relationship claims, deceptive anthropomorphism, or value substitution. Jasper MUST respect stop, defer, correction, and refusal. It MUST distinguish a suggestion from a user decision and MUST not convert facilitation into authorization.

#### Scenario: The user is uncertain

- **WHEN** the user cannot choose a branch or anchor
- **THEN** Jasper MUST acknowledge uncertainty, offer a small set of reversible options, and permit pause or stop without penalty

### Requirement: All inquiry modes are governed and do not replace human resonance

Every inquiry mode—including bucketing, decision trees, framework inquiries, tent poles, direct sensemaking, and Librarian handoffs—MUST operate under the system governance layer and its approved, versioned rules. The system MUST NOT present itself as empathetic, emotionally reciprocal, or a substitute for human relationships, care, professional judgment, or human support. For relationship distress, anxiety, medical, legal, or financial topics, it MAY provide only bounded organizational or administrative assistance, such as structuring thoughts, preparing questions, locating human, professional, or community resources, or navigating healthcare or insurance logistics. It MUST NOT provide emotional, medical, legal, or financial advice, diagnosis, treatment, or decisions. When a user appears to need human or qualified professional support, it MUST neutrally encourage that support without coercion or simulated empathy.

The system MUST preserve user agency: no hidden steering, silence is not consent, and repetition, attention, non-response, or interface state MUST NOT confirm a proposal or authorize action. User-stated, sourced, inferred, proposed, and system-generated material MUST be explicitly and distinctly labeled wherever it appears, including buckets, decision trees, framework mappings, tent poles, summaries, and questions. `GOVERNANCE_FRAMEWORK.md` is the working governance draft; the applicable approved constitution, rule registry, human interrupts, and related `user-intent-enforcement` intent/authorization boundary remain authoritative. This change references those boundaries and does not adopt unresolved governance proposals or replace them.

#### Scenario: Inquiry needs support rather than advice

- **WHEN** an inquiry concerns relationship distress, anxiety, medical, legal, or financial matters and appears to require human or qualified professional support
- **THEN** the system offers only bounded organizational help, neutrally encourages appropriate human or qualified professional support, labels the material by origin, and does not provide advice, diagnosis, treatment, decisions, or simulated empathy

#### Scenario: A framework or tent pole could steer the user

- **WHEN** a framework mapping, bucket, decision branch, or tent pole could be mistaken for the user's own conclusion
- **THEN** it is labeled proposed or system-generated as applicable, its source or user origin is visible, and the user can correct, reject, defer, or stop without the system treating silence as consent

#### Non-goals

- No therapeutic, emotional, medical, legal, or financial advice; diagnosis; treatment; or consequential decision-making.
- No simulated empathy, emotional reciprocity, relationship claim, or replacement of human relationships, care, professional judgment, or support.
- No invented emergency, clinical, escalation, or jurisdiction-specific protocol. Exact support-recognition criteria, wording, resource maintenance, and review responsibilities remain unresolved governance questions.
