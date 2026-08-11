## Purpose

Record the observed unresolved conversation-scroll behavior and define the proposed user-visible contract for one-shot top positioning after newly inserted turns settle in the browser.

## Companion observation change

Review `../../manual-scroll-observation-capture/` whenever this capability is opened or implemented. This capability defines the behavior under test; the companion defines optional human-centered evidence capture used to observe and report it. The companion must not be treated as implementation of, or proof of, these requirements, and both changes must remain in scope review together.

## ADDED Requirements

### Requirement: Current scroll behavior remains explicitly pending

The current implementation SHALL be documented as unresolved: assistant answers are not reliably top-anchored, and newly submitted user messages do not reliably auto-scroll into view at their top position. Passing automated checks SHALL NOT be treated as proof that the real browser visual behavior is complete, because those checks did not sufficiently verify the rendered interaction.

#### Scenario: Assistant answer arrives
- **WHEN** a newly inserted assistant answer is rendered in the conversation
- **THEN** the record SHALL distinguish the observed unreliable top anchoring from a completed implementation and SHALL mark live-browser verification pending

#### Scenario: User message is submitted
- **WHEN** a newly submitted user message is inserted into the conversation
- **THEN** the record SHALL distinguish the observed unreliable auto-scroll into view from a completed implementation and SHALL mark live-browser verification pending

### Requirement: Proposed one-shot top positioning contract

The proposed new-arrival behavior SHALL position each newly inserted user message and completed assistant answer at the top of the conversation viewport once insertion and layout settlement are complete. This is distinct from initial reopen placement: it SHALL NOT be used as bottom-following during new message processing or assistant-answer reveal. After that one-shot positioning, the user SHALL have full scroll control; the conversation SHALL NOT continue following the bottom or repeatedly reposition itself as content arrives or as the answer is revealed.

#### Scenario: New turn settles after insertion
- **WHEN** a user message or assistant answer has been inserted and its layout has settled
- **THEN** the conversation SHALL perform one top-positioning action for that turn, then stop automatic repositioning

#### Scenario: User scrolls after positioning
- **WHEN** the user scrolls after the one-shot top positioning
- **THEN** the conversation SHALL preserve the user-selected scroll position and SHALL NOT bottom-follow or seize scroll control

### Requirement: Initial placement when reopening hydrated history

The clarified reopen behavior SHALL place the latest rendered message/response at the top of the conversation viewport once, but only after its hydrated message window is mounted. The top of that latest message SHALL align with the viewport's content top inset (32px in the current layout), rather than bottom-locking the conversation or opening at its absolute beginning. This is a one-time restore/reopen placement, not bottom-following, stream-following, or repeated viewport reclamation during new message processing or assistant-answer reveal. After placement, the user controls scrolling normally. A future explicitly saved per-thread viewport position MAY override this default only if that feature is separately introduced; no such durable position is defined here.

#### Scenario: Reopen a non-empty saved thread
- **WHEN** a previously saved session/thread is reopened and its non-empty hydrated message window is mounted
- **THEN** the conversation SHALL align the top of the latest rendered message/response with the viewport content top inset once, after mounting, without subsequently reclaiming the viewport

#### Scenario: Empty session
- **WHEN** a reopened session has no hydrated messages
- **THEN** the conversation SHALL perform no bottom placement and SHALL remain an empty-session view

#### Scenario: Loading or history error
- **WHEN** history is still loading or hydration fails
- **THEN** the conversation SHALL not perform a misleading initial placement; it SHALL show the applicable loading or error state and may place the viewport only after a successful hydrated message window is mounted

#### Scenario: Forked or reopened thread
- **WHEN** a forked thread or another saved thread is reopened with hydrated messages
- **THEN** it SHALL use the same one-time latest-message top placement, unless a future explicitly saved per-thread viewport position has been introduced and is available to override it

#### Scenario: Reduced motion
- **WHEN** reduced-motion preferences are active during initial reopen placement
- **THEN** the conversation SHALL use no animation or an instantaneous placement while preserving the same destination, one-time timing, and user scroll control

### Requirement: Both arrival paths require live-browser investigation

The implementation SHALL remain marked pending until live-browser investigation verifies both the newly submitted user-message arrival path and the arriving assistant-answer path, including visual timing after insertion and layout settlement. Automated checks MAY remain as supporting evidence but SHALL NOT replace this browser verification.

#### Scenario: Verification covers both paths
- **WHEN** implementation status is reported
- **THEN** it SHALL state separately whether live-browser behavior was verified for user-message arrival and assistant-answer arrival, and SHALL not call the work complete while either path remains unresolved
