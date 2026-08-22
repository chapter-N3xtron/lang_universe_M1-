# Design: Coder Architecture Delivery Board

## Context and observations

The repository already separates Jasper's user-facing conversation from specialist work, has a React Flow/XYFlow concept-map renderer, and documents durable interaction and session/artifact concepts. `AGENT_OUTPUTS_VISUALIZATION_BOARD_REQUIREMENTS.md` requires concise Jasper output and complete board material. These are observations and constraints, not proof that this proposal is implemented. The existing visual artifact contract is bounded and uses `renderer: "react_flow"`; the existing session catalog and LangGraph Store/checkpointer boundaries must remain intact.

## Goals

1. Let the user choose and see whether Coder is delivering an implementation or explaining architecture.
2. Make explanations traceable to an exact repository revision and safe source locations.
3. Present both readable documents and interactive relationships on the shared board.
4. Make progress, risk, authorization, playback, and incompleteness honest and recoverable.

## Decisions

### 1. User-controlled modes and state

Coder MUST expose exactly two product modes in this contract. **Implementation/delivery** is a deadline-oriented mode: the user supplies or confirms scope, desired completion time if any, acceptance criteria, and authorization; Coder may perform only approved repository-local work. A deadline is a user constraint, not a promise or a reason to weaken safety. **Architectural comprehension** is read-only: Coder may inspect approved repository material and produce explanations/artifacts, but MUST NOT write files, install packages, change configuration, run mutating commands, publish, or infer permission to do so. The selected mode MUST be visible in status and records, and changing it requires an explicit user action.

Every run MUST expose status `queued`, `in_progress`, `completed`, `partial`, `blocked`, `at_risk`, `cancelled`, `timed_out`, or `failed`, with an explanation, known next step, and (when applicable) deadline relationship. `at_risk` MUST identify evidence of risk rather than manufacture a percentage or certainty.

### 2. Source-grounded explanation model

An explainer SHOULD organize a request into layers: repository/module map; symbol cards for functions and variables; control-flow graph; data-flow graph; loop and iteration cards; async/event timeline; and source excerpts. Each claim MUST link to a source locator containing repository-relative path, symbol or block identifier where available, start/end line range, and the inspected repository revision (commit or equivalent immutable revision). Line ranges are anchors, not permission to read unrelated content. Missing, generated, vendored, binary, secret-like, or ambiguous sources MUST be marked unavailable or blocked.

Explanations MUST describe regular loops (initialization, condition, body, update, termination), and asynchronous loops/`await`/event flows (suspension, resumption, scheduling boundary, event source, error/cancellation path) without claiming runtime behavior that static evidence cannot establish. The artifact MUST distinguish observed code, inferred relationship, proposed interpretation, and unresolved question.

### 3. Layered board delivery

A board delivery MUST have a human-readable summary layer, a source-linked explanation layer, and optional relationship/playback layers. The shared board MAY render these as cards, outline sections, and React Flow nodes/edges. Existing React Flow interactive diagrams MUST remain supported; this change does not redefine their envelope, add a renderer, or authorize edits. Layering is a presentation and artifact-organization concept, not a new transport or storage authority.

Jasper chat MUST contain only a concise summary, status, material blocker/risk, and useful next step. The complete explanation, source links, diagrams, excerpts, and reports MUST be available on the board for opening, reading, inspecting, searching, and later listening. The full material MUST NOT be duplicated into chat merely because a specialist returned it.

### 4. Semantic playback

Playback MUST be chunked by semantic unit (for example module, symbol, control-flow branch, loop phase, or event transition), not arbitrary text size alone. Each chunk MUST reference an artifact revision, stable chunk identity, source targets, and the board highlight target(s). During playback the board SHOULD highlight the corresponding node, edge, outline item, or source range; a stale or missing target MUST produce an honest unavailable-highlight state and MUST NOT silently highlight a different object. Replaying an older revision MUST use that revision's chunks and targets. Voice text MUST be bounded and must not read secrets, raw credentials, or internal reasoning.

### 5. Boundaries and authority

A session owns the user-visible request, mode selection, status, summaries, and artifact references. Provenance records who/what produced each claim and whether it is user-authored, observed, researched, generated, inferred, or proposed. A board artifact belongs to its producing session/thread; a repository binding is separate and optional. Repository revision identifies what was inspected or changed and MUST be retained with the artifact. LangGraph checkpoints remain execution continuity; LangGraph Store remains the durable application-memory authority where already specified; the session catalog remains its existing projection/catalog boundary. No new memory or storage authority is introduced.

In implementation mode, Coder MUST use least privilege and stop at new, destructive, external, secret-bearing, or broader actions requiring authorization. The worker isolation change remains the execution trust boundary: Linux/Docker workers can perform only their permitted work inside the approved Compose deployment, and Docker lifecycle is not authority to mutate host files. Host operations and publication remain separately governed capabilities. Comprehension mode is read-only even if a worker technically has write access.

### 6. Relationship and non-duplication

- `coder-architecture-workflow` owns delegation, execution-mode distinction, authorization grouping, routine verification, and Jasper's contextual report summary; this change specializes Coder's two product modes and board/explainer content without replacing it.
- `visualization-board-alignment` owns the shared visual surface, current React Flow behavior, board identity/layout/evidence boundaries, and future editing questions; this change adds no competing board identity or renderer.
- `durable-interaction-records` owns durable interaction records, revisions, playback records, and Store authority; this change defines required links/semantics but no record schema.
- `anatomy-of-a-session` owns session identity, artifact association, and user-authored Perspective; this change does not redefine a session or attribute generated explanation to the user.
- `isolate-coder-librarian-workers` owns worker/container trust separation and grouped Docker lifecycle; this change consumes that boundary and does not create a transport, broker, or topology.

## Alternatives rejected

- Put full reports in chat: rejected because it duplicates material and obscures the conversational summary contract.
- Create a second architecture canvas/storage database: rejected because it conflicts with existing board and durable-record authorities.
- Treat static traces as runtime truth: rejected because source evidence cannot prove all scheduling or dynamic behavior.
- Let deadlines override authorization: rejected because urgency is not consent or expanded scope.

## Risks and mitigations

- **Stale source links:** bind every artifact and playback chunk to a revision and mark moved/deleted targets unavailable.
- **Overconfident inference:** label inference and unresolved questions; show evidence paths.
- **Board overload:** use layers, outline navigation, bounded excerpts, and concise chat.
- **Playback drift:** revision-specific chunk IDs and target validation prevent cross-revision highlights.
- **Deadline pressure or scope creep:** visible status and authorization stops preserve user control.
- **Worker compromise or leakage:** retain isolation, least privilege, and secret-denial rules; do not treat Docker as a host boundary.

## Unresolved decisions

Future implementation must decide the exact compatible artifact/playback fields, source-parser fidelity, revision-token format, conflict behavior, line-range mapping after edits, board layer navigation, voice duration limits, and deadline display policy. It must also define test fixtures for async/event behavior and inaccessible sources. None are resolved by this documentation change.

## Governance-layer boundary

Both Coder modes are governed by the system governance layer. Coder MUST NOT present itself as empathetic or emotionally reciprocal, or as a substitute for human relationships, care, professional judgment, or human support. For relationship distress, anxiety, medical, legal, or financial topics, future behavior is limited to bounded organization, question preparation, resource location, or healthcare/insurance logistics; it must not provide advice, diagnosis, treatment, or decisions. Apparent need for human or qualified professional support calls for neutral encouragement, without coercion or simulated empathy.

The implementation contract must preserve agency and explicit provenance labels (`user-stated`, `sourced`, `inferred`, `proposed`, and `system-generated`) across architecture explainers, board artifacts, and delivery workflows. Silence and attention are never consent or authorization. `GOVERNANCE_FRAMEWORK.md` is a working draft; the approved constitution, rule registry, human interrupts, and `user-intent-enforcement` boundary remain authoritative. Support-recognition criteria and resource-maintenance responsibilities are unresolved and must not be invented here.
