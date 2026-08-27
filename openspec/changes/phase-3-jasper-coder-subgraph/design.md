## Context

See `proposal.md` for motivation and `specs/jasper-coder-subgraph/spec.md` for the behavior contract.

The observed topology has three relevant layers:

- `backend/src/chat_ui.py:357-361,596-604` constructs Coder and registers `jasper` and `coding` as sibling nodes in the outer graph.
- `backend/src/jasper_agent.py:178-213` implements `transfer_to_coding` as a `Command.PARENT` jump to that sibling, and `backend/src/chat_ui.py:420-505` performs a manual `coding_app.ainvoke(...)` plus ad hoc input/output projection.
- `backend/src/jasper_agent.py:992-998` exposes a compiled Jasper wrapper, while `backend/src/coding_agent.py:795-800` exposes the compiled Coder wrapper. Their state contracts differ (`backend/src/jasper_agent.py:82-118`; `backend/src/coding_agent.py:40-50`), especially message reducers and Jasper-only response/routing fields.

This phase assumes Phase 1 supplies the sole authoritative complete Coder graph construction boundary. Composition must remain persistence-neutral so Agent Server can inject the parent checkpointer at runtime. Phase 6 owns the future typed Coder report contract.

## Goals / Non-Goals

**Goals:**

- Move the Coder execution boundary inside Jasper's compiled graph and make Coder a directly composed LangGraph subgraph node.
- Make state translation reviewable and testable rather than relying on shared field names or whole-state merging.
- Preserve nested interrupt namespaces and parent-checkpointer inheritance.
- Leave one stable output projection seam where Phase 6 can later add its typed report.

**Non-Goals:**

- Defining Phase 6 report models, fields, validation, rendering, or failure taxonomy.
- Making Jasper orchestrate Coder's internal plan or tool loop.
- Sharing all Jasper and Coder state channels merely to simplify composition.
- Adding a separately addressable Coder surface or changing Agent Server registration.

## Decisions

### 1. Jasper owns a local Coder subgraph node

Expand Jasper's graph from its current one-node wrapper into an internal delegation graph containing the Jasper agent node, explicit mapping nodes, and the authoritative compiled Coder graph as a node. `transfer_to_coding` targets this local route instead of issuing `Command.PARENT` to an outer sibling. After Coder returns, control routes to Jasper's existing relay/finalization behavior or to Jasper's output boundary as appropriate.

The outer product graph no longer owns the coding execution node or `run_coding` manual invocation path. It treats the compiled Jasper graph as the user-facing agent boundary. This makes graph inspection, streaming namespaces, interrupts, and checkpoint lineage reflect actual nesting.

**Alternatives considered:**

- Keep the sibling and manual `ainvoke`: rejected because it is the topology being replaced and obscures nested durability semantics.
- Use `RemoteGraph` pointed at another graph in the same deployment: rejected because it adds a network/service boundary and separate-run semantics where direct local composition is required.
- Rebuild a Coder-like node inside Jasper: rejected because it would create a second, drifting authority.

### 2. Use a bridge graph with distinct input, internal, and output contracts

Wrap direct Coder composition in a small bridge `StateGraph` whose public input is a Jasper-to-Coder request contract, whose internal channels satisfy the authoritative Coder input/state schema, and whose public output is a Coder-to-Jasper result contract. The bridge performs three graph-visible steps:

1. An input adapter validates and projects the delegated task, workspace, model, execution mode, thread/user identity, and coding-session identity into Coder input channels.
2. The authoritative compiled Coder graph runs as a subgraph node. It is not called from adapter code with `ainvoke`.
3. An output adapter selects and normalizes only supported result channels: final Coder messages, status, coding-session identity, workspace, and execution manifest.

Use separate bridge channels for inbound Jasper messages/task and Coder working messages so `add_messages` and append-style reducers cannot combine histories implicitly. The output adapter explicitly excludes delegated input messages, tool-call transcripts, Coder-private working state, and Jasper-only response or visualization state. Existing user-facing attribution can remain `coding` until Phase 6 replaces or extends the output contract.

**Alternatives considered:**

- Depend on identically named keys and automatic shared-state merging: rejected because the schemas and reducers differ and accidental channel coupling would be difficult to audit.
- Invoke Coder from a custom mapping node: rejected because even with clean schemas it would preserve the manual invocation anti-pattern rather than register Coder as a genuine subgraph node.

### 3. Compile the nested Coder graph with `checkpointer=None`

The authoritative Coder builder is used in its default persistence-neutral form. The nested compilation passes no concrete saver and does not opt out with `checkpointer=False`; equivalently, its effective compile setting is `checkpointer=None`. LangGraph can therefore inherit the parent Agent Server checkpointer during each Jasper invocation and allocate nested namespaces for Coder checkpoints and interrupts.

Resume commands continue through the Jasper thread and parent graph. No adapter catches `GraphBubbleUp`, converts an interrupt into a normal error result, changes thread identifiers mid-run, or starts a fresh Coder invocation on resume.

**Alternatives considered:**

- `checkpointer=False`: rejected because it disables inherited nested persistence and breaks the durability requirement.
- A Coder-specific memory, SQLite, PostgreSQL, or other saver: rejected because it creates a second persistence authority and conflicts with runtime injection.
- A same-deployment remote run: rejected because its run/checkpoint lifecycle is not local subgraph inheritance.

### 4. Preserve Coder ownership of autonomous behavior

The bridge supplies boundary data and consumes boundary results only. It does not inspect Coder todos to drive steps, substitute Jasper tools, trim the authoritative tool set, or reproduce Coder execution-mode logic. Approval, autonomous operation, progress publication, completion formatting, execution manifests, and sanitized failures remain inside the authoritative graph.

Focused parity tests compare embedded behavior with the authoritative Coder boundary for representative read-only, approval, autonomous, and error paths. The tests assert topology and state projection in addition to final text so a regression cannot silently revert to manual invocation.

**Alternatives considered:**

- Let Jasper coordinate each Coder action: rejected because it reduces Coder autonomy and duplicates internal policy.

### 5. Reserve, but do not design, the Phase 6 report seam

Define the Coder-to-Jasper output adapter as the sole place where a later typed report can be projected. This phase maps current authoritative messages and status fields only. It introduces no provisional report model, report-field guesses, serialization rules, or Jasper presentation policy.

**Alternatives considered:**

- Add a temporary typed report now: rejected because Phase 6 explicitly owns those details and a temporary contract would create migration debt.

## Risks / Trade-offs

- **[Risk] Message reducers duplicate delegated input or tool history across the boundary** → Use distinct bridge channels and test exact input/output message sequences and attribution.
- **[Risk] A helper accidentally hides a manual `ainvoke` and appears to be subgraph composition** → Assert graph topology contains the authoritative compiled Coder subgraph and add a regression check that the Jasper-to-Coder path does not call a graph from an ordinary node.
- **[Risk] Interrupts are swallowed by error normalization** → Keep interrupt bubbling untouched and test interrupt plus same-thread resume through Jasper against a checkpointer supplied only to the parent.
- **[Risk] Coder behavior drifts between standalone and embedded paths** → Import the sole authoritative builder and run parity tests over tools, modes, output status, and errors.
- **[Trade-off] Explicit adapters add graph nodes and schemas** → Accept the additional structure because it prevents implicit reducer coupling and creates a safe Phase 6 extension seam.
- **[Risk] Concurrent Phase 4 persistence work changes runtime wiring** → Keep this phase limited to `checkpointer=None` inheritance and avoid selecting or configuring any saver; Phase 4 remains responsible for deployed persistence authority.

## Migration Plan

1. Add focused bridge-schema and mapping tests against the authoritative Coder boundary.
2. Build Jasper's internal delegation topology with the local compiled Coder subgraph and inherited checkpointing.
3. Retarget Jasper's coding transfer to the local subgraph and preserve existing return attribution/status behavior.
4. Replace the outer sibling/manual Coder handoff with the compiled Jasper boundary, without changing registration or deployment configuration.
5. Run topology, state-mapping, mode/tool parity, interrupt/resume, and regression tests.
6. Roll back by reverting the topology and adapter changes together; no data migration or saver rollback is required because this phase adds no persistence backend.
