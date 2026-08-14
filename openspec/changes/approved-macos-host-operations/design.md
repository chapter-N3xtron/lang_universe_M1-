## Context

See `proposal.md` for motivation and `specs/approved-macos-host-operations/spec.md` for the behavior contract.

The deployed Agent Server runs in Docker. Its bind mounts expose selected Mac-host files at their host paths, but the documented `LocalShellBackend` executes inside the Linux container. The current thread trace demonstrated both failure modes this change addresses: a selected project path was replaced by the entire home directory, and Jasper delegated a macOS installation task to a Linux shell.

The existing Coding subgraph is one node, nested Deep Agents interruptions already propagate through the parent checkpoint, and the frontend already resumes standard LangGraph human-in-the-loop decisions. The host sidecar demonstrates host-native process lifecycle and macOS UI integration, but it must not become an unrestricted command service.

## Goals / Non-Goals

**Goals:**

- Keep one exact selected repository authoritative, including an empty repository before `git init`.
- Preserve autonomous containerized repository work without approval-per-command friction.
- Represent the filesystem host and command runtime separately and truthfully.
- Provide a narrowly typed, human-approved path for necessary macOS operations.
- Keep host execution authority and host secrets outside autonomous Coding.
- Preserve the current Coding graph topology and documented HITL resume path.

**Non-Goals:**

- Running the autonomous Coding shell directly on macOS.
- Providing a general remote terminal, arbitrary shell strings, arbitrary interpreter execution, automatic `sudo`, or Docker control.
- Giving the host executor GitHub publication, remote Git, SSH, credential, Keychain, login-item, launch-agent, kernel, or security-policy capabilities.
- Treating every Linux test result as proof of macOS compatibility.
- Automating macOS consent, biometric, password, license, Gatekeeper, or GUI decisions.
- Adding another reasoning agent, approval model, supervisor, or graph node.

## Decisions

### 1. Make workspace identity and execution identity explicit state

Thread state retains one canonical `workspace` selected by the human. Selection resolves symlinks once, validates an authorized host root, and accepts an existing empty directory. Refresh, remount, handoff, and resume preserve the same value. Coding receives the exact path as structured state and an explicit instruction that it must not search parent, child, or sibling directories for a different repository.

A server-produced execution manifest accompanies each Coding task and result:

- filesystem origin: Mac-host bind mount;
- selected repository: canonical path;
- command runtime: Linux Agent Server container;
- native host operations: unavailable unless separately approved;
- host-operation request capability: available or unavailable.

Jasper uses this manifest when deciding whether to delegate ordinary repository work or request a macOS operation.

**Why:** A path that exists in both host and container namespaces does not identify where commands execute. Structured identity prevents model inference from replacing deployment facts.

**Alternatives rejected:** Letting Coding discover a repository beneath the home directory caused cross-project drift; relying only on `uname` discovers the boundary after a potentially unsafe delegation.

### 2. Keep autonomous Coding in the container

Repository-local files, local Git, dependencies, tests, builds, and long-horizon agent work remain in the current uncredentialed Linux container. This preserves the existing Deep Agents workflow and prevents autonomous code from inheriting a Mac-host shell.

Host compatibility remains a separate validation dimension. A Linux build or test may be reported as Linux-only; tasks that require macOS or a native application move to the approved host-operation path.

**Why:** Moving `LocalShellBackend` to the Mac would give autonomous shell commands access beyond the selected repository because the documented backend does not confine shell execution.

### 3. Add one interrupted host-operation request tool without changing graph topology

Coding receives one ordinary typed tool, `request_macos_host_operation`. The tool accepts a structured action request, not a shell command. The existing documented Deep Agents `interrupt_on` middleware applies to this tool in both autonomous and approval modes, with only approve and reject decisions. Other autonomous repository work remains uninterrupted.

The Coding subgraph remains one node and continues to use the existing parent checkpoint and `Command` resume flow. No privileged behavior is implemented as a graph node or model decision.

**Why:** The existing HITL contract is durable and visible. A separate graph branch would add routing complexity without establishing host isolation.

### 4. Run a dedicated non-agent macOS executor

A standalone host process owns the typed action catalog, validation, host-native confirmation, execution, cancellation, state, and signed receipts. It runs with a minimal environment, restrictive state/staging directories, loopback-only bounded endpoints, no model, no shell parser, no arbitrary executable field, and no Docker access.

The executor is distinct from both the general sidecar and the GitHub publisher proposed by `approved-github-repository-publishing`. The Mac executor explicitly denies `gh`, authenticated remote Git, SSH, credential access, and publication so it cannot bypass the GitHub-specific policy boundary.

**Why:** A small non-agent process can be audited as a privileged computing base. Adding commands to the existing general sidecar would spread host authority across unrelated endpoints.

### 5. Use category-specific host actions rather than a general command runner

The first action catalog is intentionally finite:

1. **Host inspection** — fixed read-only queries for macOS version, architecture, disk space, application presence/version, and approved path metadata.
2. **Artifact download and verification** — bounded HTTPS retrieval to an exact destination with domain, size, redirect, checksum, archive, and provenance policy.
3. **Homebrew operation** — exact approved formula/cask and subcommand using the resolved host Homebrew executable; no taps, arbitrary options, service enablement, upgrade-all, cleanup-all, or shell hooks unless separately specified by policy.
4. **Application staging or installation** — typed DMG/archive mount, signature/notarization assessment, copy to an approved destination, detach, and verification; no automatic privilege escalation.
5. **Native application invocation** — a policy-approved executable such as Blender with fixed argv, working directory, input/output paths, timeout, and hash-bound repository scripts or configuration.

Each category has an independent schema, executable resolver, argv builder, path policy, timeout, output limit, mutation declaration, verification step, and rollback behavior. No model-provided command string reaches a shell.

Homebrew packages and Blender scripts can execute third-party or repository code with host-user authority. Their source, exact package or script hash, expected effects, and risk are therefore explicit approval fields rather than treated as ordinary inspection.

**Why:** A generic approved command runner would still make human review vulnerable to command injection and hidden shell behavior. Typed actions make authority finite and testable.

### 6. Keep host-native confirmation authoritative

The specialized approval card renders the canonical action and excludes it from bulk approval and generic resolution. Selecting approval initiates the host executor while the LangGraph interrupt remains pending.

The executor independently verifies that the matching interrupt remains pending, re-canonicalizes every field, computes the digest, locks it, and presents a native macOS confirmation showing the executable action, argv summary, paths, downloads, hashes, mutations, privilege level, timeout, and rollback limits. No host command runs if confirmation is cancelled or any value differs.

After execution, the executor persists a signed redacted receipt. The frontend then sends the ordinary LangGraph approve decision. The resumed tool retrieves and verifies the receipt using a non-secret public key and returns the result to Coding. A failed frontend resume does not repeat the host mutation because the digest is idempotent.

Direct requests from the container can at most trigger a bounded confirmation attempt; they cannot execute silently or forge a receipt. Pending-interrupt checks, one active prompt, rate limits, expiry, and exact display reduce nuisance and confusion.

**Why:** CORS, loopback, and a request ID do not prove human presence. Native confirmation supplies a boundary independent of autonomous container execution.

### 7. Bind executable content and mutable inputs by hash

The executor resolves the exact working directory and all input/output paths beneath category-specific authorized roots. Any repository script, Blender Python file, configuration, archive, DMG, or package metadata used by an action is hashed before approval and rechecked immediately before execution. A mismatch invalidates approval.

Downloads are staged outside the repository until verified, then copied only to the approved destination. Mutable host state is rechecked before changes. Symlinks, aliases, mount changes, and path traversal are rejected when they alter the canonical target.

**Why:** The repository remains mutable while approval is pending. Hash binding prevents a reviewed script from being replaced before host execution.

### 8. Do not automate privilege or consent

The executor never supplies `sudo` credentials, reads authentication prompts, invokes password helpers, drives System Settings approval, accepts licenses, bypasses Gatekeeper, or captures Touch ID. If an action requires those steps, it stages and verifies what it can, then returns a receipt identifying the exact user-controlled step.

**Why:** Approval of a plan is not authorization to collect credentials or synthesize operating-system consent.

### 9. Persist signed receipts and request-owned process state

The executor uses a digest-keyed monotonic state machine with single-use locking. It records the request, confirmation, spawned process identity, process tree, bounded output, declared and observed mutations, verification, rollback, and terminal status. Cancellation and timeout target only the request-owned process group.

Receipts are canonical, signed, non-secret JSON. The Agent Server receives the verification public key and receipt, never executor signing material or writable state. Retries return the existing terminal receipt; an interrupted or uncertain mutation requires human inspection or a new request rather than silent replay.

**Why:** Durable truth must survive three independently restarting domains without granting the container host authority.

### 10. Treat host-operation results as the only macOS source of truth

Jasper and Coding may claim a Mac-host effect only from a valid successful receipt whose verification step matches the requested outcome. Approval alone, a downloaded file, container output, or an unverified process exit is insufficient. Follow-up autonomous work receives the verified receipt and continues in the selected repository.

**Why:** This directly prevents recurrence of the traced thread’s false assumption that a container shell represented the physical Mac.

## Risks / Trade-offs

- **[Host executor compromise]** The executor runs as the Mac user and is privileged relative to the container. → Keep it small, non-agentic, shell-free, category-limited, separately audited, and unable to execute arbitrary binaries or environment overrides.
- **[Homebrew and application code]** Approved packages or Blender scripts can execute code with host-user authority. → Display exact package/script identity and hashes, require dedicated approval, and never classify them as read-only inspection.
- **[Prompt nuisance or confusion]** Autonomous code may try to trigger host confirmations. → Verify pending interrupts, rate-limit, allow one active prompt, display exact digest and origin, and perform no action without native confirmation.
- **[Partial installation]** DMG, package, or application operations may fail after mutation. → Declare rollback limits before approval, record observed changes, attempt only category-safe rollback, and report uncertainty.
- **[Linux/macOS divergence]** Container tests may pass while host execution fails. → Label results by runtime and add explicit macOS verification actions where needed.
- **[Workspace bind-mount breadth]** Container shell access is not confined by Deep Agents virtual mode. → Preserve exact workspace state, narrow deployment mounts where practical, mask credentials, and track stronger autonomous sandboxing separately.
- **[Platform coupling]** Native confirmation and host actions are macOS-specific. → Fail closed on other hosts and never substitute Linux commands for macOS effects.

## Migration Plan

1. Add workspace persistence and execution-manifest tests; repair existing affected thread bindings without changing message history.
2. Define category schemas, policy, canonicalization, hashing, digest, state, receipt, and redaction tests with all host execution disabled.
3. Add the single interrupted Coding tool and specialized approval presentation while preserving graph topology.
4. Build the standalone executor against fake process, filesystem, download, Homebrew, DMG, and Blender adapters.
5. Add native confirmation, signed receipts, launcher lifecycle, restrictive directories, and loopback health checks.
6. Verify Docker has no executor state, signing key, control socket, host credentials, SSH agent, Keychain access, or Docker socket.
7. Run adversarial, restart, timeout, cancellation, path-race, script-race, partial-install, and output-redaction tests.
8. Run separately approved read-only Mac inspection canaries before any installation canary.
9. Run a separately approved Blender staging/install canary only after inspection and fake-adapter gates pass.

Rollback disables the host-operation tool and stops the executor. The corrected workspace binding, autonomous repository work, local Git history, and retained non-secret receipts remain intact. Rollback never moves or substitutes the selected repository.
