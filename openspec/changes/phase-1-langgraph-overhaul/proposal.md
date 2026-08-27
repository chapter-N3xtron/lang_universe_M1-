# Phase_1_LangGraph_overhaul

## Why

`Phase_1_LangGraph_overhaul` establishes a single contract for constructing the complete Coder graph. Today, Coder has a compiled wrapper graph in `src/coding_agent.py`, while integration and test paths can also assemble or invoke lower-level pieces directly; without an explicit shared graph and schema boundary, later registration and embedding work could reproduce divergent constructions.

## What Changes

- Introduce one authoritative, reusable builder for the complete Coder graph and make all in-scope Coder construction paths use it instead of independently assembling Coder nodes or wrappers.
- Introduce shared, explicit Coder input, output, and internal state schemas so standalone and parent-graph consumers can rely on the same boundary.
- Require the authoritative graph to compile without a concrete checkpointer or store, leaving persistence injection or parent-graph inheritance available to later runtime composition.
- Preserve, as compatibility requirements, the current Coder tool set, `read_only`/`approval`/`autonomous` execution-mode behavior, native Custodian filesystem and command boundary, autonomous-operation policy, credential refusal and non-disclosure behavior, interrupt policy, progress reporting, completion reporting, execution-manifest reporting, and sanitized failure behavior.
- Add focused contract tests proving construction authority, schema compatibility, persistence-neutral compilation, and preservation of current behavior.
- Explicitly exclude Agent Server registration, Jasper subgraph embedding, persistence migration, MCP migration, UI work, obsolete-path cleanup, and deployment; those remain later-phase work.

## Capabilities

### New Capabilities

- `authoritative-coder-graph`: Defines the sole reusable complete Coder graph builder, its shared schemas, persistence-neutral compilation contract, and compatibility-preserving behavior.

### Modified Capabilities

None. There are no existing main-spec capabilities in `openspec/specs/` to modify.

## Impact

- Expected implementation scope: Coder graph/schema modules and focused Coder tests under `backend/src` and `backend/tests`.
- Current facts: `src/coding_agent.py` defines `CodingAgentState`, the Deep Agents runtime construction, the Coder node, and `create_coding_agent_graph()`; `src/chat_ui.py` consumes the compiled graph; some tests directly construct wrapper graphs around `deep_agents_coding_node`.
- Proposed requirement: one exported construction boundary and one set of shared schemas become authoritative without changing user-visible Coder behavior.
- No API registration, parent Jasper topology, persistence backend, MCP boundary, UI, runtime configuration, deployment, or cleanup change is part of `Phase_1_LangGraph_overhaul`.
