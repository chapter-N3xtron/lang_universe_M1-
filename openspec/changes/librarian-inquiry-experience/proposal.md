# Librarian Inquiry Experience

## Why

Users often arrive with nonlinear thoughts, partial questions, competing concerns, and useful facts mixed together. The product needs a shared, inspectable inquiry experience that helps a person make sense of that material without silently deciding what they meant, forcing a conclusion, or turning research into an irreversible workflow. Jasper should facilitate the conversation; Librarian should do evidence work; the board and session record should preserve the complete, revisitable work.

## What Changes

- Define a human-controlled flow for bucketing and sensemaking of nonlinear input, including proposed buckets, uncertainty, corrections, and user confirmation.
- Define durable tent poles as user-controlled inquiry anchors that organize questions, evidence, decisions, and revisions without becoming a hidden agenda.
- Define evidence-grounded, revisitable decision-tree inquiries, including explicit return-from-rabbit-hole behavior and bounded playback.
- Allow optional use of versioned, sourced frameworks (for example, Information Technology Infrastructure Library (ITIL) or the scientific method) only when the user chooses them and the framework source/version is visible.
- Establish Jasper as a non-coercive conversational facilitator and Librarian as the research/evidence specialist. Librarian MUST preserve its existing Tavily iterative search path rather than inventing an alternate retrieval path.
- Define complete board artifacts, concise Jasper summaries, and bounded replay as separate representations of the same provenance-linked work.
- Define session, provenance, revision, memory/storage, authorization, attribution, uncertainty, safety, proposed-structure, and user-confirmed-structure boundaries.
- Apply the system governance layer to every inquiry mode, preserve the non-replacement-of-human-resonance boundary, and limit sensitive-domain help to bounded organization and resource navigation rather than advice or decisions.
- Specify compatibility with React Flow, LangGraph, Agent Chat UI, PostgreSQL/session catalog, and optional future vector or ontology layers without requiring those layers initially.

## Capabilities

### New Capabilities

- `inquiry-sensemaking`: Nonlinear-input bucketing, tent poles, user confirmation, framework choice, and Jasper facilitation.
- `librarian-evidence-inquiry`: Evidence-grounded decision trees, iterative Tavily research, revisitation, rabbit-hole return, attribution, uncertainty, and safety.
- `session-board-inquiry`: Complete board artifacts, concise/bounded presentation, session and storage boundaries, revisions, playback, and compatibility contracts.

### Modified Capabilities

- None. Existing changes remain authoritative for their stated scope; this change composes with them and does not rewrite their requirements.

## Belongs here versus existing changes

This change defines the shared inquiry experience and the handoff between sensemaking, facilitation, evidence work, session memory, and board presentation. `anatomy-of-a-session` owns the general session and user-authored Perspective anatomy. `research-agent-promotion` owns the top-level Research/Librarian handoff, durable source/report semantics, and evidence-grounded research outputs. `visualization-board-alignment` owns the board surface and direct board editing contract. `durable-interaction-records` owns the durable interaction ledger, Store authority, checkpoint correlation, and rebuild semantics. `user-intent-enforcement` owns the separate intent-protection plane and execution authorization. `isolate-coder-librarian-workers` owns trust-domain and worker isolation. This change MUST reference those boundaries rather than duplicate or supersede them.

## Non-goals

- No runtime implementation, user-interface implementation, database migration, dependency addition, retrieval-provider replacement, or claim that any capability is implemented.
- No autonomous decision, diagnosis, political or personal recommendation, persuasion, ranking of the user's values, or conversion of a proposal into authorization.
- No replacement for Tavily, LangGraph, Agent Chat UI, React Flow, PostgreSQL/session catalog, existing Store/checkpoint rules, or worker isolation.
- No requirement for vector search, ontology storage, semantic graph infrastructure, framework automation, or a new persistence system.
- No exposure of hidden reasoning, secrets, protected material, raw tool payloads, or unrestricted web/repository access.

## Dependencies and risks

Dependencies are the existing changes named above, current Librarian/Tavily and evidence contracts, session catalog/Store boundaries, and the current board presentation contract. A future implementation MUST verify exact APIs and versions before relying on them.

Material risks include anchoring or framing that changes what a user considers, false confidence from incomplete evidence, framework authority being mistaken for truth, stale sources, privacy leakage through durable memory, replay that overstates continuity, and a facilitator gradually becoming coercive. The design therefore requires visible uncertainty, provenance, confirmation states, bounded retention, and refusal/clarification paths.

## Unresolved decisions

Exact bucket/tent-pole schemas; whether a tent pole may be merged or split; tree depth and time/resource bounds; framework registry ownership, licensing, update cadence, and citation format; source-quality and conflict presentation; retention and deletion controls; cross-session memory opt-in; board revision/conflict rules; playback controls; and the exact user authorization surface remain open. These are not silently resolved by this change.

## Acceptance scope

The scenarios in the capability specifications are the acceptance contract for future implementation. They describe required behavior, not current capability or completed work. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## Governance-layer boundary

All inquiry modes—bucketing, decision trees, framework inquiries, tent poles, direct sensemaking, Librarian research, and board/session presentation—are governed by the system governance layer. The system MUST NOT present itself as empathetic, emotionally reciprocal, or a substitute for human relationships, care, professional judgment, or human support. For relationship distress, anxiety, medical, legal, or financial topics, it MAY provide bounded organizational or administrative assistance, including structuring thoughts, preparing questions, locating human/professional/community resources, and navigating healthcare/insurance logistics. It MUST NOT provide emotional, medical, legal, or financial advice, diagnosis, treatment, or decisions. If a user appears to need human or qualified professional support, it must neutrally encourage that support without coercion or simulated empathy.

User agency is preserved through no hidden steering, no interpretation of silence as consent, and explicit labels for `user-stated`, `sourced`, `inferred`, `proposed`, and `system-generated` material. `GOVERNANCE_FRAMEWORK.md` is the working governance draft. The applicable approved constitution, rule registry, human interrupts, and `user-intent-enforcement` intent/authorization change remain authoritative; this change does not replace them. Exact support-recognition criteria, wording, resource maintenance, and any emergency or clinical protocol remain unresolved and are intentionally not invented.

## Terminology boundary

A tent pole is a user-controlled inquiry anchor, not an inferred user belief. A proposed structure is model-generated and unconfirmed; a user-confirmed structure is explicitly accepted or edited by the user. A session is the durable body of work; a visual workspace is only the presentation surface. Existing repository `workspace_id` and session catalog meanings remain unchanged.
