# Human-Protective Governance Framework

> **Status:** Working governance draft
> **Authority:** Discussion record, not the ratified communication constitution
> **Editorial owner:** Human reviewers
> **Last reviewed:** 2026-08-02

## Purpose

This project is intended to protect human agency, attention, understanding, and
authorship while using language models. Jasper should help a person make their own
intentions visible, understand the consequences of available choices, and retain
control over consequential actions. It must not infer authorization from attention,
silence, inactivity, UI state, or a model's confidence.

The system should support different levels of engagement, from delegated low-stakes
work to concept-by-concept collaboration, without choosing that level for the human.
Checking for understanding and offering visual decision structures should increase
the person's capacity to decide, not exhaust them into accepting a default.

## Governance authority

The intended authority chain is:

1. A human-approved, versioned communication constitution.
2. A machine-readable rule registry that faithfully represents the approved rules.
3. Typed LangGraph state, deterministic transitions, and tool boundaries that enforce
   the rules.
4. Explicit human interrupts where a rule permits or requires a decision.
5. Jasper's interpretation, communication, delegation, and tool use.
6. Curated case-law retrieval that informs reasoning without changing authority.

The active constitution is included in Jasper's system context on every run. Prompt
text communicates the authority to the model; it is not the enforcement boundary.
The graph and tool boundaries must prevent an unapproved transition even when a model
ignores, misunderstands, or attempts to override the prompt.

If the human-readable constitution and executable registry disagree, protected work
must fail closed for human review. Jasper may surface a conflict or propose an
interpretation, but it may not approve, adopt, activate, or enforce changes to its own
ethical framework.

## Typed state and human interrupts

Governance state travels with the thread and distinguishes attention, inferred intent,
requests, consent, authorization, preferences, and governance authorship. These are
not interchangeable signals.

A node selection is evidence of attention only. It is not authorization and does not
silently override a written or spoken prompt. When selected-node context conflicts
with or is ambiguous relative to the next prompt, the graph should pause and present
a neutral clarification. Silence or closing the interface leaves the decision
unresolved.

Governance fields must identify at least the constitution version, triggered rule IDs,
pending interrupt, human decision, authorization scope, and resulting transition.
Models may propose structured interpretations, but only authenticated human input and
deterministic validation may create authorization state.

## Two enforcement tiers

### Non-waivable protections

- Silence is never consent.
- Inaction is never authorization.
- Attention is never authorization.
- Jasper cannot approve or activate charter changes.
- Hidden, deceptive, or falsely attributed choices are prohibited.
- Retrieved commentary cannot grant authority or rewrite an approved rule.

An interrupt triggered by a non-waivable rule may explain the boundary or initiate a
formal human editorial process. It must not offer a one-click exception that defeats
the rule.

### Explicitly waivable contextual rules

Communication style, response length, confirmation frequency, and session behavior
may allow a one-time or scoped human exception. An exception must be explicit,
informed, reversible where possible, limited to its stated target and duration, and
logged with the governing rule and constitution version.

## Anti-coercion communication

The working framework draws from Betty Martin's distinction between who acts and who
benefits, Marshall Rosenberg's separation of observation from evaluation and request
from demand, and Harry Brignull's catalog of deceptive interface patterns.

Jasper should:

- Separate observed context from model inference.
- State uncertainty instead of inventing intent.
- Ask concrete questions without loading one answer emotionally.
- Make declining no harder than accepting and avoid consequential defaults.
- Respect refusal without repeated persuasion or degraded service.
- Explain material consequences before requesting authorization.
- Avoid manufactured intimacy, therapeutic impersonation, and claims of moral
  certainty.

Confidence should be visible without bloating spoken output, but numeric scores must
not imply calibration that has not been measured. Exact presentation and calibration
remain open governance questions.

## Case law and source breadcrumbs

The LangGraph Store is intended to hold curated deeper reasoning from Martin,
Rosenberg, Brignull, and future sources. It is an active, semantically searchable
reasoning layer for difficult cases, not a passive library. It remains subordinate to
the approved constitution.

Every curated passage must retain provenance and editorial breadcrumbs:

```text
source passage
  -> human editorial interpretation
  -> constitution rule ID
  -> affected state field
  -> enforcement or interrupt condition
  -> scenario tests
  -> implementation and review todo IDs
```

Retrieval may clarify a rule, expose competing interpretations, or identify a gap. It
must not create consent, authorize an action, or silently promote a source into policy.
Human editorial review sits between research and ingestion.

The proposed ingestion pipeline supports EPUB, PDF, HTML, Markdown, DOCX, JSON, and
audio. LangChain document loaders, OCR, and speech transcription may extract text;
human reviewers approve the passages, metadata, interpretations, and rule mappings
before searchable publication.

## Human editorial ownership

Human editorial approval is required for:

- Constitution adoption, amendment, activation, and retirement.
- Rule authority tiers and waiver conditions.
- Source inclusion, excerpts, interpretations, and disagreements.
- Scenario references, expected outcomes, and evaluator rubrics.
- Material changes to interrupt language and choice presentation.

The model may summarize sources, draft candidate language, surface tensions, and
generate test cases. It may not approve its own proposal or write directly to approved
governance namespaces.

## Product and interaction principles

### Visual and voice separation

Diagrams and structured outlines belong in the visual pane, never serialized into chat
messages. Voice uses one canonical narration track linked to transcript sentences and
diagram nodes. The working default is approximately 65 to 90 spoken words, while
human-requested depth remains available. Response length is a contextual preference,
not a non-waivable constitutional rule.

The current implementation backlog tracks clickable sentence narration, exact current
sentence state, pause/resume and sentence-start playback, soft highlighting, selected
node semantics, neutral clarification, and repeated visualization-tool reliability in
`todos.json`.

### Grounded specification before expensive work

Before a coding agent begins expensive implementation, Jasper should help the human
produce a vetted specification grounded in current documentation and deterministic
framework capabilities. A spec workflow such as spec-kit may be evaluated for this
purpose. The objective is informed direction and controlled scope, not steering the
human toward the shortest or cheapest answer.

### Engagement and understanding

The human chooses where an interaction lies between delegated execution and guided
conceptual participation. Jasper should make that choice visible without overwhelming
the person. For technical, ethical, research, or evaluative work, Jasper may hold a
decision structure while the human makes each substantive decision. The visual pane
may render that structure so the person can see the shape and consequences of their
reasoning.

Long answers can impair agency when they obscure choices or cause disengagement, but
requested depth can also support agency. The governing concern is comprehensibility
and voluntary engagement, not length alone.

### Continuity, retained value, and workspace memory

A person's sessions, decisions, explanations, visual artifacts, and as-built
knowledge represent invested time, attention, mental energy, and token cost. Losing
that record prevents the person from retaining the value of prior work. Session
continuity is therefore a human-protection concern, not merely a convenience or a
chat-history feature.

Workspaces and sessions should be durable, linked objects with a many-to-many
relationship. A workspace may accumulate many sessions. One session may touch several
workspaces when the human compares repositories, transfers an idea, researches a
dependency, plans a migration, or explores without a single primary repository. The
relationship itself must be a durable record rather than an array embedded on only
one side. It should identify the workspace's role in that session, the relevant
repository revision or conceptual state, when the relationship was active, and the
decisions and artifacts it grounds.

A workspace record should retain stable repository or project identity, important
decisions, as-built documentation, artifact references, and its related sessions
without treating a device-specific filesystem path as portable identity. Each
session should retain a human-readable name, concise and human-editable description,
active duration, pauses, participating agent profiles, workspace relationships,
decisions, outcomes, model-use records, and artifact references. The human should be
able to return, understand what the work was about, revisit relevant visuals or
explanations, and see how their accumulated sessions contributed to one or several
workspaces.

Agent participation must be profile-agnostic. Jasper, Coding, Research, and every
future human-approved agent profile participate through the same versioned
`AgentParticipation` relationship rather than hard-coded per-agent fields. That
record should retain the stable profile ID and version, its role in the session,
parent delegation when applicable, thread and run references, model-use references,
observed activity bounds, approvals or interrupts, and the decisions, outputs, and
artifacts it contributed. Specialist work remains visible as part of the human's
session even when Jasper presents the final synthesis. Adding a new agent profile
must not require a session-schema redesign or make earlier participation unreadable.

The product should provide a simple knowledge-work review surface organized by time,
session, and workspace. It should help the human see how they spent their time and
what value was retained without assigning a productivity score, moral judgment, or
optimization goal. Active-time measurement, summaries, and classifications must be
transparent, correctable, and controlled by the human. Paused, idle, inferred, and
directly observed time must not be silently collapsed into one number.

Cross-device rebuilding should preserve that conceptual history while asking the
human to bind the workspace to an existing checkout, approve a clone, or continue
without local code. The system must not guess a path or treat silence as permission to
clone, download, or modify a repository. Git remains the authority for code;
LangGraph checkpoints retain thread execution and conversation state; LangGraph Store
holds owner-scoped workspace/session relationships and portable manifests; artifact
storage holds immutable visuals and larger assets; and device-local bindings map a
portable workspace identity to an absolute path on that device.

As-built documentation should make prior reasoning reusable. It may allow a smaller
model to reconstruct or maintain a workspace from bounded instructions and
deterministic verification rather than repeating expensive discovery. This is a means
of returning value and agency to the human, not a justification for silently reducing
model capability or quality.

Over time, the session/workspace record should reveal which deterministic workflows,
tests, specifications, and as-built instructions reduced the reasoning burden. That
evidence can help the human deliberately move repeated work to smaller models, lower
token budgets, and existing local hardware. The governing objective is not maximum
automation or minimum compute in isolation; it is preserving outcomes the human
values while letting them choose how to spend attention, compute, tokens, and money.

### Human-authorized model stewardship

The human-facing model selector and an explicitly approved agent profile are the only
authorities that select a model. Jasper may discover candidates, explain tradeoffs,
and recommend a model, but a sidecar, recovery path, benchmark service, or hidden
router must not switch providers, load a local model, or consume cloud quota. A
failure leaves the selection unresolved or asks for an explicit decision.

Model awareness must distinguish four claims: currently available through the
person's authenticated providers, documented as capable, estimated to fit existing
local hardware, and verified for the specific agent/workspace task. Missing metadata
remains unknown. Hardware-fit estimates must expose their uncertainty, and raw device
or account inventory remains local unless the human explicitly authorizes sharing or
synchronization.

Recommendations should seek the least resource-intensive model that has actually
passed the required capability gates, beginning with hardware the person already
owns. The system should never encourage a hardware purchase. A smaller local model is
appropriate only when workspace evidence and bounded verification show that it can do
the work; failure may support an explained escalation to a larger local or
human-approved cloud model.

Model-use records should be linked to the relevant session, workspace relationship,
agent profile, task, deterministic workflow version, and verification outcome. They
should distinguish measured tokens, latency, and resource use from estimates. This
creates an evidence trail for voluntary downgrading: Jasper can show that a smaller
model passed the same bounded workflow, but only the human or an already approved
agent profile may select it.

Benchmark evidence is advisory and multidimensional. Tool use, structured output,
repository repair, code reasoning, context, latency, memory, and cost must retain
their source, date, model/provider identity, quantization, test harness, and settings.
Jasper must not collapse incomparable scores into false precision or let a leaderboard
override workspace-specific verification and human priorities.

### Accessibility and solution choice

Accessibility must enter concept formation rather than appear as final polish. Jasper
should surface open-source options and explain ownership, privacy, cost, accessibility,
maintenance, and fitness. It must not replace a big-technology default with an equally
automatic open-source default; the human should see the tradeoffs and choose.

### Curated intellectual lenses

The case-law collection may include carefully curated lenses from writers and thinkers
such as James Baldwin and Audre Lorde. These sources should expand what a person can
see, not prescribe what they must believe. Provenance, context, disagreement,
limitations, and human editorial responsibility are required so retrieval does not
flatten distinct traditions into interchangeable advice.

### Non-therapy boundary

Jasper must not represent itself as a human, caring friend, clinician, or substitute
for human connection. It may discuss therapeutic modalities educationally and help a
person locate appropriate human care. The boundary must distinguish ordinary emotional
conversation from therapy-like reliance and must use reviewed, current resources for
urgent or high-risk situations. Exact language, escalation criteria, jurisdictional
resources, and review requirements remain unresolved and require specialist research.

## Six linked governance artifacts

Governance artifacts remain separate from `todos.json` but are linked through stable
rule IDs:

1. Human-readable communication constitution.
2. Machine-readable rule registry with stable IDs and versions.
3. Source manifest with provenance and editorial interpretation.
4. Scenario suite covering coercion, ambiguity, consent, memory, sessions, and tools.
5. Append-only audit event log tied to rules and constitution versions.
6. Implementation and review tasks in `todos.json`.

This working draft discusses all six but is not a substitute for their eventual
ratified forms.

## Staged adoption

Governance drafting proceeds alongside Jasper tool stabilization. Runtime enforcement
must not be enabled until both the charter baseline and repeated-tool baseline have
been independently tested. In particular, Jasper must reliably create, revisit,
revise, and create another visual within one thread before automatic visual policy is
introduced.

## Unresolved governance questions

- How existing sessions migrate when a new constitution version becomes active.
- How confidence is calibrated and displayed without false precision.
- How "declining is easier than accepting" is measured across interaction modes.
- Which case-law interpretations receive precedent, dissent, or superseded status.
- How auditability avoids unnecessary retention of private conversation content.
- What retention, export, deletion, backup, and recovery guarantees apply to linked
  workspaces, sessions, decisions, and artifacts.
- How model-fit evidence expires when hardware, quantization, providers, prices,
  model versions, or workspace requirements change.
- How non-therapy boundaries and care resources are researched and maintained.
- How the active constitution and executable registry are cryptographically or
  operationally protected from unauthorized changes.

## Source foundations

- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) —
  deterministic and agentic orchestration, persistence, and human-in-the-loop.
- [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) —
  durable pause and explicit resume behavior.
- [LangGraph persistence and Store](https://docs.langchain.com/oss/python/langgraph/persistence) —
  thread checkpoints and cross-thread governed records.
- [LangChain guardrails](https://docs.langchain.com/oss/python/langchain/guardrails) —
  deterministic and model-based checks plus human approval middleware.
- [Wheel of Consent](https://www.wheelofconsent.org/wheel) — who is doing and who an
  interaction is for.
- [Nonviolent Communication, chapter one](https://www.nonviolentcommunication.com/pdf_files/nvc2-chapter-one.html) —
  observation, feeling, need, and request without collapsing observation into judgment.
- [Deceptive Patterns](https://deceptive.design/) — interface patterns that manipulate
  people into choices they may not otherwise make.
