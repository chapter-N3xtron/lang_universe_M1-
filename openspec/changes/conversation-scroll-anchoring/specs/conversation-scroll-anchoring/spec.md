## Purpose

Provide deterministic, user-respecting conversation placement so each intended message target is aligned once at the real usable viewport top without clipping visible headers or controls.

## ADDED Requirements

### Requirement: Hydration places the latest completed visible message once

On successful reopen or hydration of a non-empty conversation, the system SHALL identify the latest completed visible message and top-align its visible message shell/header exactly once. It SHALL not place an empty, loading-only, hidden, or incomplete target.

#### Scenario: Non-empty history hydrates
- **WHEN** a saved conversation finishes hydration with a latest completed visible message
- **THEN** the visible shell/header of that message is top-aligned once with the conversation viewport's usable content-top edge, including the real rendered layout/control inset

#### Scenario: Empty or unsuccessful hydration
- **WHEN** hydration produces no visible completed message or produces a loading/error state
- **THEN** the system performs no automatic placement until a successful non-empty hydrated target exists

### Requirement: Submission and assistant completion use replacement placement

After a new user message is submitted, the system SHALL top-align that visible user message exactly once. When the corresponding assistant response completes, the system SHALL replace that placement by top-aligning the completed visible assistant message exactly once. Streaming chunks and assistant loading renders SHALL not count as completion or trigger additional placement.

#### Scenario: Submitted user message
- **WHEN** a new user message becomes the submitted turn's visible message
- **THEN** the system performs exactly one automatic top placement for that visible user message

#### Scenario: Assistant response completes
- **WHEN** the submitted turn's assistant response transitions from streaming/loading to completed and is visible
- **THEN** the system performs exactly one replacement top placement for the completed visible assistant message and performs no further automatic placement for that turn

#### Scenario: Streaming content grows
- **WHEN** assistant chunks, answer reveal, or other content updates change the in-progress response before completion
- **THEN** the system does not repeat or replace the already-consumed user placement and does not place the incomplete assistant response

### Requirement: Placement uses the real usable top and visible target geometry

Every automatic placement SHALL align the target's visible message shell/header top edge exactly with the conversation viewport's measured usable content-top edge, including any actual layout/control inset. A hard-coded inset SHALL NOT define the destination, and an invisible inner anchor SHALL NOT be the placement target. The target header/top content and its playback/command controls SHALL be fully within the visible conversation viewport; no target header/top content or control may be clipped above it. For a target taller than the viewport, the header and top of the message SHALL be visible even though the complete response cannot fit.

#### Scenario: Target has layout/control inset
- **WHEN** a target is placed in a viewport whose rendered controls or layout create a non-zero content-top inset
- **THEN** the target shell/header top equals the measured usable content-top edge, not a fixed pixel approximation

#### Scenario: Visible shell and controls
- **WHEN** a user or assistant target is automatically placed
- **THEN** geometry shows the visible shell/header, top content, and playback/command controls are on-screen, with none clipped above the usable viewport top

#### Scenario: Target is taller than the viewport
- **WHEN** the target message height exceeds the usable viewport height
- **THEN** its header and top content are visible at the usable top edge, without requiring the entire response to fit

### Requirement: Human movement cancels pending automatic placement

Wheel, touch, pointer/scrollbar movement, keyboard scrolling, text selection or drag movement, and other human-generated movement SHALL cancel a pending automatic placement. After cancellation, the system SHALL preserve the user's position and SHALL NOT reclaim scroll control for that pending event.

#### Scenario: User moves by wheel, touch, keyboard, scrollbar, or selection
- **WHEN** any listed human movement occurs before an automatic placement is consumed
- **THEN** the pending placement is canceled and no automatic scroll occurs for that event

#### Scenario: User scrolls after placement
- **WHEN** the user moves the conversation after a placement has completed
- **THEN** the conversation remains under user control and does not bottom-follow or reposition itself

### Requirement: Placement is one-shot across non-semantic changes

A consumed placement SHALL NOT repeat because of streaming chunks, resizes, rerenders, reduced-motion preference, answer reveal, or layout/DOM mutations. Reduced motion SHALL change only animation, if any, while preserving the same destination and one-shot behavior.

#### Scenario: Resize or layout mutation
- **WHEN** the viewport resizes or layout/DOM mutations occur after a placement request is pending or consumed
- **THEN** the request waits only for its first valid measured placement and then remains consumed without a repeat

#### Scenario: Rerender or reduced motion
- **WHEN** the target rerenders or reduced-motion mode is active
- **THEN** placement remains exactly once and uses the same usable-top destination, with instant/no animation permitted under reduced motion

### Requirement: Verification proves browser-visible behavior

The implementation SHALL remain pending until focused browser verification proves hydration, submission, and real assistant streaming-to-completion placement separately. Verification SHALL assert exact shell/header geometry, visible controls, clipping bounds, tall-message behavior, one-shot counts, and human cancellation. Observation evidence from `manual-scroll-observation-capture` SHALL be explicitly cross-referenced and reported separately; it SHALL not substitute for these assertions.

#### Scenario: Full verification matrix
- **WHEN** the change is reported as implemented
- **THEN** automated evidence includes hydrated latest-message placement, submitted-user placement, real streamed assistant completion replacement, shell/header/control rectangles, no-clipping checks, tall target behavior, reduced motion, resize/mutation/rerender deduplication, and each cancellation input

#### Scenario: Companion observation review
- **WHEN** implementation or verification is opened
- **THEN** `../manual-scroll-observation-capture/` is reviewed as the companion observation workflow, without modifying it or claiming its capture alone proves the contract
