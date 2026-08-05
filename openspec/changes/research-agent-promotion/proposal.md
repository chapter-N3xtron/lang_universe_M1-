## Why

Research is user-approved as an independently addressable top-level specialist, but the promotion must be specified as a bounded, auditable handoff rather than treated as an implicit implementation detail. Formal tracking is needed to preserve read-only authority, durable evidence provenance, session continuity, accessible source review, and complete release verification while keeping `todos.json` as the project-level task authority.

## What Changes

- Specify the visible lifecycle `Jasper -> Research -> Jasper -> record_session -> END` while retaining direct UI-selected entry to the existing top-level `research` node.
- Specify Jasper's documented `transfer_to_research` parent-graph Command, exact bounded handoff state, matching tool-call/result messages, final-only Research return, and materially-needed delegation rule.
- Remove Research from Jasper's hidden `CompiledSubAgent` list while preserving Research as an independently addressable top-level agent.
- Restrict Research to web search, explicitly selected page reads, reopening saved evidence, supported upload analysis, and safe read-only selected-workspace discovery and reads.
- Specify status-aware, bounded, immutable evidence records in the existing Agent Server LangGraph Store, lightweight checkpoint/session references, deduplication, preserved versions, offline reopen, and fork inheritance without body copying.
- Seed Jasper's evidence registry from saved session evidence and require every researched visual concept-map node and edge to cite valid saved evidence IDs.
- Add or complete the Sources view in the existing session visual workspace, including complete source metadata, immutable provenance, accessible session-specific renaming, and source-restricted `Map all` / `map selected` request composition through the existing composer.
- Preserve Research provenance and configured Research voice; Jasper introduces the transition and provides final synthesis. URLs remain clickable but are not spoken by TTS.
- Exclude custom persistence, migrations, databases, APIs or evidence services, vector indexes, OCR, whole-site crawling, shell/execute, Research mutation tools, host-filesystem access, and speculative services.
- Require focused and full automated checks, real Agent Server graph inspection, and a separately reported live-provider smoke test before implementation todos may be completed.

## Capabilities

### New Capabilities

- `top-level-research-handoff`: Visible top-level routing, bounded Jasper–Research transfer, direct entry, read-only Research authority, and final-only return behavior.
- `durable-session-evidence`: Status-aware bounded evidence, immutable Agent Server Store records, lightweight session references, provenance, deduplication/versioning, reopen, fork inheritance, and visual concept-map citation rules.
- `session-sources-view`: Complete session source review, accessible session-specific renaming, immutable provenance, visual usage, and source-restricted visual concept-map request composition.

### Modified Capabilities

- None. The repository has no existing main OpenSpec capability specifications.

## Impact

### Observed repository baseline

- `backend/src/chat_ui.py` already defines a top-level `research` node, direct supervisor routing, delegated return to Jasper, and `record_session` termination paths.
- `backend/src/jasper_agent.py` currently returns no hidden compiled specialists and defines `transfer_to_research` with `graph=Command.PARENT`.
- `backend/src/research_agent.py` already exposes read-only Deep Agents filesystem middleware and returns a final Research message with Research speaker provenance.
- `backend/src/research_evidence.py` already contains a 50,000-character bound and Agent Server Store namespaces for evidence bodies and session source records.
- `agent-chat-ui/src/components/workspace/session-sources.tsx` already contains a Sources view, session-specific display-name editing, links, visual usage, and visual concept-map request composition.
- These observations describe existing code only; they do not establish full conformance or completion of the user-defined requirements.

### Proposed affected areas

- Backend graph and handoff contracts, Research tool exposure, workspace/attachment safety, evidence schemas and Store behavior, visual evidence validation, session recording/fork behavior, Sources workspace components, composer integration, accessibility, provenance, and TTS presentation.
- Project implementation authority remains the existing todos `implement-visible-jasper-research-handoff`, `persist-bounded-session-research-evidence`, `add-session-sources-view-and-renaming`, and `verify-top-level-research-and-session-sources` in `todos.json`. OpenSpec tasks link to those IDs and do not replace or override their truthful statuses.
- Governance review remains required under `GOVERNANCE_FRAMEWORK.md`, especially human editorial ownership, visual/voice separation, session continuity, specialist participation, authorization, and durable LangGraph boundaries.
