## 1. Dependency and Compatibility Baseline

- [ ] 1.1 Add the official Python MCP SDK constraint `mcp>=1.28,<2` to every host and container dependency declaration that installs the MCP service or client, while retaining `langchain-mcp-adapters==0.3.2`.
- [ ] 1.2 Regenerate dependency locks and add an automated compatibility assertion that fails if MCP resolves below 1.28 or at/above 2.
- [ ] 1.3 Document in dependency metadata and upgrade checks that MCP SDK v2 is blocked until `langchain-mcp-adapters` supports it and end-to-end compatibility has been approved.
- [ ] 1.4 Add a protocol contract fixture for the general filesystem, shell, health, task-context, and mutation-idempotency MCP inputs and bounded outputs.

## 2. Transport-Independent Host Policy

- [ ] 2.1 Isolate the existing credential/Keychain, sensitive-file, protected-Git, destructive, and privileged-operation refusals behind transport-independent host policy entry points without deleting Custodian code.
- [ ] 2.2 Implement the exact selected `repository_root` as the non-substitutable default plus trusted human-task scope for required ordinary host paths outside it; apply canonical ancestry, traversal, symlink, stale-context, sensitive-path, and no-fallback checks at mutation time everywhere.
- [ ] 2.3 Implement the minimal trusted command environment and broad ordinary shell policy so commands are evaluated by host safety rules rather than a narrow per-task allowlist.
- [ ] 2.4 Enforce explicit human-task authority from trusted session context before autonomous mutation, and reject model-provided attempts to create or expand task/repository authority.
- [ ] 2.5 Apply process-group timeouts and cancellation, bounded request/file/listing/stdout/stderr/error results, deterministic truncation metadata, and redaction on every result path.
- [ ] 2.6 Add a protected host-side SQLite idempotency ledger with atomic reservation, canonical request digests, replayed sanitized outcomes, conflict rejection, finite retention, and crash-safe postcondition handling.

## 3. Native macOS MCP Service

- [ ] 3.1 Implement one native macOS service with the official MCP SDK v1 Streamable HTTP transport and general checked read/list/search/write/edit/move/delete/execute capabilities backed by the shared policy pipeline.
- [ ] 3.2 Add trusted task and repository session-context establishment so model-authored MCP arguments cannot choose an unapproved root or assert human authorization.
- [ ] 3.3 Add pre-dispatch bearer-token middleware using constant-time comparison, with the token loaded from host secret configuration and excluded from schemas, child environments, logs, traces, errors, and MCP content.
- [ ] 3.4 Add exact configured `Host` and `Origin` validation before MCP dispatch, require the trusted non-browser client Origin, and cover malformed, absent, and unapproved values.
- [ ] 3.5 Implement an authenticated bounded health/readiness surface covering service, policy, ledger, protocol, and dependency readiness without exposing host inventory or execution data.
- [ ] 3.6 Add sanitized audit events for allow, refusal, timeout, truncation, redaction, replay, and conflict outcomes without logging credentials or unbounded command/content data.

## 4. Restricted Native Deployment

- [ ] 4.1 Add launchd installation and lifecycle configuration that runs the MCP service as the intended non-privileged macOS user and refuses privilege elevation.
- [ ] 4.2 Discover and configure only the host interface/address and port required by Docker Desktop access through `host.docker.internal`; fail startup rather than falling back to an unrestricted listener.
- [ ] 4.3 Install and verify macOS firewall policy restricted to the intended local Docker Desktop source/interface and service port, with no LAN or Compose port publication.
- [ ] 4.4 Add secure token generation, host/container provisioning, rotation, and file-permission procedures that keep the token outside model-visible arguments and outputs.
- [ ] 4.5 Add launch/readiness checks that fail closed when token, binding, firewall, Origin/Host policy, ledger, or MCP dependency compatibility is missing or invalid.

## 5. Deep Agents MCP Backend

- [ ] 5.1 Implement an MCP-backed `SandboxBackendProtocol` using the official MCP Streamable HTTP client, including connection/session lifecycle, cancellation, cleanup, normalized errors, and trusted header injection.
- [ ] 5.2 Map every required Deep Agents built-in filesystem method to the host MCP capabilities while preserving repository-relative defaults, explicitly authorized absolute host paths, result shapes, and error behavior.
- [ ] 5.3 Map Deep Agents `execute` to host MCP execution while preserving the selected-repository starting directory, explicitly authorized external host working paths, exit status, timeout, stdout, and stderr semantics.
- [ ] 5.4 Generate stable trusted idempotency identities for mutating backend calls and correctly handle replay, in-progress, conflict, timeout, and indeterminate outcomes.
- [ ] 5.5 Keep `MultiServerMCPClient` wiring limited to additional typed broker-held MCP boundaries and add a structural test that it cannot be used as the `SandboxBackendProtocol` substitute.

## 6. Credentialed Boundary Preservation and Cutover

- [ ] 6.1 Verify Compose preparation and GitHub publication remain separate typed broker-held boundaries whose credentials are unavailable to the general host service, model arguments, command environments, and results.
- [ ] 6.2 Configure the runtime to use `host.docker.internal` and trusted secret/header injection for the MCP backend without exposing the transport token in prompts, tool schemas, traces, or configuration returned to agents.
- [ ] 6.3 Switch active Deep Agents filesystem and execute callers from the Custodian custom protocol to the MCP-backed backend only after readiness and acceptance gates pass.
- [ ] 6.4 Add a runtime assertion or test spy proving active host work cannot silently fall back to Custodian and that MCP and Custodian are not simultaneously active.
- [ ] 6.5 Preserve all Custodian implementation, launch, test, and documentation artifacts for rollback and Phase 9 physical deletion; make no cleanup deletion in this phase.

## 7. Host and Backend Verification

- [ ] 7.1 Add `SandboxBackendProtocol` contract tests for every filesystem method and `execute`, including normalized success, refusal, timeout, truncation, cancellation, and error results.
- [ ] 7.2 Add policy tests for exact selected-repository defaults, explicitly authorized ordinary external host paths, unauthorized scope expansion, missing/stale context, sibling-prefix confusion, `..`, symlink behavior, race/revalidation, and sensitive/protected external targets.
- [ ] 7.3 Add adversarial tests for credential and Keychain access, sensitive files, Git metadata/config/hooks/remotes/history/force operations, shell composition bypasses, privilege escalation, and destructive host-wide commands.
- [ ] 7.4 Add tests proving ordinary non-privileged commands are allowed without per-task enumeration after explicit human task authority and mutations are denied before such authority.
- [ ] 7.5 Add canary tests proving all success, refusal, health, exception, audit, timeout, and oversized-output channels are bounded and redact known and pattern-detected secrets.
- [ ] 7.6 Add idempotency tests for concurrent reservation, completed replay without duplicate effects, conflicting-input rejection, service restart, retention, and crash/postcondition recovery.
- [ ] 7.7 Add transport tests for valid negotiation and rejection of missing/bad token, Host, Origin, oversized requests, malformed sessions, and unintended peers before method dispatch.

## 8. Container-to-Host Acceptance and Operations

- [ ] 8.1 Build a disposable selected-repository fixture, a separate disposable ordinary-host-path fixture, and a synthetic-secret acceptance harness that runs from the actual runtime container without using real credentials.
- [ ] 8.2 Verify `host.docker.internal` DNS/routing, restricted reachability, authenticated Streamable HTTP initialization, capability discovery, health, and the pinned MCP version range from inside the container.
- [ ] 8.3 Verify allowed read/list/ordinary execute and idempotent write replay both in the selected repository and at the separately authorized disposable host path through the real MCP-backed `SandboxBackendProtocol` from inside the container.
- [ ] 8.4 Verify representative traversal, symlink, sensitive-file, Keychain, protected-Git, destructive, privileged, invalid-header, timeout, process-tree, and redaction denials from inside the container.
- [ ] 8.5 Verify the acceptance run records no Custodian custom-protocol calls and fails with bounded diagnostics for routing, authentication, header, binding, firewall, repository-default, host-scope, or policy misconfiguration.
- [ ] 8.6 Document native installation, health interpretation, token rotation, firewall/binding verification, container acceptance, cutover, monitoring, and single-active-transport rollback procedures.
- [ ] 8.7 Perform the cutover checklist and record successful host tests, backend contract tests, container-to-host acceptance, credential non-disclosure checks, and retained Custodian rollback assets.
