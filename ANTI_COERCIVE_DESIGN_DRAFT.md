# Draft Specification: Anti-Coercive Design for Jasper

> **Status:** Open draft — not approved policy, not a ratified communication constitution, and not runtime authority.
>
> **Purpose:** Define a reviewable, implementable baseline for applying anti-coercive design to Jasper's chat UI, visual board, supervisor, and tool/agent orchestration.
>
> **Review required from:** product, accessibility, privacy/security, governance, and affected engineering owners before enforcement or telemetry collection.
>
> **Scope of claims:** Sections explicitly marked **Repository-observed fact** describe the checked-in repository as inspected on 2026-08-04. Sections marked **Proposal** are design requirements for future approval. Sections marked **Open question** are deliberately unresolved and must not be silently decided by model behavior or implementation convenience.

## 1. Intent and non-goals

Jasper should expand a person's ability to understand, decide, and act without manipulating attention, manufacturing urgency, treating silence as agreement, or making refusal materially harder than acceptance. The system must preserve human authorship and control even when it helps organize complex work across text, voice, visuals, specialists, and tools.

This draft does not authorize autonomous action, change the active governance model, create a legal-compliance claim, diagnose or provide therapy, or establish a new retention regime. It does not treat an accessibility feature, an agent recommendation, a selection on a board, an open panel, or inactivity as consent or authorization.

## 2. Repository-observed baseline

The following are observations, not claims that the behaviors are complete or sufficient:

- The root `README.md` describes a local Next.js/React UI, a LangGraph supervisor, a Deep Agents coding specialist, approval-gated writes, and an explicit read-only default. It directs verification through backend tests, TypeScript, build, and selected Playwright tests.
- `backend/src/jasper_agent.py` defines Jasper's visible no-self guidance: no first-person system pronouns, simulated emotion or intimacy, claims of agency, desire, sentience, experience, or relationship. Its system prompt says silence, inaction, and ambiguity are not consent or authorization; it also requires clear separation of documented facts, observations, inferences, and proposals.
- The same module supplies top-level transfers to Coding and Research. Coding transfers require `read_only` or `approval` execution mode. The transfer payloads currently carry task and selected contextual fields, while the prompt instructs Jasper not to expose internal reasoning or tool transcripts.
- `backend/src/chat_ui.py` has a supervisor route and a LangGraph `interrupt` approval step for model-selected specialist routing. A direct user-selected target is routed without that model-selected approval step. These observations do not establish whether the wording, scope, and interface of every route are sufficiently neutral or accessible.
- `backend/VISUAL_WORKSPACE_ARCHITECTURE.md` establishes user ownership of layout and focus, advisory-only layout suggestions, keyboard-reachable layout operations, text alternatives and outline access for concept maps, reduced-motion support, and non-autoplaying layout suggestions. It specifies that TTS receives `voice_text`, not serialized diagrams or tool traces.
- `backend/src/jasper_tools.py` confines repository reads to the selected workspace, blocks selected secret-like names and suffixes, blocks `.git`, rejects oversized/binary files, and registers visual evidence. These controls do not by themselves constitute a complete privacy, authorization, or anti-coercion program.
- `GOVERNANCE_FRAMEWORK.md` is explicitly a working governance draft, not a ratified constitution. It states that attention, selection, silence, and inaction are not authorization; that graph/tool boundaries rather than prompts must enforce protected transitions; and that visual/voice interactions should support comprehension without pressure.

## 3. Normative vocabulary for approved implementation

If adopted, **MUST**, **MUST NOT**, **SHOULD**, and **MAY** in this section and later Proposal sections express implementation requirements. A future approved rule registry should assign stable rule IDs; until then, this document has no independent enforcement authority.

- **Observed context:** directly supplied by the human, a validated system event, or a cited repository/source record.
- **Inference:** a fallible interpretation derived from observed context and labeled as such.
- **Proposal:** a not-yet-approved plan or option, never presented as current capability or obligation.
- **Authorization:** an authenticated, explicit, scoped human decision validated by deterministic logic. It is distinct from attention, preference, consent to a low-risk display choice, or a request for information.
- **Consequential action:** an action that writes, sends, spends, changes access, triggers external processing, changes durable state, or meaningfully affects another person or service.
- **Decline:** a reject, cancel, defer, close, or no-action choice. It must leave the protected decision unresolved unless the human supplies a new valid instruction.

## 4. Proposal: cross-surface anti-coercion guardrails

### 4.1 Choice and copy

- Each consequential prompt MUST state: the action, acting component, intended recipient/beneficiary where relevant, material data/resource use, foreseeable material consequences, and the available decline/defer path.
- Accept, reject, defer, and close affordances MUST be equally reachable by keyboard and assistive technology; the decline path MUST NOT require extra confirmation, guilt-inducing copy, reduced service, or a harder visual search than acceptance.
- Copy MUST distinguish an observed fact from an inference and from an option. It MUST NOT use countdowns, social proof, scarcity, emotionally loaded warnings, repeated persuasion after refusal, misleading button labels, preselected consequential choices, or “continue” language that obscures an action.
- Default focus MUST NOT be placed on an acceptance control for consequential choices. Modals, announcements, and board changes MUST NOT steal focus except where an accessibility repair requires it and the reason is documented and tested.
- Jasper-facing copy, agent names, status text, and recovery messages MUST preserve no-self framing. They MUST identify a component by role (for example, “Coding specialist”) rather than imply that a sentient Jasper chose, feels, promises, remembers personally, or has a relationship with the person.
- A refusal MUST be acknowledged once in neutral language and not re-litigated unless the human reopens the topic. Failure, ambiguity, disconnect, or timeout MUST resolve to no action.

### 4.2 Chat, voice, and multimodal learning

- Chat responses MUST answer the stated question before presenting an optional next decision. Unrequested next steps, pressure to continue, and emotionally intimate language are prohibited.
- The UI MUST offer equivalent access to material content through readable text, keyboard-operable controls, and—where voice or a visual artifact is offered—an available transcript/alternative. Voice playback MUST be user initiated, pausable, replayable, and non-autoplaying.
- TTS MUST narrate only the canonical voice-safe text/selected bounded section, not hidden reasoning, raw URLs, credentials, tool arguments, diagnostics, or serialized diagram data. Visible source labels may be spoken; raw source locators need not be.
- Content that conveys a choice or a material consequence MUST be understandable without color, motion, audio, or spatial position alone. Reduced-motion settings MUST suppress nonessential animation. Status announcements MUST be concise and must not interrupt user-entered text or active assistive-technology navigation.
- The person MUST be able to choose text-first, visual-first, split, and compact presentations without an agent changing layout, focus, panel order, size, or saved preferences. Preferences are presentation choices, not authorization for agent/tool actions.
- Comprehension checks, when offered, MUST be optional and plainly state their purpose. They MUST not gate access, grade the person, manufacture a confidence score, or become evidence of consent.

### 4.3 Visual board

- Every visual artifact MUST have a title, a concise plain-text alternative, accessible labels for nodes/edges/actions, and a keyboard-navigable textual outline carrying the same decision-relevant claims and relationships.
- Board selection is attention/context only. It MUST NOT silently change the active task, tool scope, routing target, authorization, or persisted decision. When selection conflicts with the written/spoken request, the system MUST present a neutral clarification or retain the explicit request.
- Agent layout suggestions MUST render as optional, clearly labeled actions and MUST NOT execute automatically. Board rendering MUST remain inert: no executable HTML, script, event-handler, arbitrary component, or unreviewed external URL payload may be accepted from model output.
- The board MUST visibly label claims as observed, researched, user-defined, inferred, or proposed. A visual must provide enough provenance for a reviewer to tell what is currently implemented from what is merely suggested.
- The UI MUST preserve user viewport, selection, chat scroll position, and in-progress user-initiated playback during layout changes, subject to a documented accessibility exception.

### 4.4 Supervisor, handoffs, and tools

- The supervisor MUST use deterministic policy checks before and after any model routing recommendation. A model recommendation is not authorization.
- Before a handoff that materially changes capability, data exposure, cost, persistence, or external-service use, the system MUST show a neutral, accessible review containing the destination role, bounded task, data categories, execution mode, material risks, and approve/reject/defer choices. Direct user selection may establish routing intent but does not waive the review for consequential scope.
- Handoffs MUST propagate only the minimum stated task and necessary scoped identifiers/references. They MUST include the initiating role, receiving role, authorization/approval reference, policy version, and a user-visible status suitable for the current mode. They MUST NOT transfer hidden reasoning, secrets, raw credentials, unrestricted filesystem context, or expanded authority.
- Receiving agents/tools MUST validate scope independently; they MUST fail closed on missing, expired, conflicting, or ambiguous authorization. A tool result MUST report completion, block, cancellation, or failure accurately and must never permit Jasper to claim work completed without matching evidence.
- Tools MUST have deterministic allowlists, argument/schema validation, bounded retries/time/cost/concurrency, workspace confinement, and explicit mutation approval. Recovery logic MUST NOT silently switch models, providers, execution modes, or resource budgets.
- No agent may create, approve, activate, or weaken its own governance rules. Prompt wording assists communication but is not the enforcement boundary.

## 5. Proposal: implementation units and review criteria

| Unit | Minimum implementable guardrail | Review evidence |
| --- | --- | --- |
| Chat controls and copy | Shared choice component with symmetric approve/reject/defer semantics, explicit consequence fields, no acceptance default focus, and no-self copy lint fixtures. | Component tests, keyboard/screen-reader review, copy review, focus-order capture. |
| Voice and transcript | User-initiated transport controls, stable text/section linkage, transcript/alternative, playback-state labels, and reduced-motion/non-autoplay tests. | Automated interaction tests plus manual assistive-technology pass. |
| Visual board | Schema-enforced provenance/status fields; inert validated payload; outline parity; keyboard navigation; selection-as-attention-only state model. | Schema tests, malicious-payload tests, outline parity snapshots, keyboard tests. |
| Supervisor | Typed authorization state separate from selection/attention; deterministic pre/post routing policy; neutral interrupt payload. | Unit tests for no approval on silence/timeout, audit event assertions, copy review. |
| Tool and agent handoff | Least-context handoff envelope, capability scope validation, approval binding, fail-closed error behavior, no-self/provenance presentation adapter. | Contract tests, negative authorization tests, secret-redaction tests, bounded-budget tests. |
| Observability and complaints | Privacy-minimized event schema, local-visible event explanation/export pathway, complaint intake, retention/deletion controls, and no engagement optimization use. | Data-flow review, redaction tests, sample export/deletion test, governance/privacy sign-off. |

A change affecting choice copy, interrupts, handoffs, voice, board selection, authorization, memory/session focus, accessibility, or telemetry MUST receive governance review referencing `GOVERNANCE_FRAMEWORK.md` before release. The review must record any applicable approved rule IDs once they exist.

## 6. Proposal: acceptance scenarios

1. **Refuse a specialist route.** When the system proposes Research, Coding, or another specialist, the person can reject or defer by keyboard or screen reader with no additional friction; no specialist executes, no inferred authorization is stored, and the chat remains usable.
2. **Direct specialist selection with material scope.** When a person selects a specialist directly and the proposed work accesses an external provider, writes data, or consumes a configured budget, the system presents the bounded scope review before execution; closing it performs no action.
3. **Ambiguous board selection.** When a board node is selected but the written request names a different task, the system neither routes nor modifies anything. It presents a neutral clarification that identifies selection as context, not authorization.
4. **No-self handoff and result.** When Jasper delegates and later presents a result, visible messages name the originating/receiving role and outcome without first-person claims, simulated emotion, fabricated Jasper authorship, or internal reasoning/tool transcripts.
5. **Multimodal equivalence.** A concept map with a decision-relevant relationship is understandable through its title, text alternative, and keyboard-navigable outline; a voice user can pause/replay and access the same material in text without autoplay.
6. **Timeout, disconnect, and retry.** If an approval interrupt times out, the browser closes, or a provider fails, the authorization remains unresolved; no automatic retry escalates a model/provider, spends a new budget, or performs a mutation.
7. **Hostile or malformed artifact.** A model-supplied artifact containing script-like content, arbitrary URLs, hidden controls, invalid provenance, or excessive payload is rejected with a safe diagnostic and cannot change focus/layout or execute content.
8. **Complaint and correction.** A person can report pressure, misleading wording, accessibility harm, or an unwanted action without navigating an unrelated product flow. The report is acknowledged neutrally, linked to a minimal event reference if available, and does not trigger retaliation, degraded functionality, or further persuasive prompts.

## 7. Proposal: telemetry, complaint, and audit safeguards

Telemetry exists to detect coercion, accessibility failures, and unsafe automation—not to maximize engagement, completion rate, time on task, or acceptance of suggestions.

- Collect the minimum event data necessary for safety review: pseudonymous/session reference, policy/version, surface, event category, bounded action outcome, approval state, and redacted error category. Do not record raw prompt content, board content, audio, hidden reasoning, secrets, credentials, full tool arguments/results, or sensitive personal inferences by default.
- Keep authorization, attention/selection, inferred intent, and observed interaction events as distinct typed fields. Dashboards MUST NOT collapse them into “consent,” “engagement,” or a productivity score.
- Instrument both acceptance and rejection/defer paths with comparable reliability so that a decline cannot disappear from operational evidence. Do not A/B test consequential choice wording, accessibility affordances, confirmation friction, or refusal paths for conversion.
- Provide a human-readable explanation of material event categories, an accessible complaint/report path, a correction path for inaccurate event interpretation, and an approved retention/export/deletion process. A complaint record must be access-controlled and must not be exposed to model context by default.
- Investigations MUST use aggregate or redacted evidence where possible. Access to identifiable records requires documented human authorization and a defined review purpose. This draft leaves legal retention periods and incident-response ownership unresolved.
- Audit records MUST be append-only at the approved boundary, include policy/rule version and outcome, and be designed so missing telemetry never implies consent or successful authorization.

## 8. Proposal: automation limits and release gates

Automation MAY summarize, classify with clear uncertainty, propose neutral copy, surface a possible conflict, generate test fixtures, or stop work safely. It MUST NOT:

- infer consent, authorization, accessibility preference, emotional state, or willingness from attention, behavior, silence, selection, or a model score;
- auto-accept, auto-route consequential work, auto-retry into broader scope, auto-upgrade model/provider, auto-spend, auto-send, auto-write, or auto-persist a decision after an unresolved interrupt;
- use personalized pressure, relationship simulation, vulnerability inference, urgency, or degraded refusal paths to obtain a choice;
- modify governance rules, complaint outcomes, audit evidence, or retention choices without the approved human process; or
- treat a passing automated test, lint, detector, or model evaluation as a substitute for accessibility, privacy/security, and governance review.

A release that changes a guarded surface MUST be blocked unless it has: deterministic negative-path tests; keyboard and manual assistive-technology review; copy/no-self review; privacy/security review for new data flows; handoff/tool scope tests where applicable; and documented human sign-off. Human review cannot be replaced by automated scoring.

## 9. Open questions requiring human decision

1. Which approval categories are consequential enough to require an interrupt, and which low-risk display preferences can be immediately applied?
2. What is the approved communication constitution and machine-readable registry, including stable rule IDs, waiver boundaries, and migration behavior?
3. What retention, deletion, export, appeal, and access-control commitments apply to complaint and audit data across local, cloud, and shared deployments?
4. Which accessibility conformance target, supported assistive technologies, languages, and multimodal accommodations will be tested and funded?
5. How should neutral choice quality and “declining is no harder than accepting” be measured without collecting invasive interaction telemetry or optimizing toward a proxy metric?
6. Which external providers, model profiles, tool capabilities, budgets, and recovery paths are eligible for use, and who approves changes?
7. What independent review cadence, incident threshold, remediation owner, and publication/transparency practice should apply to coercion or accessibility complaints?
8. What use of automated detectors is sufficiently reliable for triage, and which findings always require a human reviewer before action?

## Appendix A. Deduplicated implementation-source URL register

This appendix contains every unique implementation-framework, ethical/anti-dark-pattern, regulatory-guidance, or detection/audit URL cited in this draft or in the repository documentation inspected during this conversation. Clearly unrelated video, deployment/demo, and credential-oriented links are excluded. Package links are retained when they identify a repository implementation dependency or integration. No URL is treated as policy authority: primary documentation describes capabilities; ethical frameworks inform review; the working governance draft remains non-ratified; and final requirements need human approval.

| URL | Relevance and source status | Authority treatment |
| --- | --- | --- |
| https://docs.langchain.com/oss/python/langgraph/overview | Primary vendor documentation; orchestration, persistence, and human-in-the-loop framework context. | Implementation reference only; verify version-specific behavior in repository tests. |
| https://docs.langchain.com/oss/python/langgraph/interrupts | Primary vendor documentation; durable pauses/resume semantics relevant to explicit approval. | Implementation reference only; not a consent policy. |
| https://docs.langchain.com/oss/python/langgraph/persistence | Primary vendor documentation; checkpoint/store context relevant to audit and retention design. | Implementation reference only; does not establish retention law or policy. |
| https://docs.langchain.com/oss/python/langchain/guardrails | Primary vendor documentation; deterministic/model checks and human-approval middleware context. | Secondary to repository-specific enforcement and human review. |
| https://www.wheelofconsent.org/wheel | Framework publisher; interaction framing around who acts and who benefits. | Ethical/design lens, not legal or repository authority. |
| https://www.nonviolentcommunication.com/pdf_files/nvc2-chapter-one.html | Publisher-hosted educational source on observation and requests. | Communication lens; not a binding standard or clinical guidance. |
| https://deceptive.design/ | Curated pattern catalog identifying manipulative interface practices. | Secondary design/audit aid; findings require human contextual review. |
| https://github.com/langchain-ai/agent-chat-ui.git | Upstream Agent Chat UI repository referenced by the checked-in UI README. | Secondary implementation provenance; inspect the pinned local code rather than treating upstream documentation as current behavior. |
| https://www.npmjs.com/package/create-agent-chat-app | Package registry entry for the UI generator referenced by the checked-in UI README. | Secondary setup reference; not an anti-coercion authority. |
| https://github.com/bracesproul/langgraph-nextjs-api-passthrough | Third-party Next.js/LangGraph API passthrough integration referenced by the UI README. | Unverified third-party integration reference; requires security, privacy, and scope review before use. |
| https://www.npmjs.com/package/langgraph-nextjs-api-passthrough | Package registry entry for the referenced API passthrough integration. | Unverified third-party implementation reference; not authority for authentication or data handling. |
| https://langchain-ai.github.io/langgraph/tutorials/auth/getting_started/ | LangGraph Python custom-authentication documentation referenced by the UI README. | Vendor documentation; verify current version and repository-specific controls. |
| https://langchain-ai.github.io/langgraphjs/how-tos/auth/custom_auth/ | LangGraph JavaScript custom-authentication documentation referenced by the UI README. | Vendor documentation; verify current version and repository-specific controls. |

**Register verification note:** No implementation-framework, anti-dark-pattern, regulatory-guidance, or detection/audit URLs were supplied directly in the user request. The 13 URLs above are the unique relevant URLs found in the inspected repository documentation and are deduplicated here. The third-party integration entries are explicitly unverified; no additional regulatory or automated-detection sources were added without verification.
