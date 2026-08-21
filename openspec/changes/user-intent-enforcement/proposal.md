## Why

Long-running development can drift from what a user meant, especially when exploratory conversation later becomes scheduled, multi-agent work. The change proposes a local, reviewable intent record and deterministic protection boundary without confusing intent verification with Jasper’s existing LangGraph Supervisor or frontier-model execution.

## User-defined governance/philosophical principles (not independently verified facts)

The following principles are supplied by the user as governance and ontology concepts for consideration by a future verifier and policy layer. They are not presented as independently verified social-science findings, implementation facts, legal requirements, or settled project policy:

- Human-to-human resonance and shared story can increase collective problem-solving capacity.
- An artificial agent must not present simulated human resonance, empathy, community, or relationship as genuine. Its non-human identity and system boundaries must remain transparent.
- Anthropomorphic or relationally deceptive communication can blur intent and create coercive risk. Future review should examine this as a governance concern rather than treating relational language as evidence of consent, authorization, or genuine relationship.
- Intent protection should reduce exhaustion, unnecessary conversational expansion, wasted time, and unnecessary monetary or token costs, while not optimizing away clarification that is necessary for informed human control.
- The system should preserve human agency, clear system boundaries, transparent non-human identity, intent clarity, and provenance/story continuity.

These concepts should be considered when defining ontology terms, provenance fields, verifier evidence, clarification behavior, resource accounting, and policy inputs. OPA/Rego requires explicit structured facts and deterministic rules; it cannot infer the philosophical claims above by itself. A future adapter must therefore represent only reviewable, sourced, user-confirmed, or otherwise explicitly classified facts (with uncertainty and provenance) rather than smuggling these principles into policy as inferred truth.

The supplied relational-culture framing is user-defined and requires future operationalization and evidence review. It does not independently establish requirements or authorize runtime behavior. Relevant repository references are [`GOVERNANCE_FRAMEWORK.md`](../../../GOVERNANCE_FRAMEWORK.md), [`ANTI_COERCIVE_DESIGN_DRAFT.md`](../../../ANTI_COERCIVE_DESIGN_DRAFT.md), [`anatomy-of-a-session`](../anatomy-of-a-session/proposal.md), and [`research-agent-promotion`](../research-agent-promotion/proposal.md). The linked OpenSpec proposals remain planning artifacts and do not supersede this proposal's separation from Jasper's Supervisor or its no-tasks-yet scope.

**Government-document search limitation:** Within the selected repository, no suitable government-issued document was located that could be linked as a verified source for human agency, coercion, relational culture, anthropomorphic or deceptive agent behavior, resource costs, or intent protection. No government source is invented or treated as evidence here; a future evidence review may add a stable primary reference if one is intentionally introduced into the repository.

## What Changes

- **Separate the protection plane from Jasper.** The intent-verification/protection system is a completely separate subsystem from Jasper’s existing LangGraph Supervisor and its frontier models. Jasper remains the Supervisor node: it can strategize with the user and invoke the Librarian or Coder. The verifier is not a second Supervisor, and Jasper is not the authority or intermediary for intent confirmation.
- **Define complementary responsibilities.** Plane handles prioritization and planning of development intent; Temporal dispatches planned work to agents and sub-agents; OpenSpec records proposed changes and later validation artifacts; OPA protects user intent at execution boundaries. These systems must exchange traceable references rather than silently become sources of authority for one another.
- **Support emergent intent before OpenSpec.** During an exploratory or creative session with no OpenSpec change yet, a local intent-verification model harvests the user’s evolving intent from the conversation, states its interpretation directly to the user, and accepts easy correction or editing by voice or text. The resulting intent may be provisional until the user confirms it, and must remain usable without routing confirmation through Jasper.
- **Version intent and adapt it to OPA.** Confirmed and provisional intent are versioned records containing objective, scope, constraints, prohibitions, authorization/consent state, ambiguity, provenance, and revision history. An adapter converts the selected version into structured OPA input. Stable Rego policy logic evaluates intent data and execution context; the design must not imply that Rego is generated for each user action.
- **Protect all coder actions.** Enforcement applies to Coder actions in both emergent sessions and scheduled/spec-driven work, at tool, activity, task, and workflow boundaries. Decisions must minimize routine human approval overhead while clearly supporting `allow`, `constrain`, `pause`, `deny`, `stop`, `rollback`, and intent-shift clarification, with fail-closed behavior for protected mutations.
- **Make the story traceable end to end.** Preserve breadcrumbs from creative session(s) through harvested intent versions, confirmations/edits, OpenSpec change(s), Plane planning/prioritization, Temporal dispatch/run(s), agent/sub-agent work, and verification/outcomes. A user must be able to follow one or multiple originating exploratory sessions and understand elapsed time, effort, tools and models used, decisions, interruptions, rework, and whether the system was supportive or obstructive to the creative process.
- **Record auditable evidence without granting it authority.** Retrieval, repository inspection, impact analysis, and prior examples may inform interpretation or policy input but cannot confirm intent, authorize an action, or override OPA. Fine-tuning, if used, remains limited to narrow intent/drift classification and evaluation.
- **Preserve human control and communication boundaries.** Support correction, withdrawal, consent, authorization, attention, and accessibility across voice and text. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## Capabilities

### New Capabilities

- `user-intent-enforcement`: Defines versioned intent harvesting and confirmation, the separate protection boundary, OPA input adaptation and stable policy evaluation, enforcement outcomes for emergent and scheduled coder work, and end-to-end provenance/traceability.

### Modified Capabilities

- None. **Observed repository fact:** the current `openspec/specs/` contains no existing capability specification to modify. Jasper, Plane, Temporal, and OpenSpec are therefore described here as proposed architectural boundaries, not as changes to existing requirements.

## Impact

### Observed repository facts

- The selected change currently contains only `proposal.md` and `.openspec.yaml`; no specs, design, or tasks artifacts exist yet.
- The existing proposal explicitly describes this as planning-only and identifies `GOVERNANCE_FRAMEWORK.md` as a reference. This revision preserves that scope.

### Proposed design requirements

- The proposal requires provenance records for each intent version and enforcement decision, including timestamps, stable links/IDs, parent session and OpenSpec/Plane/Temporal references, confirmation/edit history, tool/model/runtime records, policy-bundle and adapter versions, and observed inputs/outcomes.
- It requires effort and duration accounting across conversation, planning, waiting/interruptions, execution, review, rollback, and rework, with clear distinctions between measured observations and estimates.
- It requires user-facing traceability that exposes the breadcrumb story, decision explanations, interruptions, changed intent, tool/model use, outcomes, and supportive-versus-obstructive experience without exposing secrets or treating inferred data as confirmed intent.
- Future implementation may affect the local verifier runtime, direct user confirmation UX, intent persistence/versioning, OPA adapters and policy bundles, Coder/tool/workflow boundaries, Temporal activities, Plane synchronization, OpenSpec linkage, audit/provenance storage, and verification/observability. Exact schemas, retention, privacy, confirmation expiry, policy rollout, replay semantics, and hardware constraints remain for later artifacts.
- This request authorizes only this proposal revision. It does not authorize implementation code, task lists, design artifacts, delta specs, migrations, or deployment changes; tasks are intentionally not being written yet.

## Areas for Further Inquiry

The recent Librarian report is treated as a set of research leads, not as verified evidence or settled requirements. The following topics should be investigated independently before they are used to justify implementation or policy decisions:

- **Stateful trajectory monitoring and intent drift.** Examine whether monitoring an evolving action/conversation trajectory can detect drift early enough to protect intent without turning inferred changes into authorization or imposing excessive approval overhead.
- **DeepContext.** Investigate the report's F1 and latency claims through independent evaluation. Those reported metrics require validation and would not, by themselves, prove protection against coding-intent violations or drift.
- **Agent-Sentry and provenance boundaries.** Explore whether Agent-Sentry-style ideas can provide useful provenance or boundary signals. Any metrics reported for Agent-Sentry remain unverified until reproduced under relevant coding-agent conditions.
- **VideoAgent and AgentOrchestra.** Keep these systems separate from direct evidence for coding-intent enforcement; at most, assess them as non-direct analogies or research context rather than proof that the proposed protection boundary works.
- **Granite Guardian and Llama Prompt Guard 2.** Verify any comparison claims, including applicability, accuracy, latency, context handling, and threat-model fit, before drawing conclusions about their suitability for this proposal.
- **LangGraph persistence and interrupt/resume.** Compare LangGraph's documented persistence and interrupt/resume capabilities with the proposal's needs for durable state and human control. Do not infer that LangGraph provides a built-in intent-alignment score; the absence of such a documented score remains a design gap to address separately.
- **Compact stateful enforcement components.** Assess compact stateful detectors, action ledgers, provenance links, deterministic allowlists and policy checks, and selective escalation as potentially complementary mechanisms. They should preserve the local verifier's separation from the Jasper Supervisor and should not replace explicit user confirmation where authorization is required.
- **Narrow classification research.** Consider parameter-efficient fine-tuning (PEFT), Low-Rank Adaptation (LoRA), and Quantized Low-Rank Adaptation (QLoRA) only as research areas for narrow intent/drift classifications, with independent evaluation and no assumption that tuning establishes authority or alignment.
- **Benchmarking.** Define explicit comparative benchmarks for accuracy, latency, context size, false positives, and the ability to keep pace with frontier coding agents. Results should distinguish measured observations from estimates and should test emergent and planned work, provenance from creative sessions through OpenSpec/Plane/Temporal/execution, and the stable OPA/Rego policy boundary with intent supplied as input.

### Semantic models and ontologies as candidate memory/context components

This is proposed inquiry into possible components of the memory/context layer, not an established repository implementation, an adopted architecture, or a universal standard. A future design may compare the following complementary structures:

- **Semantic model.** A semantic model could represent structured, typed meaning for entities, attributes, facts, dimensions, metrics, and provenance. This may support both exact views (for example, which constraint applies to which artifact) and analytical views (for example, effort, duration, drift, or outcome by session, agent, or workflow).
- **Ontology.** An ontology could make explicit the concepts, roles, relationships, obligations, states, events, constraints, and provenance connecting the user, exploratory sessions, Jasper Supervisor, OpenSpec, Plane, Temporal, agents/sub-agents, tools, repository artifacts, approvals, and outcomes. It could express, for example, that an intent version constrains a proposed change, that a Temporal run dispatches an approved OpenSpec-linked activity, or that an observed tool action has an actor, target, authorization context, and result.
- **Retrieval tradeoffs.** An ontology may be more useful than vector retrieval or a text/document database for explicit relationships, constraint checks, and end-to-end traceability. Vector retrieval remains an optional complement for fuzzy similarity and text corpora, and text/document or relational storage may remain useful for documents, transactions, and operational records. The ontology is not claimed to replace either universally; the appropriate combination requires evaluation.
- **Small-model use.** A fine-tuned small local model could receive a compact subgraph or typed evidence packet, extract candidate intent and intent shifts from conversations, map utterances and observed actions to ontology concepts, identify affected entities and obligations, and emit structured facts for deterministic validation. The model would remain an interpreter/classifier that proposes evidence, not the authority for intent, consent, authorization, policy, or execution.
- **Deterministic tools and structures.** Candidate safeguards include JSON Schema or Pydantic validation; ontology/graph storage with exact queries; an event ledger; provenance IDs and timestamps; graph consistency and constraint checks; repository/dependency analysis; Temporal, OpenSpec, and Plane adapters; a tool-call gateway; and OPA/Rego evaluation. The primary LangGraph Supervisor conversation and actions would be observed through adapters and events, rather than assuming that the local model directly controls Jasper. These mechanisms should make facts, links, versions, and policy inputs inspectable and replayable where appropriate.
- **Monitoring and clarification.** The separate verifier could monitor the user conversation and the primary Supervisor for adherence signals, detect possible intent shifts, and ask the user for clarification. OPA should protect Coder actions in both planned/spec-driven work and emergent work, including actions observed through the applicable gateway or adapters. Monitoring output remains evidence for clarification and deterministic evaluation; it does not silently authorize changes or turn the verifier into a second Supervisor.
- **Open research questions.** Compare ontology/semantic-model memory with PostgreSQL and text storage, and with vector databases, on retrieval relevance, latency, footprint, explainability, update/version handling, small-model context efficiency, and throughput. Tests should include evolving intent, exact relationship queries, provenance reconstruction, constraint violations, concurrent or long-running work, and both planned and emergent coder actions. Results must distinguish measured observations, estimates, and unresolved assumptions.

The user supplied the video link and summary as research context for these inquiries. The claims in that material have not been independently verified in this proposal and must not be treated as evidence, requirements, or implementation facts until separately evaluated.

These inquiries do not create tasks, design artifacts, or specifications. They preserve the proposal's distinction between emergent and planned work, keep OPA/Rego policies stable with intent as input, and retain provenance from creative sessions through OpenSpec, Plane, Temporal, and execution. Any future work must continue to treat the local intent verifier as separate from the Jasper Supervisor.
