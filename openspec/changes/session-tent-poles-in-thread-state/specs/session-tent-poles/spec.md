## Purpose

Define human-approved session tent poles as structured, authoritative LangGraph state for one thread, with same-thread reads, separately approved installation-wide Store promotion, and reversible legacy compatibility.

## ADDED Requirements

### Requirement: Structured tent poles are authoritative thread state

The system SHALL represent human-approved session tent poles in the current LangGraph thread's checkpointed `tent_poles` state channel. Each tent pole MUST contain exactly the proposed business fields `id`, `content`, `priority`, and `approved_at`: `id` MUST be a non-empty immutable opaque identifier unique within the thread, `content` MUST be non-empty human-approved text, `priority` MUST be an integer, and `approved_at` MUST be a timezone-aware ISO-8601 approval timestamp. The list MUST contain no more than 20 records and MUST use complete-list replacement rather than append semantics. Lower `priority` values SHALL order first, with `id` as the deterministic tie-breaker.

#### Scenario: Human approves a structured replacement

- **WHEN** the human explicitly approves a valid complete list for the authoritative thread
- **THEN** the system SHALL checkpoint that structured list in the same thread and SHALL expose the same IDs, content, priorities, approval timestamps, and deterministic order on readback

#### Scenario: Update exceeds the retained limit

- **WHEN** an attempted replacement contains more than 20 tent poles
- **THEN** the system MUST reject the complete replacement and MUST leave the previously authoritative thread-state list unchanged

#### Scenario: Model or tool proposes tent-pole text

- **WHEN** a model, workflow, or tool produces candidate tent-pole content without the human's explicit approval of the complete replacement
- **THEN** the system MUST NOT write or label that content as an approved thread tent pole

### Requirement: State presence controls compatibility fallback

The system SHALL distinguish an absent `tent_poles` state key from a present list. A present valid list SHALL be authoritative even when it is empty. Legacy fallback MUST be consulted only when the state key is absent. A present but invalid value MUST fail closed and MUST NOT silently reveal or substitute legacy values.

#### Scenario: Explicitly empty state is authoritative

- **WHEN** the human explicitly approves an empty list and the current thread state contains `tent_poles: []`
- **THEN** the system SHALL return no tent poles and MUST NOT repopulate values from LangGraph Store session records or `session_catalog.tent_poles`

#### Scenario: New state key is absent on a legacy thread

- **WHEN** an existing thread has no `tent_poles` state key
- **THEN** the system SHALL return preserved legacy tent poles through the compatibility fallback according to the approved legacy precedence and MUST NOT synthesize an empty authoritative state value merely because one legacy source has no rows

#### Scenario: Present state is malformed

- **WHEN** the current thread contains a `tent_poles` key that violates the structured contract
- **THEN** the system MUST report a validation or migration failure and MUST NOT fall back to a stale legacy list

### Requirement: Tent-pole reads are isolated to the executing thread

A workflow or tool SHALL read tent poles only from the state of its authoritative executing thread. The read interface MUST NOT accept a model- or tool-controlled target `thread_id`, `session_id`, owner, Store namespace, Store key, or search query. The system MUST verify authoritative runtime thread identity and MUST NOT permit one thread to inspect another thread's tent poles.

#### Scenario: Same-thread workflow reads tent poles

- **WHEN** a workflow or tool executes in thread A and requires approved tent poles
- **THEN** it SHALL receive thread A's effective authoritative list from current state, or the compatibility fallback only if thread A's state key is absent

#### Scenario: Same owner requests another thread's values

- **WHEN** code executing for thread B attempts to request thread A's tent poles, even though both threads have the same owner or repository binding
- **THEN** the system MUST deny the cross-thread read without revealing thread A's tent-pole existence or content

#### Scenario: Fork reads copied state

- **WHEN** a forked thread contains tent poles in its own copied checkpoint state
- **THEN** it SHALL read only that local snapshot and MUST NOT gain ongoing lookup authority over the parent thread

### Requirement: Installation-wide promotion requires separate Store-write approval

Approval of a thread tent pole SHALL authorize only the same thread's checkpointed state update. It MUST NOT authorize a LangGraph Store write, update, index, or delete. Any promotion to installation-wide memory MUST be a separate operation with fresh explicit human approval of the exact source thread, tent-pole ID and content, destination Store namespace/key, installation-wide audience, and proposed write. Changed inputs MUST invalidate the approval.

#### Scenario: Tent pole is approved for one thread

- **WHEN** the human approves or updates tent poles for a session thread
- **THEN** the system SHALL update only that thread state and MUST perform no installation-wide Store mutation

#### Scenario: Human separately approves installation-wide promotion

- **WHEN** the human reviews and explicitly approves the exact promotion operation
- **THEN** the promotion operation SHALL write only the approved value to the approved Store destination with source provenance and MUST NOT treat later thread edits as approval to rewrite the promoted item

#### Scenario: Promotion is rejected, abandoned, or changed

- **WHEN** promotion is rejected, abandoned, missing approval, replayed after use, or has changed source content or destination
- **THEN** the system MUST perform no Store write and MUST require a new exact approval for any later attempt

### Requirement: Legacy records and compatibility remain preserved

The migration SHALL preserve every existing tent-pole value in legacy LangGraph Store session records and every row in `session_catalog.tent_poles`. New authoritative approvals MUST NOT overwrite or delete those legacy records. The compatibility fallback MUST remain available for state-absent threads until state migration readback and rollback have both been verified. This change MUST NOT authorize table deletion, legacy cleanup, or fallback removal.

#### Scenario: State-backed read succeeds after migration

- **WHEN** a migrated thread's complete structured list passes direct state readback and effective-reader comparison
- **THEN** state SHALL be authoritative for that verified thread while its legacy Store values and table rows remain unchanged

#### Scenario: Migration has not been verified

- **WHEN** a thread has not passed readback and rollback verification
- **THEN** the system MUST retain its legacy compatibility path and MUST NOT delete, truncate, or rewrite its Store or table records

#### Scenario: New approved state differs from frozen legacy data

- **WHEN** the human approves a new state list after state authority is enabled
- **THEN** the effective read SHALL return the new state list while the frozen legacy records remain preserved and non-authoritative

### Requirement: Migration is evidence-based and reversible

Migration MUST be dry-run first, deterministic, resumable, bounded by authoritative owner/thread identity, and explicitly approved by cohort. It SHALL preserve legacy content and order, map legacy table `position` to `priority`, derive stable deterministic IDs from stable legacy identity, and use only an evidenced human-approval timestamp for `approved_at`. It MUST report disagreements, malformed data, duplicate or over-limit values, missing approval evidence, and owner/thread mismatches. It MUST leave ambiguous or Store-only records on compatibility fallback rather than inventing required fields or human attribution.

#### Scenario: Legacy table rows have sufficient evidence

- **WHEN** owner/thread identity, content, position, human-reviewed source, and approval timestamp are unambiguous and the cohort is approved
- **THEN** migration SHALL write one deterministic complete state list, preserve content order through priority, and produce repeatable IDs and timestamps on retry

#### Scenario: Legacy record lacks approval timestamp or attribution evidence

- **WHEN** migration cannot establish a required structured field without invention
- **THEN** it MUST leave the record unchanged on legacy fallback, report it as unresolved, and MUST NOT write a fabricated structured tent pole

#### Scenario: Readback or rollback verification fails

- **WHEN** direct state readback, effective compatibility comparison, isolation checks, explicit-empty checks, or rollback fallback parity fails
- **THEN** rollout MUST stop, the affected cohort MUST return to preserved legacy fallback, new state writes MUST be disabled where safe representation cannot be proven, and no legacy record or table SHALL be deleted

### Requirement: Scope remains limited to tent-pole authority planning

This change SHALL NOT itself modify implementation, databases, deployment, existing OpenSpec changes, or unrelated files. Any future implementation under this contract MUST NOT include table deletion, legacy-record deletion, document-linking behavior, general UI changes, or unrelated session/artifact behavior.

#### Scenario: Planning change is reviewed

- **WHEN** this OpenSpec change is validated or approved
- **THEN** the result SHALL be a planning contract only and MUST NOT be represented as implemented, deployed, migrated, or safe for legacy cleanup

#### Scenario: Adjacent feature is proposed during implementation

- **WHEN** document linking, general UI redesign, table deletion, or unrelated session behavior is requested alongside this work
- **THEN** it MUST be excluded and handled through a separate explicitly approved change
