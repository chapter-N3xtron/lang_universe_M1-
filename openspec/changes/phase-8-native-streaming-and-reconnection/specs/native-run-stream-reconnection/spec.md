## Purpose

Provide safe native run streaming and browser reconnection for durable Jasper threads without exposing privileged Coder internals or coupling run survival to a browser connection.

## ADDED Requirements

### Requirement: Durable Jasper thread identity
The system SHALL assign and reuse a durable Agent Server thread ID for each Jasper conversation, and SHALL use that identity for submissions, history retrieval, active-run discovery, and reconnection rather than treating a browser connection as the conversation identity.

#### Scenario: Conversation is reopened
- **WHEN** a user reopens an existing Jasper conversation in a new browser mount
- **THEN** the client reconnects to the same server thread ID and presents that thread's authoritative conversation state

#### Scenario: New conversation receives durable identity
- **WHEN** a user starts a new Jasper conversation
- **THEN** the system creates or obtains a server thread ID before relying on the conversation for resumable execution

### Requirement: Native run and thread streaming
The system SHALL use the supported native Agent Server streaming contract and the Agent Chat UI native stream client for Jasper messages, run lifecycle state, and deliberately selected progress events rather than maintaining a parallel application-specific chat stream.

#### Scenario: Jasper response streams
- **WHEN** an authorized Jasper run emits user-visible message chunks
- **THEN** the client incrementally presents those chunks through the native thread stream and reconciles them with the authoritative completed message

#### Scenario: Stream reaches terminal state
- **WHEN** a Jasper run completes, fails, is interrupted for approval, or is explicitly cancelled
- **THEN** the client presents the corresponding native terminal or interrupt state without inventing a second run lifecycle

### Requirement: Reconnect to an active or resumable run
The system SHALL reconnect on mount, or use a documented native equivalent, when the durable thread has an active or resumable run. Reconnection SHALL attach to the existing run or thread stream and SHALL NOT submit a duplicate run.

#### Scenario: Browser reload during active work
- **WHEN** the browser reloads while an authorized run remains active
- **THEN** the remounted client discovers and reconnects to that run on the durable thread without creating another run

#### Scenario: Reconnect races with completion
- **WHEN** a run completes between active-run discovery and stream attachment
- **THEN** the client converges on the thread's authoritative completed state without resubmitting the user input

#### Scenario: No resumable run exists
- **WHEN** the client mounts an existing thread with no active or resumable run
- **THEN** it loads authoritative thread state and does not start a run solely because reconnection was requested

### Requirement: Browser disconnect does not imply cancellation
The server SHALL keep authorized autonomous work independent of the browser stream lifetime. Loss or closure of the browser connection SHALL NOT by itself cancel, interrupt, roll back, or duplicate the authorized run; cancellation SHALL require an explicit authorized cancellation action or an existing server-side terminal policy.

#### Scenario: Network connection drops
- **WHEN** the browser loses its stream connection during authorized autonomous work
- **THEN** the server continues the run subject to its existing authorization, interrupt, timeout, and cancellation policies

#### Scenario: User explicitly cancels
- **WHEN** an authorized user issues the existing explicit cancellation action
- **THEN** the server applies cancellation according to the native run lifecycle rather than treating it as an ordinary disconnect

### Requirement: Event replay is distinct from checkpoint durability
The system SHALL document and implement checkpoint recovery and stream-event replay as separate guarantees. Checkpoints SHALL provide durable graph/thread state but SHALL NOT be represented as proof that every prior stream event can be replayed.

#### Scenario: Replay is supported and cursor is retained
- **WHEN** a reconnecting transport supports event cursors and the client supplies the last received event ID within the replay window
- **THEN** the stream resumes after that event without intentionally duplicating earlier replayable events

#### Scenario: Replay is unavailable or expired
- **WHEN** event replay is unsupported, the last event ID is unavailable, or the replay retention window has expired
- **THEN** the client reloads authoritative thread and run state, clearly converges to the current state, and does not claim that transient missed events were recovered

#### Scenario: Checkpoint exists without replay log
- **WHEN** durable checkpoint state exists but replayable stream events do not
- **THEN** run recovery uses checkpoint/thread state while transient progress gaps remain non-authoritative and do not become fabricated transcript entries

### Requirement: Deliberate event exposure and transcript projection
The server SHALL deliberately configure subgraph and custom-event streaming and SHALL project only Jasper user-visible messages plus an allowlist of bounded, approved Coder progress events to the browser. The browser SHALL add only user messages and Jasper user-visible messages to the conversation transcript.

#### Scenario: Approved Coder progress is emitted
- **WHEN** authorized Coder work emits an allowlisted progress event with approved public fields
- **THEN** the client may display that bounded progress as non-transcript run activity associated with the Jasper run

#### Scenario: Subgraph event is not allowlisted
- **WHEN** a Coder or other subgraph emits an event that is not explicitly classified as user-visible progress
- **THEN** the server omits it from the browser-visible stream regardless of client behavior

#### Scenario: Jasper publishes a Coder outcome
- **WHEN** Coder work finishes and Jasper produces a user-facing synthesis
- **THEN** only Jasper's user-visible message is appended to the transcript, not the raw Coder report

### Requirement: Sensitive internal content never enters the user stream
The server SHALL exclude raw Coder reports, chain-of-thought or internal reasoning, unapproved model output, tool call arguments and results, prompts, credentials, tokens, environment values, and other secrets from browser-visible transcript and progress events. Redaction at the UI SHALL NOT be the security boundary.

#### Scenario: Internal tool event contains sensitive data
- **WHEN** a tool or subgraph event contains a secret or internal payload
- **THEN** the server does not publish that payload on the user-facing stream or persist it as a user transcript message

#### Scenario: Progress event contains extra fields
- **WHEN** a nominal progress event includes fields outside the approved public schema
- **THEN** the server drops the extra fields or rejects the event before browser delivery

### Requirement: Jasper-only user interface with server-enforced Coder boundary
The user-facing chat SHALL remain fixed to Jasper and SHALL NOT offer Coder as a selectable assistant. The server SHALL authorize assistant and subgraph access so a client cannot bypass Jasper by changing assistant, graph, thread, run, or event-stream identifiers.

#### Scenario: User opens chat
- **WHEN** the Agent Chat UI is mounted
- **THEN** Jasper is the fixed conversational assistant and no assistant dashboard or Coder selector is introduced

#### Scenario: Client requests Coder directly
- **WHEN** a browser client attempts to create, join, or stream a Coder run outside an authorized Jasper delegation
- **THEN** the server denies the request without exposing Coder events or reports

#### Scenario: Client requests another user's thread or run
- **WHEN** a client presents a durable thread ID, run ID, or replay cursor it is not authorized to access
- **THEN** the server denies access before returning state or stream events

### Requirement: Existing approval behavior remains unchanged
The change SHALL preserve the current approval-mode default and the current generic inferred-routing approval behavior. Streaming, reconnecting, replaying, or remounting SHALL NOT grant approval, consume an approval twice, bypass a pending interrupt, or introduce a new route-specific approval default.

#### Scenario: Generic inferred routing requires approval
- **WHEN** existing generic inferred-routing rules require approval for a Jasper-to-Coder action
- **THEN** the same approval is required after this change and neither stream attachment nor reconnection satisfies it

#### Scenario: Reconnect while approval is pending
- **WHEN** the browser reconnects to a run interrupted for approval
- **THEN** the pending approval state is presented without automatically resuming or cancelling the run

#### Scenario: Existing default is used
- **WHEN** no explicit approval-mode override is supplied
- **THEN** the same approval-mode default in effect before this change remains in effect
