# Phase_7_Host_MCP_transition

## Why

The native Custodian custom HTTP protocol is a bespoke execution boundary that prevents standard MCP interoperability and complicates secure Docker-to-macOS host access. This phase replaces that protocol in active execution paths while retaining the existing safety contract and Deep Agents backend interface.

## What Changes

- **BREAKING**: Replace active use of the Custodian custom HTTP protocol with one authenticated, general-purpose native macOS MCP service using Streamable HTTP and reached from Docker Desktop through `host.docker.internal`.
- Pin the official Python MCP SDK maintenance-v1 line to `mcp>=1.28,<2`, because `langchain-mcp-adapters==0.3.2` requires `mcp<2`; explicitly block MCP SDK v2 migration until the adapter supports it.
- Implement an MCP-backed `SandboxBackendProtocol` with the official MCP client so Deep Agents retains its built-in filesystem and `execute` interface.
- Reserve LangChain `MultiServerMCPClient` for additional typed, broker-held MCP boundaries; it is not a substitute for the sandbox backend.
- Provide broad ordinary shell and filesystem working freedom rather than a narrow per-task command allowlist. The selected repository remains the authoritative default and must never be silently substituted, while an explicit human task may authorize required work at other ordinary host paths. Preserve credential/keychain refusal, sensitive-file and protected-Git denial, checked paths and mutations, redacted and bounded output, timeouts, destructive and privileged-operation blocks, and autonomous execution only after an explicit human task.
- Keep credentials outside model-visible arguments and require token authentication, Host and Origin validation, restricted host binding/firewall policy, health checks, idempotent mutations, and container-to-host verification.
- Keep Compose preparation and GitHub publication as typed broker-held boundaries so agents never receive their credentials.
- Treat MCP only as transport, not as a sandbox or replacement for host-side policy enforcement.
- Defer physical Custodian deletion to Phase 9.
- Exclude graph topology, memory, UI, and cleanup deletion.

## Capabilities

### New Capabilities

- `host-mcp-execution-boundary`: Defines the authenticated native macOS MCP execution service, its Deep Agents backend compatibility, broad-but-guarded host operations, broker-held credential boundaries, and Docker-to-host verification contract.

### Modified Capabilities

None.

## Impact

- Affects the native macOS execution service, container-side backend adapter, Docker Desktop host routing/configuration, dependency pins, service launch and firewall configuration, and boundary-focused tests and runbooks.
- Replaces the active Custodian protocol contract but does not remove Custodian files in this phase.
- Preserves existing Deep Agents filesystem/execute behavior and repository binding semantics while changing the transport and client implementation beneath them.
