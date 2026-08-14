## Purpose

Anatomy of a Session defines an Inquiry-oriented body of work whose assembled materials and durable user-authored Perspective remain intelligible, attributable, and revisitable over time.

## ADDED Requirements

### Requirement: Inquiry-oriented session body of work
The system SHALL represent a session as an Inquiry-oriented body of work rather than only an ordered conversation transcript. A session SHALL be able to associate materials assembled in the inquiry and retain enough artifact identity, source/provenance status where applicable, and session relationship information for the user to distinguish the materials that informed their work.

#### Scenario: User reviews an inquiry with assembled materials
- **WHEN** a user revisits a session containing multiple inquiry materials
- **THEN** the session SHALL present those materials as associated with the same Inquiry-oriented body of work rather than representing them only as undifferentiated chat messages

#### Scenario: Session contains sourced and user-created materials
- **WHEN** a session includes sourced research material and a user-created artifact
- **THEN** the session SHALL retain their distinguishable artifact identities and applicable source/provenance status

### Requirement: Recognized session artifact categories
The system SHALL support associating visualizations or charts, PDFs, research outputs, polls, and a durable Perspective with an Inquiry-oriented session. Research outputs SHALL include links, saved pages, reports, and research-pass reports as distinguishable forms. The recognized categories do not require every session to contain every form and do not limit future session materials that conform to the session’s provenance and relationship boundaries.

#### Scenario: Inquiry combines several artifact forms
- **WHEN** a user assembles a chart, a PDF, a saved page, a research report, a research-pass report, and a poll during an inquiry
- **THEN** the session SHALL be able to associate each material with that session using its applicable recognized artifact form

#### Scenario: Inquiry has no poll or PDF
- **WHEN** a session contains only a research link and a Perspective
- **THEN** the session SHALL remain a valid Inquiry-oriented body of work without implying that a poll, PDF, chart, or other absent artifact was created

### Requirement: Durable user-authored Perspective
The system SHALL provide a durable Perspective associated with a session that records the user’s current understanding, conclusion, decision, or stance based on the materials they have assembled. The Perspective SHALL be identified as user-authored; the system SHALL NOT attribute a model-generated summary, research report, poll result, visualization, or decision-tool output to the user as their Perspective without the user’s authorship.

#### Scenario: User records a current conclusion
- **WHEN** the user authors a statement of their current conclusion after reviewing session materials
- **THEN** the system SHALL retain that statement as the session’s user-authored Perspective and distinguish it from the underlying materials and generated outputs

#### Scenario: Generated material is available but not adopted
- **WHEN** a session contains a generated summary, report, poll result, visualization, or decision-tool output that the user has not authored as Perspective
- **THEN** the system SHALL retain the material without labeling or presenting it as the user’s Perspective

### Requirement: Reopened session history is initially latest-oriented

When a previously saved session/thread is reopened for revisitation, its hydrated non-empty message history SHALL initially place the conversation at the bottom once, after the hydrated message window is mounted, so the most recently said content is visible. This is initial restore placement only: it SHALL NOT bottom-follow new processing or assistant-answer reveal, repeatedly reclaim the viewport, or override subsequent user scrolling. Empty sessions have no placement target; loading or history errors wait for successful hydration; forked/reopened threads use the same default; reduced motion uses instant/no animation. A future explicit durable per-thread viewport position may override this default only if separately introduced, and this change does not define that feature.

#### Scenario: User reopens an inquiry thread
- **WHEN** a user revisits a saved session with hydrated messages
- **THEN** the conversation initially shows the latest saved content at the bottom once, while the user retains normal scroll control afterward

#### Scenario: Session revisitation has no usable history
- **WHEN** the session is empty, still loading, or history hydration errors
- **THEN** it does not perform a misleading placement and presents the applicable empty, loading, or error state

### Requirement: Perspective revisitation and revision
The system SHALL allow the user to revisit and update their durable Perspective as the inquiry develops. An updated Perspective SHALL represent the user’s then-current understanding, conclusion, decision, or stance and SHALL NOT be treated as evidence that the earlier Perspective was erroneous, that the user must maintain the update, or that the inquiry has reached a final answer.

#### Scenario: New material changes the user’s understanding
- **WHEN** the user revisits a session after assembling new or reconsidered material and updates their Perspective
- **THEN** the session SHALL retain the updated user-authored Perspective as their current view without preventing later revision

#### Scenario: User leaves a Perspective unchanged
- **WHEN** a user reviews additional session material and chooses not to update their Perspective
- **THEN** the system SHALL preserve the existing Perspective without inferring agreement, finality, authorization, or a required decision

### Requirement: Non-prescriptive illustrative inquiry support
The system SHALL permit sessions and Perspectives to support learning, dense-text or scientific inquiry, social or political perspective formation, voting considerations, and decision-tool outputs as illustrative uses. For social or political inquiry and voting considerations, the system SHALL present materials and Perspective as support for the user’s own deliberation and SHALL NOT prescribe, infer, or represent a political conclusion, candidate preference, vote, or stance as the user’s own.

#### Scenario: User considers a voting-related inquiry
- **WHEN** a user assembles materials and records a Perspective while considering a vote
- **THEN** the session SHALL preserve the user-authored Perspective and associated materials without prescribing or asserting a candidate preference, vote, or political conclusion for the user

#### Scenario: User uses decision-tool output during scientific inquiry
- **WHEN** a user associates a decision-tool output with dense scientific materials and records or revises a Perspective
- **THEN** the system SHALL retain the decision-tool output as material distinct from the user-authored Perspective and allow the user to determine whether it informs their current view

### Related model-use boundary
Model-use records and selected-versus-actual model metadata are governed by `../durable-interaction-records/` and `../model-selection-and-stewardship/`. A user-authored Perspective SHALL remain distinct from any generated recommendation, including a recommendation about model choice.
