# Visualization Board Alignment

## Why

The repository now has a working visual workspace for grounded concept-map artifacts, but the OpenSpec documentation does not yet describe that surface accurately or separate observed behavior from approved future board-editing requirements. The documentation should give product, design, and implementation work one truthful contract without claiming that board editing, deletion, or Jasper mutation already exists.

## What Changes

- Document the current React Flow/XYFlow concept-map workspace, its grounded artifact boundary, outline/map presentation, voice interaction, relationship to Chat, Split, and Visual workspace modes, and the approved desktop/laptop control layout.
- Establish a single normal-flow desktop workspace top bar for session, todo, theme, repository, and Sources/Visuals actions; place Chat/Split/Visual mode controls in the desktop composer controls; and organize the remaining composer controls into lower left/right control groups without duplicating behavior.
- Replace the labeled tool-call switch with one accessible icon-only Wrench/Phone toggle that retains the existing tool-call visibility state.
- Record the current use of `@xyflow/react` and `lucide-react` as observed implementation facts; do not turn the current icon library into an unsupported product requirement.
- Specify editable board titles, explicit Enter commit, trash-icon deletion, and an unselected confirmation dialog that names the board and states permanent deletion.
- Approve direct user board editing as a future capability: moving/resizing nodes, editing node content, adding/deleting/reconnecting nodes and edges, and preserving the user’s layout.
- Specify that Jasper may edit the selected board only after an explicit user request, updating summaries and voice narration while preserving layout unless the user asks otherwise.
- Preserve provenance/evidence distinctions, durable session storage expectations, and the boundary against exposing internal reasoning or protected material.

## Capabilities

### New Capabilities

- `visualization-board`: Current visualization workspace behavior and the approved/future board title, deletion, direct-editing, and explicit Jasper-editing contract.

### Modified Capabilities

- None. Existing OpenSpec changes describe session anatomy and Research evidence, but do not define this board interaction contract.

## Impact

This change updates the desktop/laptop UI implementation and focused tests in addition to its OpenSpec documentation. It does not change schemas, migrations, generated files, dependencies, or stored data. The current response contract observed in the reviewed implementation is visual response version `2`; this change uses that version as an observation and does not propose a schema/version change.

## Open decisions

Before Jasper board editing is implemented, design must decide the exact edit request/tool schema; the durable representation of nodes, edges, layout, provenance, and revisions; revision numbering plus stale-update/conflict handling; the allowed node/edge mutation scope; the authorization boundary between user-directed edits and Jasper authority; whether edits mutate in place or create revision history; and the board-selection/session identity requirements, including behavior when identity is missing, stale, or ambiguous. These remain unresolved decisions, not current implementation requirements.

## Terminology boundary

This change uses **visual workspace** only for the Chat/Split/Visual presentation
surfaces and browser-local layout preferences. Repository selection is a separate
repository-path binding concern. Existing `workspace_id` fields and persisted keys
remain unchanged and mean the durable repository binding ID, not a visual workspace
ID. See `openspec/TERMINOLOGY.md`.
