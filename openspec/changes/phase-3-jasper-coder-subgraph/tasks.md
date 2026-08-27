## 1. Boundary Contracts and Regression Fixtures

- [ ] 1.1 Add focused tests that define the Jasper-to-Coder request projection and Coder-to-Jasper result projection, including exact message handling, attribution, workspace, model, execution mode, thread/user identity, coding-session identity, status, and execution manifest.
- [ ] 1.2 Add negative mapping tests proving Jasper-only channels and Coder-private/tool-transcript state do not cross the boundary or merge through incompatible message reducers.
- [ ] 1.3 Add a graph-topology regression test that requires the authoritative compiled Coder graph to appear as a local nested Jasper subgraph and rejects the sibling/manual `ainvoke` and same-deployment `RemoteGraph` patterns.

## 2. Jasper-Coder Subgraph Composition

- [ ] 2.1 Define explicit bridge input, internal, and output state contracts with separate inbound Jasper context and Coder working-message channels.
- [ ] 2.2 Implement the input adapter that validates and projects only the authoritative Coder inputs from Jasper state.
- [ ] 2.3 Add the Phase 1 authoritative complete Coder graph directly as the bridge's compiled subgraph node without copying or independently assembling Coder nodes, tools, or policies.
- [ ] 2.4 Implement the output adapter that returns current final Coder messages and supported status/identity/workspace/manifest fields while leaving a single extension seam for Phase 6 and adding no typed report details.
- [ ] 2.5 Compile the nested Coder graph with effective `checkpointer=None`; add construction assertions that reject `checkpointer=False`, concrete savers, and Coder-specific stores.

## 3. Jasper Topology Integration

- [ ] 3.1 Expand Jasper's compiled graph to route accepted coding transfers through the local bridge/subgraph and return completed, blocked, errored, or interrupted execution through Jasper's existing conversation boundary.
- [ ] 3.2 Retarget `transfer_to_coding` from the outer `Command.PARENT` sibling route to Jasper's local Coder route while preserving execution-mode validation, canonical workspace selection, execution manifest, and delegated task context.
- [ ] 3.3 Replace the outer graph's sibling `coding` node and manual `coding_app.ainvoke(...)` result-mapping path with the compiled Jasper boundary, without changing graph registration or introducing a user-facing Coder selection.

## 4. Durability and Behavioral Verification

- [ ] 4.1 Add an approval-interrupt test showing the nested interrupt bubbles through Jasper with its graph namespace intact and resumes on the same Jasper thread using a checkpointer supplied only to the parent graph.
- [ ] 4.2 Add a restore test showing incomplete nested Coder state survives parent graph reconstruction and continues without consulting an application-selected Coder saver or starting a replacement Coder run.
- [ ] 4.3 Add embedded-versus-authoritative parity tests for representative read-only, approval, autonomous, and sanitized-error paths, including Coder tool availability, autonomy, status, completion/progress behavior, and execution-manifest output.
- [ ] 4.4 Run the focused Jasper, Coder, topology, mapping, interrupt, and durability test suites and document that no registration, memory/RAG, MCP, UI-streaming, cleanup, deployment, or Phase 6 typed-report work was introduced.
