# Phase_2_Coder_graph_registration

## Why

The authoritative Coder graph needs an independently addressable Agent Server registration so it can be tested in isolation and invoked durably from Temporal without exposing it as a second product-facing agent. An explicit boundary is needed now to prevent graph registration from being mistaken for native Temporal integration or an authorization boundary.

## What Changes

- Register the authoritative Coder graph as a second independently addressable Agent Server graph for focused service-level tests and internal orchestration; Jasper remains the only graph exposed to the product UI and normal users.
- Require Agent Server authorization to deny browser and normal-user Coder invocation and graph enumeration as appropriate, while allowing an authenticated internal Temporal/service identity to invoke Coder.
- Define an explicit Temporal Activity-to-Agent-Server bridge: Temporal owns outer workflow scheduling, retries, timers, and cancellation, while Agent Server owns each inner graph run and its thread state.
- Require stable operation, workflow, thread, and run identifiers; idempotent start-or-reattach behavior; cancellation propagation; and reconciliation of orphaned outer workflows or inner runs.
- Clarify that registering another Agent Server graph is neither a native Temporal integration nor, by itself, an authorization boundary.
- Exclude Jasper embedding, persistence implementation, product UI changes, MCP, and deployment from this change.
- Do not adopt the public-preview native LangGraph plugin or the prerelease Deep Agents plugin in this change.

## Capabilities

### New Capabilities

- `independent-coder-registration`: Independently registers and protects the authoritative Coder graph and defines the reliable Temporal Activity-to-Agent-Server invocation contract.

### Modified Capabilities

- None.

## Impact

Future implementation affects Agent Server graph configuration and authorization, the internal Temporal activity client/bridge, identity and correlation contracts, focused graph and orchestration tests, and operational reconciliation behavior. It does not alter the Jasper-facing product surface, implement persistence or deployment, add MCP, or introduce either excluded preview plugin.
