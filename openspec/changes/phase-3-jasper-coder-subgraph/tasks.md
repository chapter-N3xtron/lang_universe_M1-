## 1. Boundary Contracts and Regression Fixtures

- [x] 1.1 Add focused tests that define the Jasper-to-Coder request projection and Coder-to-Jasper result projection, including exact message handling, attribution, workspace, model, execution mode, thread/user identity, coding-session identity, status, and execution manifest.
- [x] 1.2 Add negative mapping tests proving Jasper-only channels and Coder-private/tool-transcript state do not cross the boundary or merge through incompatible message reducers.
- [x] 1.3 Add a graph-topology regression test that requires the authoritative compiled Coder graph to appear as a local nested Jasper subgraph and rejects the sibling/manual `ainvoke` and same-deployment `RemoteGraph` patterns.

## 2. Jasper-Coder Subgraph Composition

- [x] 2.1 Define explicit bridge input, internal, and output state contracts with separate inbound Jasper context and Coder working-message channels.
- [x] 2.2 Implement the input adapter that validates and projects only the authoritative Coder inputs from Jasper state.
- [x] 2.3 Add the Phase 1 authoritative complete Coder graph directly as the bridge's compiled subgraph node without copying or independently assembling Coder nodes, tools, or policies.
- [x] 2.4 Implement the output adapter that returns current final Coder messages and supported status/identity/workspace/manifest fields while leaving a single extension seam for Phase 6 and adding no typed report details.
- [x] 2.5 Compile the nested Coder graph with effective `checkpointer=None`; add construction assertions that reject `checkpointer=False`, concrete savers, and Coder-specific stores.

## 3. Jasper Topology Integration

- [x] 3.1 Expand Jasper's compiled graph to route accepted coding transfers through the local bridge/subgraph and return completed, blocked, errored, or interrupted execution through Jasper's existing conversation boundary.
- [x] 3.2 Retarget `transfer_to_coding` from the outer `Command.PARENT` sibling route to Jasper's local Coder route while preserving execution-mode validation, canonical workspace selection, execution manifest, and delegated task context.
- [x] 3.3 Replace the outer graph's sibling `coding` node and manual `coding_app.ainvoke(...)` result-mapping path with the compiled Jasper boundary, without changing graph registration or introducing a user-facing Coder selection.

## 4. Durability and Behavioral Verification

- [x] 4.1 Add an approval-interrupt test showing the nested interrupt bubbles through Jasper with its graph namespace intact and resumes on the same Jasper thread using a checkpointer supplied only to the parent graph.
- [x] 4.2 Add a restore test showing incomplete nested Coder state survives parent graph reconstruction and continues without consulting an application-selected Coder saver or starting a replacement Coder run.
- [x] 4.3 Add embedded-versus-authoritative parity tests for representative read-only, approval, autonomous, and sanitized-error paths, including Coder tool availability, autonomy, status, completion/progress behavior, and execution-manifest output.
- [x] 4.4 Run the focused Jasper, Coder, topology, mapping, interrupt, and durability test suites and document that no registration, memory/RAG, MCP, UI-streaming, cleanup, deployment, or Phase 6 typed-report work was introduced.

## Verification Record

- Phase-focused result: 147 tests passed across Jasper, Coder, topology, mapping, execution-mode policy, approval, security, persistence, and Temporal contract suites.
- Static verification: Ruff lint and formatting checks passed; `git diff --check` passed; the documented `npx --yes @fission-ai/openspec@latest validate phase-3-jasper-coder-subgraph --strict --no-interactive` command reported the change as valid.
- Scope confirmation: graph registration was unchanged, and no memory/RAG, MCP, UI-streaming, cleanup, deployment, or Phase 6 typed-report work was introduced.
