# Phase_3_Jasper_Coder_subgraph

## Why

Jasper currently hands coding work to a sibling top-level node that manually calls a compiled Coder graph, so Coder execution is not a genuine nested part of Jasper's LangGraph topology. Jasper needs to embed the same complete authoritative Coder graph locally so users retain one Jasper-facing surface while Coder keeps its autonomous behavior, tools, interrupts, and durable execution semantics.

## What Changes

- Embed the complete authoritative Coder graph directly in Jasper as a genuine local compiled LangGraph subgraph, replacing the current sibling-node/manual `ainvoke` handoff.
- Reuse the authoritative Coder graph construction boundary; do not copy, simplify, or independently reassemble Coder behavior.
- Define explicit adapters from Jasper state to Coder input and from Coder output back to Jasper state because their schemas and message reducers differ.
- Compile the nested Coder graph with the default `checkpointer=None`, with no concrete saver and never `checkpointer=False`, so each invocation inherits the parent Agent Server checkpointer and supports interrupts and durable resume.
- Prohibit same-deployment `RemoteGraph` use for the Jasper-to-Coder relationship.
- Keep Jasper as the only user-addressed agent and preserve Coder autonomy, tools, execution modes, workspace identity, interrupt behavior, progress behavior, and result/status return.
- Coordinate with Phase 6 by preserving a stable output-mapping seam, but do not define or implement Phase 6's typed report details.
- Exclude graph registration, memory/RAG, MCP, UI streaming, obsolete-path cleanup, and deployment.

## Capabilities

### New Capabilities

- `jasper-coder-subgraph`: Defines Jasper's local authoritative Coder subgraph composition, explicit state mapping, inherited checkpointing, and single Jasper-facing interaction boundary.

### Modified Capabilities

- None.

## Impact

- Future implementation primarily affects Jasper and top-level graph composition under `backend/src`, plus focused topology, mapping, interrupt, durability, and behavioral-regression tests under `backend/tests`.
- Current observed baseline: `backend/src/chat_ui.py:357-361` constructs Coder beside the outer graph; `backend/src/chat_ui.py:420-505` manually invokes it with `coding_app.ainvoke(...)` and maps selected results; `backend/src/chat_ui.py:596-604` registers `jasper` and `coding` as sibling nodes. `backend/src/jasper_agent.py:178-213` sends `Command.PARENT` to that sibling, while `backend/src/jasper_agent.py:992-998` compiles Jasper as a one-node wrapper. `backend/src/coding_agent.py:40-50` and `backend/src/jasper_agent.py:82-118` show the differing state schemas, and `backend/src/coding_agent.py:795-800` compiles the current Coder graph without an application-supplied saver.
- No product-facing Coder endpoint, registration change, persistence-backend migration, typed Phase 6 report contract, memory/RAG, MCP transport, UI streaming behavior, cleanup, or deployment work is included.
