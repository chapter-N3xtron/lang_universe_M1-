## Context

The reviewed implementation renders saved or newly received `react_flow` concept-map artifacts in `agent-chat-ui/src/components/workspace/concept-map-renderer.tsx` using `@xyflow/react` (the React Flow/XYFlow implementation) and Dagre for automatic layout. The renderer currently derives node positions, marks nodes as non-draggable, disables edge connection, and presents map controls plus an Outline view. Nodes can be selected, narrated with TTS, highlighted during narration, and used to seed a grounded Jasper follow-up.

`WorkspaceShell` currently provides persistent Chat, Split, and Visual modes. Split uses resizable chat and visual panels; the selected mode is persisted per thread. A visual suggestion may offer a mode change, but the person applies it. A visual artifact is not the same thing as an editable board: the current renderer is principally a grounded presentation surface.

The current response/type contract observed in the UI is version `2` (`JasperResponse.version` and the test fixtures), with `renderer: "react_flow"`. The existing durable session catalog stores session visual artifacts and references; the OpenSpec contract must preserve that durable relationship without inventing a new persistence schema here.

## Observed implementation versus approved behavior

### Observed now

- Concept maps are rendered with `@xyflow/react` / React Flow and automatic Dagre positioning.
- The current concept nodes are not draggable and the current flow is not connectable; this is why direct board editing is not claimed as implemented.
- The surface supports Map/Outline presentation, node selection, source labels, evidence-aware metadata, node narration/replay, and a highlighted node during voice playback.
- Chat, Split, and Visual modes are available, with persistent mode and resizable Split panels.
- The UI imports icons from `lucide-react` (Lucide React), including mode, map, narration, source, session, and action icons. This is an implementation/library observation, not a requirement that all future board controls must use Lucide.
- The current visual title is displayed from the artifact title. The inspected implementation does not provide the requested board-title click/Enter editor, trash-icon deletion action, deletion confirmation dialog, or direct node/edge editing workflow.

### Approved or proposed product behavior

- A person may rename the selected board by clicking its title, entering a non-empty title, and pressing Enter to commit. Escape/cancel behavior should avoid an accidental rename.
- A trash icon is the deletion affordance. Activation opens a confirmation dialog naming the board and explicitly stating that deletion is permanent. The dialog has no preselected option; the person must choose Cancel/Keep or the destructive confirmation.
- Direct board editing is approved as a future capability, not a current implementation claim.
- Jasper may modify the selected board only on an explicit user request. Jasper may update node/edge summaries and voice narration, but must preserve the user’s layout unless the user explicitly asks for layout changes.
- The visual surface must retain evidence and provenance labels when content is edited. User-defined, observed, researched, proposed, and inferred claims must remain distinguishable; editing text must not silently convert attribution or evidence status.
- **Approved desktop/laptop workspace layout:** one normal-flow top bar remains above Chat, Split, and Visual workspaces. It contains the existing session controls (All sessions, Fork as new session, Close session, New session), todo, theme, repository link/control, and Sources/Visuals affordance as applicable. The floating mode navigator is removed. Icon-only Chat, Split, and Visual controls move to the left of the desktop composer control row; their state continues to use the existing per-thread workspace preference. The lower composer row groups model, mode, upload, and the one tool-call visibility control on the left, and agent, voice, repository, and repository-access selectors on the right. Text entry, microphone, and send remain in the main input area. The visibility control retains the existing `hideToolCalls` query-state behavior, displaying Wrench and Phone icons with state-specific accessible names. No new persistence or control state is introduced, and mobile behavior is retained outside this desktop/laptop scope.

## Design boundaries

1. **Board identity and lifecycle**
   A board is a visual artifact associated with a durable session. Renaming changes the board’s user-facing title, not its artifact identity, cited evidence identifiers, source locators, content digests, or Research authorship. Deleting a board permanently removes that board artifact and its board-specific references from the user-visible session. It must not silently delete shared evidence or canonical Research reports that the board cites; those require their own lifecycle decision.

2. **Layout ownership**
   Automatic layout may be used when a board is first presented or when the user requests re-layout. Once the user moves or resizes nodes, the resulting positions and dimensions are user layout state. Content-only edits, including Jasper summary/narration edits, preserve those positions and dimensions by default.

3. **Direct editing scope**
   Future direct editing includes moving and resizing nodes; editing node labels, details, claim metadata where permitted, and narration; adding and deleting nodes; and adding, deleting, or reconnecting edges. All mutations need validation against the board’s evidence/provenance boundary and must preserve a usable accessible Outline representation.

4. **Jasper authority**
   “Edit the board” is an explicit user-directed action scoped to the selected board. Jasper must not rewrite a board merely because it is selected, because a new chat turn occurred, or because a visual suggestion was shown. Jasper can update summaries and voice narration only when requested, and must report what changed without exposing internal reasoning.

5. **Voice and highlighting**
   Voice playback may narrate node content and must visibly highlight the node currently being narrated. Stopping or completing narration clears the active highlight. Narration must preserve the board’s claim status and evidence references and must not speak raw URLs as a substitute for provenance.

6. **Durability and evidence**
   Board state and revisions must remain associated with the durable session storage boundary and be reopenable without requiring a new web read. Checkpoints may hold bounded working context and lightweight references; durable evidence/report bodies remain in the existing Store boundary. A board cannot claim research grounding without valid saved evidence references. Protected content, credentials, environment files, private keys, auth headers, Git internals, and internal reasoning are outside the board surface.

## Open decisions before Jasper editing

The following questions were identified in the prior analysis and are intentionally unresolved:

1. **Edit request/tool schema:** What exact user-facing request forms and structured Jasper tool arguments identify the operation, target board, requested fields, layout intent, expected revision, and response/audit summary?
2. **Durable layout representation:** How are node positions, dimensions, ordering, viewport, layout ownership, and layout version stored durably alongside the board without changing the existing persistence schema in this documentation-only change?
3. **Revision and conflicts:** What revision token/version is required, how are stale updates detected, and whether conflicts are rejected, merged, previewed, or require explicit user resolution?
4. **Mutation scope:** Which node and edge fields and graph operations may Jasper change, and which are prohibited or require separate user approval (including creation/deletion/reconnection, evidence links, claim metadata, and layout)?
5. **Authorization boundary:** What proves an explicit user request, what permissions apply to the session/board, and which operations must remain user-only or be separately confirmed?
6. **In-place versus history:** Do accepted edits replace the current board in place, create immutable revisions, or support both, and what restore/undo/audit behavior follows?
7. **Selection and identity:** How are board ID, durable session ID, and active chat/session context carried and validated, and what happens when the selected board is missing, stale, or ambiguous?

These questions do not weaken the already documented requirements for an explicit target, no ambiguous edits, preservation of layout/provenance/evidence, protection of shared evidence/reports, or separation of observed implementation from proposed behavior.

## Alternatives considered

- Treat the current generated concept map as already editable: rejected because the inspected React Flow nodes are non-draggable and connections are disabled.
- Use a board title as a replacement for immutable artifact identity: rejected because provenance and durable references must survive display-name changes.
- Let Jasper opportunistically rewrite selected boards: rejected because selection is not consent for mutation and would undermine user control and layout preservation.
- Make Lucide React a normative product dependency: rejected because the current library is observed implementation detail; the product requirement is the affordance and accessible meaning, not a particular icon package.
