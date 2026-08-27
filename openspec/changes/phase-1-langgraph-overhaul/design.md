## Context

`Phase_1_LangGraph_overhaul` implements the architecture described in `proposal.md`; behavioral requirements are in `specs/authoritative-coder-graph/spec.md`.

**Current facts:** `backend/src/coding_agent.py` currently contains the `CodingAgentState` type, Custodian typed-tool definitions, Deep Agents construction, session caching, progress/completion formatting, `deep_agents_coding_node`, and `create_coding_agent_graph()`. The latter builds a one-node wrapper and immediately compiles it. `backend/src/chat_ui.py` obtains that compiled wrapper for its Coder handoff, while security/integration tests also demonstrate independently assembled wrappers around the lower-level node. The nested Deep Agents app is currently created with `checkpointer=None`; the outer Coder wrapper is compiled without explicit persistence. Coder behavior is already covered in focused tests for modes, interrupts, tools, Custodian confinement, credential non-disclosure, progress cards, completion reports, manifests, and sanitized errors.

**Proposed requirements:** one public builder and shared input/output/state schemas become the only complete-Coder construction contract. Consolidation must not alter the behavioral baseline. The builder remains persistence-neutral so later phases can separately register it with Agent Server or embed it in Jasper without undoing a persistence choice made here.

## Goals / Non-Goals

**Goals:**

- Make ownership of complete Coder topology explicit and reusable.
- Give standalone and parent consumers narrow input/output contracts while retaining a complete internal state schema.
- Convert existing behavior into regression invariants, especially security boundaries and execution-mode policy.
- Keep low-level Coder functions testable without allowing them to become competing production construction APIs.

**Non-Goals:**

- Selecting or configuring a checkpointer, store, database, thread service, or deployment-time persistence policy.
- Creating registration adapters, Jasper state mappings, remote invocation protocols, or UI translations.
- Refactoring Custodian, replacing MCP or other tool boundaries, renaming public agents, or removing obsolete paths merely because consolidation reveals them.

## Decisions

### 1. One public complete-graph builder owns topology

Create or formalize one public Coder builder in the Coder domain module. It constructs the complete outer Coder graph, wires entry and terminal flow, applies the shared schemas, and compiles the graph. Production consumers use this builder. Low-level node and Deep Agents construction helpers remain implementation details; direct node invocation is acceptable for isolated unit tests, but no production or complete-graph integration path may independently recreate the wrapper.

This keeps the existing single-node topology simple while making authority enforceable. A contract test will inspect production references and graph shape sufficiently to catch a second construction path.

**Alternative considered:** export an uncompiled `StateGraph` and let every consumer compile it. Rejected because compilation at each call site invites divergent options and weakens the “one complete builder” contract.

**Alternative considered:** make the lower-level Coder node itself the reusable boundary. Rejected because a node does not define graph schemas, topology, entry/exit behavior, or compilation policy needed by standalone registration and subgraph composition.

### 2. Separate shared input, output, and complete state schemas

Define three shared schema types in the Coder domain boundary:

- Input: messages, workspace, model, execution mode, thread identity, user identity, and optional existing coding-session identity.
- Output: messages, canonical workspace and execution manifest when available, coding-session identity, and coding status; user-interface events remain represented where emitted by graph execution.
- Complete state: the union needed by Coder execution, including the message and UI reducers, without importing Jasper-only routing fields.

The authoritative graph declares these schemas rather than exposing an accidental parent-state shape. Existing `CodingAgentState` users migrate to the shared complete-state name or a compatibility alias only if required to avoid a needless broad rename. Runtime checks and typing tests verify that success, blocked, and error returns fit the output boundary.

**Alternative considered:** retain one broad `TypedDict` as input, state, and output. Rejected because it makes internal and parent-only fields appear required to callers and provides no stable mapping contract for later composition.

**Alternative considered:** duplicate schemas in future registration and Jasper adapters. Rejected because duplicated contracts are the divergence this phase is intended to prevent.

### 3. Compile with no concrete persistence objects

The builder compiles without passing a checkpointer or store and exposes no module-global persistence singleton. Likewise, this phase does not add a concrete persistence object to nested Deep Agents construction. Tests will construct and invoke the graph without persistence and inspect the compiled graph/configuration to ensure no concrete saver or store was captured.

This preserves two later choices: Agent Server can inject persistence at registration/runtime, and Jasper can embed Coder under parent persistence according to LangGraph inheritance semantics.

**Alternative considered:** parameterize this phase's builder with a default in-memory saver. Rejected because even a convenient default changes thread/interrupt behavior and can block parent inheritance.

**Alternative considered:** migrate immediately to the planned production database. Rejected as persistence migration is intentionally a later independent change.

### 4. Freeze behavior with characterization tests before consolidation

Treat source and existing passing tests as current facts, then add focused assertions for the requirements that must survive. The compatibility matrix covers:

- `read_only`: read-only Custodian backend, no mutable typed Custodian tools, no mutation or execution.
- `approval`: the four current typed Custodian tools and review interrupts for write, edit, delete, execute, Compose read, and GitHub publication.
- `autonomous`: the same mutable tool boundary, autonomous authorized work, and only GitHub publication interrupted.
- unsupported direct modes normalize to `read_only`.
- native Custodian remains the sole filesystem/command boundary; ordinary commands remain on built-in execute; remote Git remains unavailable except approved private publication.
- broker-held Compose/GitHub credentials are neither requested from the human nor returned to Coder.
- task-list-driven 15-minute progress replacement/removal, completion and blocker status, execution manifest, missing-final-result handling, and sanitized failures remain unchanged.

Where behavior is prompt-governed, tests assert the policy text and effective tool/interrupt configuration together instead of testing only prose. Existing tests remain the baseline and should be updated only for imports or construction authority, not relaxed.

**Alternative considered:** rely only on existing end-to-end tests. Rejected because they do not explicitly prove shared schema boundaries, sole construction authority, or persistence neutrality.

### 5. Keep downstream adapters out of this phase

The existing chat integration may switch its import/call to the authoritative builder only as needed to eliminate a competing construction path. It must not be redesigned as Jasper subgraph embedding or Agent Server registration. No `langgraph.json`, server registration, persistence configuration, MCP configuration, frontend contract, or deployment file is changed.

**Alternative considered:** prove reusability by completing registration and embedding now. Rejected because that couples independently testable phases and would violate the requested boundary.

## Risks / Trade-offs

- [Schema narrowing accidentally drops reducer metadata or optional error fields] → Derive shared schemas from current state/result behavior and test message accumulation, UI reduction, success, blocked, and error outputs.
- [“One builder” is enforced only by convention] → Keep one public complete construction API, migrate production/integration consumers, and add a repository-level construction-authority test targeted to Coder graph assembly.
- [Characterization tests fossilize incidental implementation details] → Assert the user-visible and security-sensitive compatibility matrix, not cache layout, private helper names, or incidental message object classes.
- [Persistence-neutral tests pass while a nested default is introduced later] → Assert both outer compilation and nested Deep Agents construction receive no concrete checkpointer/store in this phase.
- [Changing imports breaks current consumers] → Prefer a compatibility alias where necessary and migrate in-scope callers atomically; do not maintain two functioning builders.
- [Current prompt and tool behavior drifts during extraction] → Move definitions without rewriting policy, then run focused Coder and security tests before any optional organization change.

## Migration Plan

1. Add characterization tests for shared contracts, construction authority, no bound persistence, and the compatibility matrix before moving topology ownership.
2. Introduce the shared input/output/complete-state schemas and update Coder type annotations without changing runtime behavior.
3. Establish the sole public complete-graph builder, retaining the existing node, edges, and behavior.
4. Migrate the current in-scope production consumer and complete-graph integration tests to that builder; keep only isolated low-level unit tests on private helpers.
5. Run focused Coder, security, supervisor/chat handoff, and persistence tests, then run the repository's applicable backend test gate.

No deployment or data migration occurs. Rollback is a code-only revert of schema/builder consolidation because no registration, persisted-data format, runtime configuration, or storage backend changes in this phase.
