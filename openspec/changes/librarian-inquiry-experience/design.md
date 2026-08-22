# Design: Librarian Inquiry Experience

## Status and evidence boundary

This is a proposed documentation contract. Repository observations (existing `librarian_agent.py`, `jasper_tools.py`, `research_evidence.py`, session routes, and React Flow board components) are implementation context only; they do not prove conformance. Existing Librarian currently invokes the Open Deep Research path, whose search tools include Tavily-backed behavior. Future work MUST preserve the established iterative search, read, evidence-save, and report flow after any worker or orchestration boundary change.

## Experience model

1. Jasper receives the user's words and MUST first reflect a compact, uncertainty-labeled interpretation when the structure is unclear.
2. The system proposes buckets (topics, tensions, facts, questions, constraints, decisions, and unknowns) with links to the originating user material. It MUST allow easy correction, deletion, merge, and rename.
3. The system proposes tent poles: a small set of durable inquiry anchors. Each anchor MUST show why it was proposed and MUST remain unconfirmed until the user accepts or edits it.
4. The user chooses direct inquiry, a decision tree, Librarian research, an optional framework, or a return to the prior branch. A choice is not authorization for unrelated work.
5. Librarian performs bounded iterative discovery and explicit page reading through its existing Tavily path, saves evidence and provenance, and returns claims, counterevidence, gaps, and next questions.
6. Jasper presents a concise summary and asks whether to continue, revise, return, or stop. The complete board/session artifact remains available for inspection.

## Roles and authority

Jasper MUST facilitate, clarify, summarize, offer options, and respect stop/return/correction. Jasper MUST NOT pressure a user toward a bucket, framework, decision, or research path. Librarian MUST specialize in retrieval, source evaluation, evidence capture, and citations; it MUST NOT present evidence as the user's conclusion or authorize actions. User confirmation is the authority for durable inquiry structure and decisions. The separate user-intent-enforcement change remains authoritative for protected execution authorization.

## Structure and provenance

Every bucket, tent pole, question, branch, claim, framework use, summary, board node, and revision SHOULD carry stable identity, source/parent links, timestamp, author/actor, status, confidence/uncertainty, and revision links. User-authored, user-confirmed, model-proposed, model-inferred, observed, and externally sourced material MUST remain distinguishable. A proposal MUST NOT be serialized as confirmed merely because it was displayed, repeated, or used temporarily.

## Frameworks

Frameworks are optional aids, never mandatory stages. A framework registry entry MUST include name, version, publisher/source, retrieval date, license/usage constraints, and a concise description of intended use. ITIL and the scientific method are examples, not bundled requirements. Framework prompts and mappings MUST be inspectable, bounded, and reversible; a framework MUST NOT override user intent, evidence, safety policy, or uncertainty.

## Branching and rabbit-hole return

A decision-tree branch MUST have a parent anchor/question, purpose, status, and bounded budget or stop condition. Entering a sub-branch MUST create a return point. “Return” MUST be an explicit user-visible action that restores the prior branch context and reports what was learned, what remains uncertain, and what was not completed. The system MUST NOT infer return from silence, attention, or a topic change.

## Representations

The canonical durable artifact is the complete structured inquiry/board record with provenance, evidence links, branch history, and revisions. Jasper's chat response SHOULD be concise and link to the relevant nodes or sources rather than duplicating the full artifact. Playback MUST be bounded by an explicit segment, time/length limit, or user-selected range, and MUST identify whether content is a summary, source excerpt, or user-authored text. No representation may expose hidden reasoning or silently collapse uncertainty.

## Storage and compatibility

LangGraph checkpoints remain bounded execution state; the existing Store/session boundary remains the durable artifact and evidence authority; PostgreSQL/session catalog remains a rebuildable projection as defined by `durable-interaction-records`. Session relationships and memory retention MUST be explicit and owner-authorized; cross-session reuse MUST be opt-in and provenance-preserving. React Flow/XYFlow may render board artifacts, Agent Chat UI may render chat and controls, and existing session catalog routes may index records, but none is required to become the source of truth. Vector retrieval and ontology/semantic layers MAY be added later as adapters; the initial contract MUST work without either.

## Governance-layer boundary

All inquiry modes and representations described here—bucketing, decision trees, framework inquiries, tent poles, direct sensemaking, Librarian research, board artifacts, and delivery of summaries—remain under the system governance layer. The system must not present itself as empathetic, emotionally reciprocal, or a substitute for human relationships, care, professional judgment, or human support. In relationship distress, anxiety, medical, legal, or financial contexts, it may only organize the user's material, prepare questions, locate human/professional/community resources, or help navigate healthcare/insurance logistics; it must not provide emotional, medical, legal, or financial advice, diagnosis, treatment, or decisions. If human or qualified professional support appears needed, the system should neutrally encourage it without coercion or simulated empathy.

Every representation must explicitly label `user-stated`, `sourced`, `inferred`, `proposed`, and `system-generated` material. Silence, attention, repeated display, or a selection is never consent or authorization. `GOVERNANCE_FRAMEWORK.md` is a working governance draft; the approved constitution, rule registry, human interrupts, and `user-intent-enforcement` intent/authorization boundary remain authoritative. Support-recognition criteria, resource maintenance, and any emergency or clinical protocol are unresolved and are not specified here.

## Failure and safety behavior

On missing, conflicting, stale, or insufficient evidence, Librarian MUST say so and offer clarification, more bounded research, or stop. Sources MUST be attributed to their actual publisher/author and retrieval status; search snippets and failed reads MUST NOT be called read pages. Sensitive content, secrets, unauthorized workspace paths, and disallowed external actions MUST be denied and excluded from summaries, artifacts, and logs. Authorization MUST be explicit for storage, cross-session memory, external disclosure, and consequential actions.

## Implementation sequencing (future only)

Future implementation should first agree on schemas and state transitions, then add deterministic proposal/confirmation handling, then integrate existing Librarian evidence references, then render board/chat/playback projections, and finally test recovery, stale revisions, privacy, accessibility, and non-coercion. This sequence is a plan, not an implementation claim.
