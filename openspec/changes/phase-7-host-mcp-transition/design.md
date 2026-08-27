## Context

See `proposal.md` for motivation and `specs/host-mcp-execution-boundary/spec.md` for the behavioral contract. Today the container reaches a native macOS Custodian service through a custom HTTP API. The replacement crosses the same trust boundary: an agent-controlled container asks a host process to read, mutate, and execute within a human-selected repository. Standardizing the wire protocol does not reduce the authority of that process and does not make MCP a sandbox.

The Deep Agents runtime expects `SandboxBackendProtocol`, including its built-in filesystem methods and `execute`; MCP tool collections alone do not implement that protocol. Transport credentials and repository/task authority must come from trusted runtime configuration, not model-authored tool arguments. Docker Desktop supplies the stable client-side hostname `host.docker.internal`, while the native listener and macOS firewall must constrain which peers can reach the service.

## Goals / Non-Goals

**Goals:**

- Put one native macOS host-execution service behind standards-compliant MCP v1 Streamable HTTP.
- Preserve the observable Deep Agents backend contract while moving its transport to the official MCP client.
- Centralize broad ordinary shell/filesystem policy at the host boundary and carry forward all existing refusal, path, mutation, timeout, output, and redaction controls.
- Make authentication, network exposure, retries, health, and container-to-host acceptance testable.
- Keep credentialed Compose preparation, GitHub publication, and any future broker capabilities structurally distinct from general host execution.

**Non-Goals:**

- Treating MCP, Docker Desktop networking, or MCP tool schemas as a security sandbox.
- Replacing `SandboxBackendProtocol` with a collection returned by `MultiServerMCPClient`.
- Designing per-task command allowlists or per-operation human approval for ordinary work after an explicit task.
- Changing graph topology, memory, UI, repository-binding wire/storage names, or artifact ownership.
- Deleting Custodian assets; Phase 9 owns physical cleanup.

## Decisions

### 1. Use the official Python MCP SDK v1 on both ends

The native service and the backend transport use official SDK Streamable HTTP primitives. Dependency declarations pin `mcp>=1.28,<2` next to the existing exact `langchain-mcp-adapters==0.3.2` constraint. Lock/compatibility checks must fail if SDK v2 resolves. An upgrade to v2 is a separate compatibility change after the adapter advertises v2 support and end-to-end behavior is verified.

**Alternatives considered:** Keeping the custom protocol would preserve technical debt and interoperability problems. Migrating directly to SDK v2 would conflict with the current adapter. Implementing MCP framing by hand would recreate a custom, less-audited transport.

### 2. Run one policy-enforcing native service with coarse, general tools

A launchd-managed native process exposes a small set of general capabilities sufficient to back filesystem methods and shell execution: checked reads/listings/searches, checked writes/edits/moves/deletes, and ordinary command execution. The schema is coarse enough for broad work and is not generated from a task-specific command list. Each call enters one shared policy pipeline before any side effect:

1. authenticate and validate transport metadata;
2. obtain trusted human-task scope and selected-repository context established by the application when the human supplied the task;
3. validate and canonicalize operation inputs and environment;
4. evaluate sensitive-data, Git-protection, destructive, and privilege policy;
5. reserve the idempotency record for mutations;
6. execute with deadline and process-tree control;
7. bound and redact result/error data before returning it;
8. commit the idempotency outcome and emit a secret-free audit event.

Human-task scope and selected-repository context are session metadata established by trusted application code. An explicit host task may include ordinary work outside the selected repository, but a model-provided path or statement that a task was approved cannot create or expand that scope. The service does not begin autonomous mutation merely because a client can connect.

**Alternatives considered:** A command allowlist is too narrow for general coding work and moves routine tool choice back to humans. Exposing unrestricted host shell directly would omit the existing policy boundary. One MCP service per command or repository would increase lifecycle and policy drift without strengthening the required semantics.

### 3. Adapt MCP to `SandboxBackendProtocol`, not vice versa

A container-side backend class implements every required protocol method and maps it to the native service with the official MCP client session. It owns connection lifecycle, method/result conversion, timeouts, normalized errors, and cleanup. Paths presented through Deep Agents retain repository-relative behavior by default and may use ordinary absolute host paths when trusted human-task context authorizes them; the adapter never searches for or invents a fallback repository. `execute` preserves expected command, working-directory, exit, timeout, stdout, and stderr behavior while consuming bounded MCP results.

`MultiServerMCPClient` remains available only for extra typed broker-held MCP servers, such as narrowly modeled credentialed boundaries. Those tools are registered separately and are never passed where a `SandboxBackendProtocol` is expected.

**Alternatives considered:** Wrapping `MultiServerMCPClient.get_tools()` as a backend creates a false type and semantic equivalence and can bypass backend filesystem conventions. Retaining the Custodian adapter behind the new class would leave the custom active protocol in place.

### 4. Preserve the selected-repository default and checked unrestricted-host semantics

The trusted context carries the repository binding identity, exact selected `repository_root`, and the scope of the explicit human task; it does not reinterpret `workspace_id` as a UI workspace. Repository work starts in that exact root and never searches for or substitutes another checkout. When the explicit task requires work elsewhere on the host, trusted task context may authorize ordinary absolute host paths without a new per-command gate. A model-authored claim cannot create that authority. Existing targets are canonicalized with real-path and ancestry checks. New targets are checked by walking to an existing canonical ancestor, validating each component, denying unsafe symlink traversal, and performing mutations with descriptor-relative/no-follow techniques where the platform permits. The service revalidates at the mutation boundary and fails closed on missing, stale, moved, or ambiguous context.

Sensitive-path rules apply everywhere, including both the selected repository and explicitly authorized external host paths. Git policy protects `.git` internals and denies credential-bearing remote/config/hook operations, destructive history changes, force operations, and protection bypasses whether attempted through filesystem tools or shell execution. Shell working directories and referenced paths pass through the same task-scope, path, and policy checks. Environment construction starts from a minimal trusted baseline, excludes broker/transport secrets, and denies credential helpers, privilege escalation, protected system mutation, and destructive host-wide patterns. Policy tests include alternate spellings, symlinks, shell composition, external-path scope, and common bypass attempts.

**Alternatives considered:** Confining every operation to the selected repository was rejected because an explicit human host task may require ordinary work elsewhere. Treating any model-provided path as authorized was rejected because only trusted human-task context can expand scope. String-prefix checks fail on sibling prefixes and symlinks, and container-only checks can be bypassed before requests reach the authority.

### 5. Authenticate outside model arguments and constrain HTTP exposure

The client obtains a high-entropy bearer token from a container secret/configuration channel unavailable to prompts and injects it into HTTP headers in trusted transport code. It never places the token in tool schemas, arguments, logs, traces, MCP content, or exceptions. The native service compares tokens in constant time, rejects unauthenticated requests before MCP dispatch, and supports controlled rotation with a short overlap if deployment requires it.

HTTP middleware validates an exact configured set of `Host` values (including the selected port) and an exact Origin policy before SDK dispatch. The non-browser container client sends the configured trusted Origin explicitly so absence is not silently accepted. CORS is not used as authentication.

The launch configuration binds only the interface/address required by Docker Desktop rather than publishing indiscriminately. Installation determines the actual Docker Desktop host-facing route, records the selected address, and installs a macOS firewall rule limited to the intended local Docker Desktop source/interface and service port. Startup fails if binding or firewall prerequisites cannot be verified. The endpoint is not exposed through Compose port publishing or a LAN listener.

**Alternatives considered:** A token in an MCP tool argument is model-visible and leakable. Loopback-only binding is not generally reachable from Docker Desktop. Binding all interfaces without firewall restriction exposes a host execution service to unintended peers. Host/Origin checks alone are request-hardening, not authentication.

### 6. Bound execution and all response channels

Commands run as the logged-in non-privileged service account in a new process group with a maximum deadline and no privilege elevation. Timeout or cancellation terminates the entire process group, with escalation after a grace interval. Request size, file-read size, listing count, stdout, stderr, structured MCP content, exception text, audit fields, and aggregate response size have explicit limits. Truncation is deterministic and reported with metadata.

Redaction runs on every success and failure path after collection and before serialization/logging, using known secret values supplied only to the redactor plus credential/key/token pattern detection. The transport token is never supplied to child environments. Refusals use stable public error categories and omit raw sensitive inputs.

**Alternatives considered:** Client-side truncation permits oversized or secret-bearing data to cross the trust boundary. Killing only the shell leaves descendants running. Relying on prompts for restraint is not enforcement.

### 7. Make mutations replay-safe with a host-side idempotency ledger

Every mutating adapter call supplies a trusted request ID plus an operation key. The service computes a canonical digest over the authenticated session/task context, selected-repository identity, authorized host scope, operation name, and validated inputs. A local protected SQLite ledger atomically records `in_progress`, terminal outcome metadata, and expiry. The combination of identity and digest determines behavior:

- same identity and digest, completed: return the stored sanitized outcome;
- same identity and digest, in progress: wait briefly or return a retryable status without starting another mutation;
- same identity, different digest: reject as a conflict;
- new identity: reserve atomically before mutation.

Stored outcomes are bounded and redacted, and retention is finite. For operations where a crash can occur between side effect and terminal record, mutation implementations use atomic replace/rename and pre/postcondition fingerprints so recovery can determine whether the intended state already exists instead of blindly replaying.

**Alternatives considered:** Client-only retry suppression does not survive reconnects. An in-memory cache loses state on service restart. Treating all filesystem writes as naturally idempotent does not cover append, move, delete, or command-mediated mutations.

### 8. Separate liveness from authority and verify from inside the container

A minimal authenticated readiness route (or non-mutating MCP health capability) reports protocol/service version, policy readiness, ledger readiness, and dependency compatibility without filesystem data, tools arguments, secrets, or host inventory. launchd and the runtime use it for health, but successful health does not itself grant task authority.

An acceptance harness runs from the actual runtime container and verifies:

- `host.docker.internal` resolution and route;
- expected binding/firewall reachability and rejection from an unintended peer where test infrastructure permits;
- rejection for missing/bad token, Host, and Origin;
- authenticated MCP initialize/session negotiation and capability discovery;
- health and dependency version range;
- backend-compatible read/list/execute in a disposable repository fixture;
- write retry replay and conflicting idempotency-key rejection;
- traversal, symlink escape, sensitive file, Keychain, protected Git, destructive, and privileged denials;
- timeout process-tree termination and output truncation/redaction;
- absence of calls to the Custodian custom protocol.

Tests use synthetic canary secrets and disposable repositories, never real credentials.

**Alternatives considered:** Host-only tests miss Docker DNS/routing and secret injection. A TCP probe cannot prove MCP negotiation, authentication, policy, or backend semantics.

### 9. Keep credentialed business boundaries typed and separate

Compose preparation and GitHub publication stay behind explicit broker APIs/MCP servers with narrow typed inputs and outputs. Trusted broker code holds their credentials and performs authorization; the general execution service neither returns those credentials nor weakens sensitive-file policy to make them reachable. If exposed through MCP, `MultiServerMCPClient` may load these additional typed tools, but they remain distinct from host filesystem/execute methods and the backend adapter.

**Alternatives considered:** Injecting GitHub or Compose credentials into the general shell environment gives the model credential access. Folding publication into the host service broadens authority and makes policy harder to audit.

## Risks / Trade-offs

- **[Broad shell access admits bypass techniques that static matching may miss]** → Keep all authority in the native non-privileged process, minimize its environment, combine semantic command/path policy with filesystem revalidation, maintain adversarial bypass tests, and fail closed on ambiguity. Document that this is policy containment, not a sandbox.
- **[A host-facing listener is a high-value target]** → Layer token authentication, exact Host/Origin checks, restricted binding, macOS firewall rules, no LAN/Compose publication, token rotation, bounded parsing, and secret-free auditing.
- **[Docker Desktop networking varies by release/configuration]** → Discover and verify the required host-facing interface during installation and block readiness when the expected route/firewall state is absent.
- **[Protocol adaptation can subtly change Deep Agents semantics]** → Add contract tests against every `SandboxBackendProtocol` method and compare normalized results/errors with the current behavior before cutover.
- **[Idempotency cannot make arbitrary shell commands transactional]** → Reserve before execution, classify mutation-capable calls, use postconditions where possible, and return an explicit indeterminate result after unrecoverable crashes rather than replaying blindly.
- **[Redaction can over-redact useful output or miss novel secrets]** → Combine exact known-value redaction with conservative patterns, use canary tests on every response path, and keep hard sensitive-path refusal as the primary control.
- **[Temporary coexistence leaves two implementations on disk]** → Route all active callers to MCP, add a no-Custodian-call acceptance assertion, and defer only physical deletion to Phase 9 so rollback remains possible.
- **[SDK v1 eventually becomes obsolete]** → Keep the `<2` pin and compatibility test explicit; schedule v2 only after adapter support rather than silently drifting dependencies.

## Migration Plan

1. Add dependency constraints and CI/lock verification for `mcp>=1.28,<2` with `langchain-mcp-adapters==0.3.2`.
2. Extract or reuse the current host policy behaviors behind transport-independent operations, then implement the Streamable HTTP MCP service, middleware, ledger, health, launchd configuration, binding, and firewall setup without deleting Custodian.
3. Implement the official-client `SandboxBackendProtocol` adapter and its contract tests. Keep extra broker MCP clients separately wired.
4. Add trusted secret injection and task/repository session context. Verify that transport and broker credentials never enter model arguments, child environments, logs, or results.
5. Run native policy tests, then the full acceptance harness from the runtime container using a disposable repository and synthetic canaries.
6. Cut active filesystem/execute configuration from Custodian to the MCP backend only after health and acceptance pass. Retain Custodian files stopped/unreferenced for rollback and later Phase 9 removal.
7. Observe bounded health, refusal categories, timeouts, and replay conflicts. Do not log commands or content beyond the existing sanitized audit policy.

**Rollback:** Stop the MCP launch service and revert active configuration to the retained Custodian path using the prior secret/configuration, without deleting the MCP implementation or idempotency ledger. Rollback is permitted only as an operational recovery and must not result in simultaneous active transports. Re-run the previous boundary checks before restoring service. Custodian remains physically present specifically to support this window until Phase 9.
