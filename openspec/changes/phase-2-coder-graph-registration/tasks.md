## 1. Confirm Plugin Contracts

- [ ] 1.1 Add the official `temporalio[langgraph]` dependency through the project package manager at a version compatible with the installed LangGraph release; confirm `LangGraphPlugin`, `graph`, Workflow, Activity, retry, timeout, and cancellation APIs without using private plugin internals.
- [ ] 1.2 Verify that the plugin accepts the authoritative Coder `StateGraph` builder, that the Coder node can run as an Activity, and that the real Coder input and output contract round-trips through the supported Temporal payload converter; stop if these contracts cannot be satisfied.
- [ ] 1.3 Record and test the plugin's public-preview status, one-node durability boundary, at-least-once Activity behavior, and cancellation behavior before enabling retries beyond one attempt.

## 2. Expose the Authoritative Builder

- [ ] 2.1 Refactor Coder graph construction into one authoritative function that returns the uncompiled `StateGraph` and one thin existing compile function used by the supervisor.
- [ ] 2.2 Mark `deep_agents_coding_node` with plugin-required `execute_in: activity` metadata without changing its normal supervisor behavior, schemas, topology, persistence ownership, or Custodian boundaries.
- [ ] 2.3 Update focused graph contract tests to prove the supervisor and Temporal use the same builder, the supervisor can still route to and run Coder as a subagent, and no copied or wrapper Coder implementation exists.

## 3. Define the Temporal Contract

- [ ] 3.1 Define a serializable internal request/result contract containing `operation_id`, graph input, terminal status, and sanitized failure information using the existing Coder field names verbatim.
- [ ] 3.2 Use `operation_id` as the Temporal Workflow ID and pass it unchanged as Coder's `thread_identity`; keep Activity attempt numbers and Temporal Run IDs out of the logical operation identity.
- [ ] 3.3 Define explicit Workflow ID conflict/reuse behavior so an equivalent repeated request addresses the existing operation and a conflicting request does not silently start unrelated work.
- [ ] 3.4 Add tests proving stable identity across Workflow replay and Activity retry and distinct identity for distinct operations.

## 4. Register and Run Coder with Temporal

- [ ] 4.1 Implement a Temporal Workflow that retrieves `graph("coder")`, compiles it inside the Workflow, invokes it with validated input, and returns the Coder terminal result.
- [ ] 4.2 Implement a Temporal worker entrypoint that registers the Workflow and `LangGraphPlugin(graphs={"coder": authoritative_builder()})`.
- [x] 4.3 Configure finite Activity and heartbeat timeouts, an explicit retry policy, and a public worker interceptor scoped to the generated `coder.coding_agent` Activity; do not modify the authoritative Coder graph configuration, claim exactly-once execution, or enable unsafe retries for side-effecting Coder work.
- [ ] 4.4 Keep Agent Server out of the Temporal execution path and leave its Jasper registration unchanged.

## 5. Verify Outcomes and Lifecycle

- [ ] 5.1 Add focused tests for first execution, successful terminal result, sanitized terminal failure, timeout, retry policy, Workflow replay, and worker restart behavior supported by the plugin test environment.
- [x] 5.2 Add focused cancellation tests proving worker-boundary heartbeats deliver a cancelled Workflow to the running Coder Activity and report the actual terminal state.
- [ ] 5.3 Test Activity re-execution against existing repository mutations; permit retries beyond one attempt only if repeated entry safely resumes from current state and does not duplicate unsafe external effects.
- [ ] 5.4 Verify completed node results are not rerun during ordinary Workflow replay.

## 6. Verify Scope

- [ ] 6.1 Verify Agent Server still registers only Jasper and normal product discovery exposes no standalone Coder graph.
- [ ] 6.2 Verify no Activity-to-Agent-Server bridge, Agent Server Coder authorization policy, synthetic Agent Server IDs, custom plugin infrastructure, prerelease Deep Agents plugin, UI change, Jasper routing change, persistence implementation, MCP change, or deployment change was introduced.
- [ ] 6.3 Run the focused Coder graph and Temporal tests plus applicable backend static checks, then record the public-preview and deployment/restart boundaries without claiming deployed behavior.
