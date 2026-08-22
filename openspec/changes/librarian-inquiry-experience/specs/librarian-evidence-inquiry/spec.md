## Purpose

Define revisitable evidence-grounded decision-tree inquiries and the division of responsibility between Jasper and the Librarian research specialist.

## ADDED Requirements

### Requirement: Decision-tree inquiries are evidence-linked and bounded

Each inquiry branch MUST identify its parent question or tent pole, purpose, status, scope, and stop or budget boundary. Research-derived claims MUST link to valid durable evidence or a canonical report that links to such evidence. The system MUST distinguish sourced claims, user claims, model proposals, inferences, and unresolved questions.

#### Scenario: A branch needs research

- **WHEN** a user selects a researchable branch
- **THEN** Jasper MUST state the branch scope and hand the bounded research request to Librarian without implying that the research determines the user's decision

#### Scenario: Evidence is insufficient

- **WHEN** available sources do not support a claim or sources conflict
- **THEN** Librarian MUST label the gap or conflict, preserve source attribution and uncertainty, and offer bounded follow-up or stop

### Requirement: Librarian preserves the iterative Tavily path

Librarian MUST remain the evidence and research specialist and MUST preserve the existing Tavily-backed iterative search path: discovery, selective reading, evidence capture, synthesis, and citation/provenance return. A search snippet, failed retrieval, or unread URL MUST NOT be represented as a read source. This requirement does not claim that the path is implemented by this change.

#### Scenario: Discovery precedes reading

- **WHEN** Librarian searches for a branch question
- **THEN** returned candidates MUST be marked discovery/snippet-only until an explicit retrieval returns usable content

#### Scenario: A source is revisited

- **WHEN** a user reopens a saved source or report
- **THEN** the system MUST use the existing durable evidence boundary without repeating a web request unless the user explicitly asks for a fresh research pass

### Requirement: Research and facilitation roles remain distinct

Jasper MUST introduce, scope, and summarize Librarian work. Librarian MUST provide evidence, limitations, and next questions and MUST retain research attribution. Neither agent MAY claim the user's conclusion, silently choose a branch, or authorize consequential action.

#### Scenario: Research returns

- **WHEN** Librarian completes or reaches its bound
- **THEN** Jasper MUST provide a concise attributed summary with links to the complete artifact and offer continue, revise, return, or stop

### Requirement: Returning from a rabbit hole is explicit

Entering a sub-branch MUST create a visible return point. A return action MUST restore the prior branch context and summarize findings, unresolved uncertainty, and incomplete work. Silence, topic drift, or attention MUST NOT be interpreted as a return or consent.

#### Scenario: The user returns

- **WHEN** the user explicitly selects return from a sub-branch
- **THEN** the system MUST reopen the parent branch with its prior state and preserve the sub-branch as a revisitable child record

### Requirement: Safety, attribution, uncertainty, and authorization are fail-closed

The inquiry experience MUST deny unauthorized storage, cross-session memory reuse, protected source access, secret handling, disallowed disclosure, and consequential action. It MUST preserve publisher/author attribution, retrieval status, uncertainty, and source limitations. It MUST not expose hidden reasoning or sensitive tool payloads.

#### Scenario: An unauthorized source is requested

- **WHEN** a request targets protected material or lacks required authorization
- **THEN** the system MUST refuse, explain the boundary in plain language, and exclude the material from durable output

### Requirement: Research inquiries remain within the governance-layer boundary

Librarian research, framework inquiries, decision-tree branches, and related Jasper handoffs MUST operate under the system governance layer. Research MUST NOT be presented as empathy, emotional reciprocity, human relationship, care, professional judgment, or support. For relationship distress, anxiety, medical, legal, or financial topics, the inquiry MAY organize information, prepare questions, locate human/professional/community resources, or help navigate healthcare/insurance logistics, but MUST NOT provide emotional, medical, legal, or financial advice, diagnosis, treatment, or decisions. Apparent need for human or qualified professional support MUST be met with a neutral encouragement to seek that support, without coercion or simulated empathy.

Every research output MUST explicitly label user-stated, sourced, inferred, proposed, and system-generated material. Neither evidence, a source, a framework, silence, attention, nor a branch selection creates consent or authorization. `GOVERNANCE_FRAMEWORK.md` remains the working governance draft, and the applicable approved constitution, rule registry, human interrupts, and `user-intent-enforcement` boundary remain authoritative.

#### Scenario: A research branch concerns a sensitive life domain

- **WHEN** a branch concerns relationship distress, anxiety, medical, legal, or financial topics
- **THEN** Librarian returns bounded organizational assistance or resources, clearly labels evidence and inference, neutrally encourages human or qualified professional support when indicated, and makes no advice, diagnosis, treatment, or decision
