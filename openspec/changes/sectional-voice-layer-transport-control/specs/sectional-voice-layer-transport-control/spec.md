## Purpose

Provide a shared, user-controlled frontend playback contract for completed assistant answers and speakable sections while retaining the existing Pocket TTS streamed PCM transport and protecting conversation navigation.

## ADDED Requirements

### Requirement: Stage 1 latest-answer transport
The frontend SHALL expose a bottom play/stop control beside the microphone for the latest completed assistant answer. Play SHALL enqueue that answer as one ordered playback request, and stop SHALL cancel all active and queued playback owned by the controller. Empty, loading, failed, or incomplete answers SHALL not be playable.

#### Scenario: Play latest completed answer
- **WHEN** a latest completed assistant answer contains speakable text and the user activates the bottom play control
- **THEN** the controller starts or queues one whole-answer playback session and exposes its active/queued/stopped state to all controller surfaces

#### Scenario: Empty or incomplete answer
- **WHEN** the latest answer is empty, loading, failed, or still streaming
- **THEN** the bottom control is disabled or unavailable and no TTS request is started

#### Scenario: Stop
- **WHEN** the user activates stop from the bottom control or another shared control
- **THEN** active audio is stopped, queued items are canceled, and all surfaces report idle/stopped without changing conversation scroll position

### Requirement: Sequential section playback
In Stage 2, the frontend SHALL identify ordered speakable sections in a completed assistant answer and SHALL support sequential playback in document order. Each section SHALL have a stable section identity scoped to a stable message identity and a per-section play/stop control.

#### Scenario: Whole answer advances through sections
- **WHEN** whole-answer playback is started for an answer with multiple speakable sections
- **THEN** sections are played exactly once in document order and the controller advances only after the current section completes successfully

#### Scenario: Section control starts one section
- **WHEN** the user activates a section play control while the controller is idle
- **THEN** only that section is selected for playback and its state is reflected by bottom, message-level, and section surfaces

#### Scenario: Section ordering survives rerender
- **WHEN** the answer rerenders without changing its stable message identity or section content identity
- **THEN** playback order and section identities remain deterministic and are not duplicated

### Requirement: Shared controller state and commands
Bottom, message-level, section, keyboard, and macro-key controls SHALL dispatch through one shared controller state. No surface SHALL maintain an independent audio session or infer transport state solely from its own local rendering.

#### Scenario: Equivalent controls
- **WHEN** play, stop, or supported future transport actions are invoked from any supported surface, keyboard shortcut, or macro key
- **THEN** the same controller transition occurs and every surface receives the same active item, queue, error, and idle state

#### Scenario: Visualization narration boundary
- **WHEN** an existing visualization-node narration action is used
- **THEN** it remains a related existing capability and does not silently become a second queue or a separate implementation of this shared answer/section controller

### Requirement: Section selection replaces whole-answer playback
Selecting a section during whole-answer playback SHALL explicitly stop and replace the current whole-answer queue with the selected section. Previously active audio and not-yet-played sections SHALL not resume afterward unless the user starts whole-answer playback again.

#### Scenario: Section selected during whole-answer playback
- **WHEN** section B is selected while whole-answer playback is playing section A or queued sections remain
- **THEN** the controller cancels A, clears the whole-answer queue, starts B as the sole selected item, and marks the replacement generation authoritative

#### Scenario: Stale completion after replacement
- **WHEN** a completion/error callback from A or the replaced queue arrives after section B is selected
- **THEN** the callback is ignored and cannot stop B, advance the queue, or overwrite B's state

### Requirement: Transport and audio error behavior
The controller SHALL treat `/api/tts/stream` as an SSE stream of base64 PCM chunks and SHALL preserve that endpoint and its contract unless later evidence proves a backend change necessary. SSE failures, malformed/undecodable PCM, AudioContext failures, and playback interruption SHALL stop or fail the affected item deterministically, clear unsafe queued work as defined by the active command, and expose an actionable non-secret error state.

#### Scenario: SSE stream error
- **WHEN** the endpoint emits an error, closes unexpectedly, or yields an invalid chunk
- **THEN** the affected item enters an error/stopped state, no stale callback advances another generation, and the user can retry or stop through the shared controller

#### Scenario: Audio capability failure
- **WHEN** the browser cannot create/resume the required audio path
- **THEN** playback does not silently claim success, controls expose the failure, and conversation content and scroll position remain unchanged

### Requirement: Stable identities and replacement generations
Every playback item SHALL be addressable by a stable message ID, a stable section ID scoped to that message, and a controller generation/session ID. IDs SHALL be derived from durable message identity plus deterministic section order/content identity, not from array position alone, and SHALL remain frontend ephemeral metadata rather than durable playback records.

#### Scenario: New message overlaps playback
- **WHEN** a new user or assistant message arrives while an older answer is playing
- **THEN** the current policy is applied deterministically: existing playback continues for its stable item unless the user invokes replacement/stop, and the new message is not inserted into the old queue

#### Scenario: Message replacement
- **WHEN** the source answer changes identity or is replaced by a newer completed answer
- **THEN** items belonging to the old identity cannot receive new queue entries or mutate the new identity's state

### Requirement: Markdown sectionization has explicit boundaries
Stage 2 sectionization SHALL treat Markdown headings and paragraphs as candidate boundaries, preserve source order, trim surrounding whitespace, and omit sections with no speakable text. The design SHALL explicitly label policies for lists, code, tables, math, tool output, and streaming partial content as resolved or unresolved before implementation; unresolved policies SHALL not be silently treated as acceptance criteria.

#### Scenario: Headings and paragraphs
- **WHEN** a completed answer contains headings and paragraphs
- **THEN** headings and their associated speakable content are emitted in deterministic source order with stable section IDs

#### Scenario: Unsupported or unresolved block types
- **WHEN** an answer contains a list, code block, table, math, tool output, or streaming partial block whose policy is unresolved
- **THEN** the implementation does not invent spoken content silently; the item is excluded, represented as explicitly unsupported, or held behind a documented decision

#### Scenario: Partial streaming content
- **WHEN** an answer is still streaming
- **THEN** section playback is not accepted as final content and no completed-answer queue is built from partial content

### Requirement: Optional pause/resume is evidence-gated
True pause/resume SHALL NOT be an initial acceptance requirement. It MAY be designed as a future command only after browser and audio verification demonstrates reliable pause/resume semantics for streamed PCM and safe restart behavior; stop/cancel remains the initial interruption contract.

#### Scenario: No pause evidence
- **WHEN** browser/audio verification has not established reliable pause/resume
- **THEN** the controller exposes stop rather than claiming pause/resume support

#### Scenario: Verified future pause
- **WHEN** a later evidence review proves pause/resume safe and the capability is separately approved
- **THEN** pause/resume can be added without weakening stop, replacement, stale-callback, or accessibility guarantees

### Requirement: Keyboard and macro actions use human-control safeguards
Supported keyboard shortcuts and macro-key actions SHALL route to the same controller commands as visible controls, provide an accessible name and state announcement, and SHALL not trigger playback unexpectedly while focus is in text entry unless explicitly configured.

#### Scenario: Keyboard stop
- **WHEN** the user invokes the documented keyboard stop action
- **THEN** the shared controller stops the same active and queued items as the visible stop control

#### Scenario: Macro action while composing
- **WHEN** a macro key is pressed while the user is typing in a text-entry control and the action is not explicitly opted into there
- **THEN** it does not start or replace playback

### Requirement: Playback preserves conversation navigation
Playback, queue transitions, audio callbacks, and control state updates SHALL NOT change conversation scroll position, trigger automatic placement, or interfere with scroll anchoring. The implementation SHALL cross-reference `conversation-scroll-anchoring` and remain separate from `manual-scroll-observation-capture`.

#### Scenario: Playback while scrolled
- **WHEN** playback starts, advances, errors, or stops while the user is at any conversation scroll position
- **THEN** the scroll position and anchoring state remain unchanged except for an independently initiated human scroll

#### Scenario: Control rerender
- **WHEN** bottom, message-level, or section controls rerender as playback state changes
- **THEN** no focus jump, layout-induced scroll, or automatic message placement occurs

### Requirement: No durable interaction state
The controller SHALL keep playback queue, active item, generation, cancellation, and error state ephemeral to the frontend session. It SHALL not add durable playback records or LangGraph checkpoint state.

#### Scenario: Reload or checkpoint
- **WHEN** the page reloads or a LangGraph checkpoint is written
- **THEN** no playback session is restored or persisted as a durable interaction record

### Requirement: Staged acceptance and branch placement
Stage 1 SHALL be eligible for the stable bottom-locking branch only after its latest-answer, stop, error, keyboard/macro, accessibility, and no-scroll criteria pass. Stage 2 sectionization and per-section transport SHALL remain in the experimental branch until section boundary policies, queue/replacement behavior, and browser/audio evidence pass; future pause/resume remains outside both initial acceptance gates.

#### Scenario: Stage 1 gate
- **WHEN** Stage 1 verification is reviewed
- **THEN** stable placement is permitted only with passing deterministic controller, transport error, human-control, and no-scroll evidence

#### Scenario: Stage 2 gate
- **WHEN** Stage 2 verification is incomplete or section policies remain unresolved
- **THEN** section controls are not promoted to the stable bottom-locking branch
