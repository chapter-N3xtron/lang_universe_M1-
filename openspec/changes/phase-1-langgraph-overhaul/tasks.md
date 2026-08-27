## 1. Characterize the Current Coder Contract

- [x] 1.1 Add focused tests that capture the current complete Coder graph topology, successful/error result shape, and message/UI reducer behavior before consolidation.
- [x] 1.2 Add or tighten mode-matrix tests for the exact `read_only`, `approval`, and `autonomous` tool inventories, Custodian backend mutability, interrupt sets, and unsupported-mode fallback.
- [x] 1.3 Add or tighten security characterization tests for the native Custodian-only boundary, ordinary execute behavior, remote Git restriction, broker-held Compose/GitHub credentials, credential refusal, and secret non-disclosure.
- [x] 1.4 Add or tighten reporting tests for 15-minute task-derived progress replacement and cleanup, completion/blocker status, execution-manifest attachment, missing-final-result handling, and sanitized failures.

## 2. Establish Shared Coder Schemas

- [x] 2.1 Define explicit shared Coder input, output, and complete-state schemas with the current message and UI reducers and without Jasper-only state.
- [x] 2.2 Apply the shared schemas to Coder node annotations and graph construction, retaining a compatibility alias only where needed to avoid a second state contract.
- [x] 2.3 Add schema contract tests covering standalone-compatible input and completed, blocked, invalid-workspace, and internal-failure outputs.

## 3. Make Graph Construction Authoritative

- [x] 3.1 Establish one public reusable builder that owns the complete Coder graph's schema declarations, node, entry edge, terminal edge, and compilation.
- [x] 3.2 Ensure the authoritative builder compiles and runs without a concrete checkpointer or store and does not introduce module-global persistence.
- [x] 3.3 Preserve nested Deep Agents construction with no concrete checkpointer/store while retaining the exact current tools, prompts, middleware, modes, autonomy, Custodian boundary, credential protections, and report behavior.
- [x] 3.4 Add construction-authority and persistence-neutrality tests that fail if an in-scope production path assembles a parallel complete Coder graph or captures a concrete persistence implementation.

## 4. Migrate In-Scope Consumers

- [x] 4.1 Update the existing chat Coder handoff to consume the authoritative builder without changing routing, default handoff mode, message naming, result mapping, or Jasper topology.
- [x] 4.2 Update complete-graph integration and security tests to use the authoritative builder, leaving direct lower-level calls only where an isolated unit test specifically requires them.
- [x] 4.3 Confirm no Agent Server registration, Jasper subgraph embedding, persistence migration, MCP migration, UI feature work, obsolete-path cleanup, runtime configuration, or deployment change was introduced.

## 5. Verify Compatibility

- [x] 5.1 Run the focused Coder agent, coding security, coding persistence, and supervisor/chat handoff test suites and resolve regressions without weakening the characterized contract.
- [x] 5.2 Run the applicable backend test gate and static/type checks for the touched modules.
- [x] 5.3 Review the final diff against `authoritative-coder-graph` requirements and verify that exactly one complete Coder builder and one shared schema set remain.
