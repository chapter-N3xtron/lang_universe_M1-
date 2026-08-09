## Purpose

Define the truthful current visualization-board workspace and the approved future interaction contract for board title, deletion, direct editing, explicit Jasper editing, voice highlighting, provenance, and durable session behavior.

## ADDED Requirements

### Requirement: Current grounded visualization workspace

The current UI SHALL be documented as a React Flow/XYFlow concept-map visual workspace that renders `react_flow` artifacts with nodes, edges, source/evidence references, claim status, narration content, and an accessible Outline representation. The workspace SHALL be understood as a visual presentation surface today; this requirement SHALL NOT claim that direct board mutation is already implemented.

#### Scenario: User opens a grounded visual artifact

- **WHEN** a valid visual artifact is available for the session
- **THEN** the workspace SHALL present its concept map or Outline, retain the artifact’s title and alt text, and expose its source/evidence relationships without exposing tool-call internals

#### Scenario: Current renderer does not support direct mutation

- **WHEN** the current implementation renders a board
- **THEN** the documentation and product surfaces SHALL NOT represent its non-draggable nodes or non-connectable edges as already editable

### Requirement: Chat, Split, and Visual relationship

The workspace SHALL retain distinct Chat, Split, and Visual modes. Chat SHALL focus on conversation, Visual SHALL focus on the visual surface, and Split SHALL show resizable chat and visual panes. A suggested mode SHALL remain a suggestion that the user applies; it SHALL NOT silently take control of the foreground. The selected mode and supported panel layout SHALL remain durable for the thread according to existing client/session persistence behavior.

#### Scenario: User changes workspace mode

- **WHEN** the user selects Chat, Split, or Visual
- **THEN** the corresponding surface arrangement SHALL be shown, and returning to the thread SHALL restore the supported persisted preference without implying that the board itself was edited

### Requirement: Stable desktop workspace controls

On desktop and laptop viewports, the workspace SHALL render one consistent top bar in normal document flow above the Chat, Split, and Visual surfaces. It SHALL retain an equivalent available action for All sessions, Fork as new session, Close session, New session, todo visibility, theme, repository link/control, and Sources/Visuals. Existing session availability and disabled rules, close/fork flows, and per-thread workspace persistence SHALL remain intact. The workspace SHALL NOT duplicate controls or retain a floating Chat/Split/Visual navigator above the panes.

#### Scenario: User changes workspace modes

- **WHEN** the user selects Chat, Split, or Visual through the icon-only desktop composer controls
- **THEN** the workspace SHALL use the existing persisted mode behavior and visibly distinguish the selected control

#### Scenario: User accesses top-bar session actions

- **WHEN** a session is open, closed, or unavailable
- **THEN** the top bar SHALL expose the corresponding existing session action with its current enabled or disabled state and flow

### Requirement: Desktop composer control organization

On desktop and laptop viewports, text entry, microphone, and send SHALL remain in the primary input area. A lower composer control row SHALL place model selection, icon-only Chat/Split/Visual controls, file upload, and exactly one tool-call-visibility control on the left; agent selection, voice selection, repository selection, and repository-access selection on the right. The mode controls SHALL have accessible names and tooltips. The Chat control SHALL use a chat-appropriate icon, Split a split-panel icon, and Visual an eye-inside-a-square visual-board icon or an accessible Lucide composition with that meaning.

#### Scenario: User changes tool-call visibility

- **WHEN** the user activates the single tool-call-visibility control
- **THEN** the existing tool-call visibility state SHALL change, and the icon-only control SHALL expose either “Show tool calls” or “Hide tool calls” according to the resulting behavior while using the Wrench and Phone icon treatment

### Requirement: Lucide implementation distinction

The documentation SHALL identify `lucide-react` / Lucide React icons as an observed implementation choice in the current UI. Lucide usage SHALL NOT be presented as a normative product requirement. Any future title, trash, mode, or narration control SHALL have an accessible name and discernible meaning regardless of whether Lucide or another icon implementation is used.

#### Scenario: Icon library changes

- **WHEN** a future implementation replaces or supplements Lucide icons
- **THEN** the board behavior and accessible affordances SHALL remain conformant without treating the library change as a product behavior change

### Requirement: Editable board title

A future editable board SHALL let the user start title editing by clicking the displayed board title, commit a non-empty title by pressing Enter, and cancel without mutation via Escape or an equivalent explicit cancel interaction. Renaming SHALL change only the user-facing board title and SHALL preserve board identity, layout, evidence references, provenance, and durable session association.

#### Scenario: User commits a board title

- **WHEN** the user clicks the board title, enters a non-empty replacement, and presses Enter
- **THEN** the board SHALL display and durably retain the replacement title while preserving its board identity, layout, and provenance

#### Scenario: User cancels a board title edit

- **WHEN** the user is editing a board title and presses Escape or cancels
- **THEN** the board SHALL exit title editing without changing the stored title

### Requirement: Permanent board deletion confirmation

A future board SHALL expose deletion through a trash-icon affordance with an accessible name. Activating it SHALL open a confirmation dialog that names the board and explicitly states that deletion is permanent. Neither the cancel option nor the destructive confirmation option SHALL be preselected; deletion SHALL occur only after an explicit destructive confirmation, while Cancel/Keep SHALL leave the board unchanged.

#### Scenario: User reviews permanent deletion

- **WHEN** the user activates the board trash icon
- **THEN** a modal confirmation SHALL identify the board by name, state that deletion is permanent, and present both choices with neither choice preselected

#### Scenario: User cancels deletion

- **WHEN** the user chooses Cancel/Keep or dismisses the confirmation
- **THEN** the board and its user-visible session reference SHALL remain unchanged

#### Scenario: User confirms deletion

- **WHEN** the user explicitly confirms permanent deletion
- **THEN** the board artifact and board-specific session reference SHALL be permanently deleted, and shared evidence or canonical Research reports SHALL not be deleted implicitly

### Requirement: Direct user board editing is approved for future implementation

A future board SHALL support direct user editing of node positions and sizes, node content, and graph structure: adding and deleting nodes, adding and deleting edges, and reconnecting edges. The system SHALL validate edits, preserve evidence/provenance distinctions, and preserve the user’s layout across content-only changes and reopenings. Automatic re-layout SHALL occur only on initial layout, explicit user request, or an explicitly accepted operation that requires it.

#### Scenario: User edits graph content and structure

- **WHEN** the user moves or resizes a node, edits content, adds or deletes a node, or adds, deletes, or reconnects an edge
- **THEN** the board SHALL retain the requested valid change, preserve other user layout state, and keep claim status and evidence references interpretable

#### Scenario: User reopens an edited board

- **WHEN** the user reopens a durably saved board
- **THEN** the board SHALL restore the latest saved user layout and valid edits without requiring a new web read solely to reconstruct the board

### Requirement: Explicit Jasper board editing

Jasper SHALL edit the selected board only when the user explicitly requests board editing and the selected board is identified. Jasper MAY update node/edge summaries and voice narration, but SHALL preserve the user’s layout and dimensions unless the user explicitly requests layout changes. Jasper SHALL preserve Research authorship, evidence references, claim status, and the distinction between user-defined and generated content.

#### Scenario: User asks Jasper to update the selected board

- **WHEN** the user explicitly asks Jasper to edit the selected board
- **THEN** Jasper SHALL update only the requested board content, report the resulting changes, preserve layout by default, and retain valid provenance/evidence references

#### Scenario: Board is selected but no edit is requested

- **WHEN** a board is selected and the user asks an unrelated question or merely views it
- **THEN** Jasper SHALL NOT mutate the board

### Open decisions: Jasper editing contract

The following are unresolved and SHALL be decided before implementation: the exact edit request/tool schema; the durable representation of node, edge, layout, provenance, and evidence state; revision identifiers and stale-update/conflict behavior; the permitted node/edge mutation scope; the authorization boundary proving explicit user intent and separating user-only operations; in-place mutation versus immutable revision history and restore/undo/audit behavior; and the board-selection/session identity fields and failure behavior for missing, stale, or ambiguous targets. Until decided, the requirements above remain a proposed contract, not an implementation authorization. Any decision SHALL retain an explicit target board, reject ambiguous edits, preserve layout/provenance/evidence, protect shared evidence and canonical reports, and distinguish observed current implementation from proposed behavior.

### Requirement: Voice playback highlights the narrated node

During voice playback of a board node, the visual workspace SHALL highlight the node whose narration is currently playing. The highlight SHALL clear when playback stops or completes, and the narration SHALL retain the node’s claim status and evidence context without speaking raw URLs as the provenance mechanism.

#### Scenario: User plays node narration

- **WHEN** voice playback begins for a node
- **THEN** that node SHALL be visibly and accessibly distinguished as active, and the active state SHALL clear when playback ends or is stopped

### Requirement: Provenance and durable session boundary

Every board SHALL remain associated with its durable session and SHALL preserve artifact identity, source/evidence references, claim status, provenance, limitations, and applicable content/version metadata through title edits, direct edits, Jasper content edits, reopenings, and deletion of unrelated boards. Board editing SHALL NOT turn inferred, proposed, researched, observed, or user-defined content into another claim type without an explicit valid operation. Durable evidence bodies and canonical Research reports SHALL remain in the existing Store boundary, while checkpoints retain only bounded working state and lightweight references.

#### Scenario: Board uses saved research evidence

- **WHEN** a board contains research-derived claims
- **THEN** each such claim SHALL resolve to valid saved evidence identifiers or validated canonical-report references, and the board SHALL not trigger a new web read merely because it is reopened or edited

#### Scenario: Board cannot access protected material

- **WHEN** a board operation would expose secrets, credentials, environment files, private keys, auth headers, Git internals, or internal reasoning
- **THEN** the operation SHALL be denied and the protected material SHALL not be placed in the board, visible response, logs, or durable artifact

### Non-requirement: response/schema version

The reviewed implementation and fixtures use visual response version `2`, and the generated UI type declares `Version = 2`. This change does not alter or introduce a response/schema version. Any future version change MUST be documented and coordinated with the authoritative backend schema and generated types rather than inferred from board-editing behavior.
