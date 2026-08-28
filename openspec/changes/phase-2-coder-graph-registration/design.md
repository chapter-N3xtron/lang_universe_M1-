## Context

The authoritative Coder graph currently compiles a single `deep_agents_coding_node`, and the supervisor graph embeds that compiled graph. The first version of this change proposed independently registering Coder in Agent Server and invoking it from a Temporal Activity. Runtime verification found that the supported Agent Server create-run API generates its own run ID and does not accept a caller-assigned run ID. That makes the proposed lost-response-safe start-or-reattach contract impossible as written.

The chosen replacement is Temporal's official LangGraph plugin. The plugin is public preview and runs registered LangGraph nodes as Temporal Activities. It does not invoke Agent Server and does not use Agent Server threads or runs. This limitation and ownership change are accepted for this phase.

## Goals / Non-Goals

**Goals:**

- Run the one authoritative Coder graph as a durable Temporal Workflow without copying its implementation.
- Keep Coder internal and independently runnable without exposing it in the product UI or Agent Server discovery.
- Give Temporal clear ownership of workflow identity, scheduling, retries, timeouts, cancellation, and completed task results.
- Preserve stable Coder operation identity across Activity retries and Workflow replay.
- Verify the public-preview plugin against the current Coder graph before enabling an internal caller.

**Non-Goals:**

- Registering Coder as a second Agent Server graph.
- Building an Activity-to-Agent-Server HTTP or SDK bridge.
- Giving Agent Server ownership of Temporal-triggered Coder state.
- Changing Jasper routing, product UI behavior, persistence implementation, MCP, or deployment topology.
- Adopting the separate prerelease Deep Agents plugin.

## Decisions

### 1. Use the official Temporal LangGraph plugin

The backend will use `temporalio[langgraph]` at a version that provides `temporalio.contrib.langgraph.LangGraphPlugin` and supports the installed LangGraph version. The plugin will register the authoritative Coder graph under the stable internal name `coder`.

This is an explicit acceptance of a public-preview dependency. A custom compatibility layer will not be added around undocumented plugin internals. If the supported plugin cannot register and execute the current Coder graph, implementation stops and records the incompatibility.

### 2. Preserve one authoritative Coder graph builder

Coder graph construction will be separated into one function that returns the uncompiled `StateGraph` required by `LangGraphPlugin` and one thin compile function for the existing supervisor path. Both paths use the same builder, schemas, node function, and topology. The supervisor retains its current ability to route to and run Coder as a subagent. No wrapper graph, copied node, or second Coder implementation is introduced.

The Coder node will declare the plugin-required `execute_in: activity` metadata. Jasper's local compilation continues to use the same node normally; the metadata has no routing effect outside the Temporal plugin.

### 3. Run Coder inside Temporal, not Agent Server

A conventional Temporal Workflow retrieves `graph("coder")`, compiles it within the Workflow, and invokes it with validated Coder input. A Temporal worker registers that Workflow and the `LangGraphPlugin` configured with the authoritative Coder builder.

Temporal owns the outer Workflow and the plugin-owned Activity execution. Agent Server is not contacted, does not create a thread or run, and does not own state for these operations. The existing Agent Server registration remains Jasper-only.

### 4. Use one stable operation identity

The internal caller supplies an immutable `operation_id`. The caller starts the Temporal Workflow with that value as its Workflow ID. The Workflow passes the same value to Coder as `thread_identity`, so Coder's existing session derivation remains stable across Activity retries and Workflow replay.

Temporal's Workflow ID and Workflow Run ID provide operational correlation. No synthetic Agent Server `thread_id` or `run_id` is created. A repeated request with the same Workflow ID follows Temporal's configured Workflow ID conflict and reuse policy rather than starting uncorrelated work.

### 5. Treat the complete Coder node as one side-effecting Activity

The authoritative Coder graph currently has one node, so the plugin makes one complete Coder execution a Temporal Activity. The worker configuration will provide a finite start-to-close timeout and an explicit retry policy. The Activity input must be serializable and must include the stable operation identity, repository path, execution mode, model selection, user identity, and task messages.

Temporal Activity retries are at-least-once. A retry can re-enter Coder after repository mutations made by an earlier failed attempt. Before enabling retries beyond one attempt, focused tests must show that the Coder resumes from current repository state without duplicating unsafe external effects. Broker-held GitHub publication remains an explicit typed boundary and is not made automatically retryable by this change. If safe retry behavior cannot be demonstrated, the initial policy must avoid automatic re-execution rather than claim exactly-once behavior.

### 6. Use Temporal cancellation and terminal outcomes

Workflow cancellation propagates through the plugin to the running Coder Activity. Because the public-preview LangGraph plugin does not emit Activity heartbeats, the dedicated Coder worker uses Temporal's public Activity interceptor API to heartbeat only the generated `coder.coding_agent` Activity. The Activity has an explicit heartbeat timeout. This worker boundary does not modify or wrap the authoritative Coder graph, its node, or its supervisor configuration.

The heartbeats report worker-side liveness rather than Coder progress. Cancellation remains cooperative and can only stop work at cancellation-aware asynchronous boundaries. The Workflow returns or raises the authoritative Temporal terminal outcome and does not attempt Agent Server cancellation or reconciliation.

Completed node results are held by Temporal's plugin task-result cache during Workflow replay. Long histories may later use the plugin's documented continue-as-new cache handoff, but continue-as-new is not required in this phase.

### 7. Keep product exposure unchanged

The product-facing Agent Server manifest continues to register only Jasper. No Coder choice is added to browser discovery, normal-user invocation, or Jasper routing. Internal Temporal startup is a service boundary and is not represented as browser authorization.

### 8. Verify boundaries independently

Focused tests will cover authoritative builder reuse, required Activity metadata, plugin registration, Workflow input validation, stable identity propagation, successful result return, terminal failure, timeout/retry policy, cancellation, and the Jasper-only Agent Server manifest. Tests will also verify that no Agent Server bridge, independent Coder registration, or prerelease Deep Agents plugin was introduced.

## Risks / Trade-offs

- **Public-preview plugin:** The API may change. Pin and test a compatible supported version; do not depend on private plugin internals.
- **Coarse durability:** The complete Coder is one Activity, so Temporal cannot checkpoint each internal Deep Agents step. A failed Activity attempt may rerun the complete Coder node.
- **At-least-once side effects:** Repository mutations may survive a failed attempt. Retry behavior must be tested and described honestly; exactly-once execution is not promised.
- **Payload compatibility:** LangChain messages and Coder output must cross Temporal's payload converter. Stop if the supported converter cannot round-trip the real contract without a documented conversion boundary.
- **Cancellation latency:** Worker-side liveness heartbeats deliver cancellation, but cancellation can only stop work at cancellation-aware asynchronous boundaries. A blocked event loop can also prevent heartbeats. Focused tests must verify the actual Coder path.
- **Ownership change:** Temporal-triggered Coder runs will not appear as Agent Server threads or runs. This is intentional for the chosen plugin architecture.

## Migration Plan

1. Verify plugin, payload, retry, and cancellation compatibility with the authoritative Coder graph.
2. Refactor graph construction to expose the single uncompiled builder while preserving Jasper's compiled path.
3. Add the Temporal Workflow and worker registration with focused tests.
4. Enable an internal caller only in separate deployment work after the source contract passes.

Rollback removes the Temporal worker registration and plugin dependency while leaving Jasper's existing compiled Coder path and Agent Server registration unchanged.
