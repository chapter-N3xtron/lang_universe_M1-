## Context

See `proposal.md` for motivation and `specs/approved-github-repository-publishing/spec.md` for the behavior contract.

The current Coding subgraph is a one-node Deep Agents graph. Approval and autonomous modes both use documented `LocalShellBackend`; its documentation states that shell commands are not confined by `root_dir`, virtual mode, or filesystem permissions. Nested tool interrupts already propagate through the parent LangGraph checkpoint and the frontend already renders standard `action_requests` and resumes them with `Command` decisions.

The Agent Server must therefore be treated as untrusted for GitHub credentials whenever autonomous shell execution exists. Blanking a child process variable is insufficient because a process in the same container can inspect parent process metadata, known socket paths, mounts, and reachable services. The GitHub credential and the authority to publish must remain outside that container.

## Goals / Non-Goals

**Goals:**

- Preserve uninterrupted autonomous local repository work.
- Add one explicit publication request that uses documented Deep Agents/LangGraph tool interruption and durable resume behavior.
- Keep the GitHub credential and privileged GitHub operations in a host security domain unavailable to the Agent Server.
- Bind human approval and publication to one canonical repository snapshot and one exact remote operation.
- Make retries, restarts, rejection, expiry, and partial failure explicit and auditable.
- Keep the existing graph topology unchanged.

**Non-Goals:**

- Giving autonomous Coding general GitHub CLI, API, SSH, Docker, Keychain, or host-command access.
- Publishing to organizations, owners other than `chapter-N3xtron`, existing repositories, extra branches, or tags.
- Supporting force push, remote deletion outside rollback of a repository created by the same request, or arbitrary Git commands in the privileged process.
- Making GitHub repository creation and first push transactionally atomic; GitHub exposes them as separate effects.
- Adding another reasoning agent, supervisor, approval model, or custom LangGraph execution engine.

## Decisions

### 1. Separate autonomous work from privileged publication

The Agent Server remains the autonomous Coding domain and receives no GitHub token, GitHub CLI configuration, private key, SSH agent socket, publisher signing key, publisher state directory, or Docker socket. A dedicated host publisher process is the only component allowed to use the existing `chapter-N3xtron` host GitHub login.

The publisher runs as a separate host process with a minimal environment, restrictive state and staging directories, loopback-only access, bounded requests, and no model. It invokes fixed argv operations rather than a shell. Its credential remains in macOS Keychain through the host GitHub CLI; token text is never copied into graph state, tool arguments, Docker configuration, repository files, or logs.

**Why:** Environment filtering inside `LocalShellBackend` does not create a security boundary against autonomous shell execution. Process separation keeps the credential outside the adversarial domain.

**Alternatives rejected:**

- Passing `GH_TOKEN` into the Agent Server and clearing it only for autonomous child commands: recoverable from the shared process/container.
- Mounting host GitHub or SSH configuration: recoverable by autonomous shell commands.
- Mounting the Docker socket to launch a privileged one-shot container: gives autonomous execution host control.
- Running GitHub CLI directly as an approved shell command: the credential would still exist in the shared container before and after approval.

### 2. Use one ordinary interrupted tool; do not change graph topology

Coding receives one narrowly typed tool, `request_github_repository_publication`. It accepts only the local repository, proposed repository name, visibility, source ref, exact source SHA, and target branch. Owner, remote URL, refspec, digest, and expiry are canonicalized rather than trusted from model output.

The existing documented Deep Agents `interrupt_on` mechanism is configured for this tool in both autonomous and approval modes. Autonomous filesystem and shell work continues normally; only the publication request interrupts. Allowed decisions are `approve` and `reject`. The Coding subgraph remains one node, nested interrupts continue through the existing parent checkpoint, and no routing node or reasoning layer is added.

**Why:** This uses the existing durable HITL contract and isolates the high-agency action without converting long-horizon autonomous work into approval-per-command work.

**Alternative rejected:** Adding a publication graph node or separate publication agent would expand graph topology without improving the credential boundary.

### 3. Treat host-native confirmation as the authoritative user-presence boundary

The specialized approval card displays every canonical field required by the spec and excludes publication from bulk approval and generic “resolve” behavior. Choosing approval initiates the loopback host publisher flow while the LangGraph interrupt remains pending.

Before any remote effect, the publisher independently validates the request, confirms that the matching LangGraph action is still pending, computes the canonical digest, acquires a single-use lock, stages the exact source commit, and presents a host-native macOS confirmation containing the owner/name, visibility, source SHA, target branch, and cleanup warning. Cancellation or mismatch produces no remote effect.

After host confirmation, the publisher executes and verifies the operation, persists a signed redacted receipt, and returns its digest. The frontend then submits the ordinary LangGraph `approve` decision. When the interrupted tool resumes, it retrieves the signed receipt by canonical digest, verifies it using a non-secret publisher public key, and returns the result to Coding. If frontend resume fails, the receipt remains available and the same request resumes idempotently.

A direct call from the Agent Server may at most request that the host display a bounded confirmation; it cannot publish silently, forge a signed receipt, or obtain the credential. Rate limiting, one active prompt, expiry, and exact field display limit nuisance prompts and approval confusion.

**Why:** CORS, loopback binding, browser origin, and possession of a request ID are not sufficient authorization against arbitrary autonomous network calls. Host user presence and signed receipts form the independent boundary.

**Alternative rejected:** Resuming LangGraph first and letting the tool execute GitHub operations would either expose credentials to the Agent Server or require trusting an unauthenticated network call from it.

### 4. Canonicalize and freeze the source before publication

The publisher resolves the local path without symlinks and requires it to be beneath an authorized root. It invokes Git with fixed argv and independently checks repository identity, clean status, unresolved operations, source ref, and commit SHA. Owner is always `chapter-N3xtron`; repository URL and push refspec are derived server-side.

Before GitHub mutation, the publisher creates a private temporary bare staging repository or bundle containing the exact approved commit and target branch. Subsequent working-tree or branch movement cannot alter staged content. The staging location and publisher state are never mounted into Docker.

**Why:** A mutable shared working tree creates a time-of-check/time-of-use race. Publication must bind to content, not merely a branch name or path.

### 5. Limit the privileged operation to create-and-first-push

The host publisher validates that the target does not exist, then uses the host GitHub CLI with explicit owner/name, visibility, staged source, target branch, and first push. It does not accept arbitrary URLs, refspecs, CLI flags, environment overrides, or shell text. It verifies the GitHub repository identity and remote branch SHA after pushing.

If creation succeeds and push fails, the publisher attempts deletion only when its durable state proves that the same request created that previously absent repository and the initial approval disclosed this cleanup. It records partial failure if deletion is unavailable or unverifiable.

**Why:** A fixed operation is reviewable and testable. General host command execution would turn the publisher into a credentialed remote shell.

### 6. Use signed, durable, non-secret receipts for coordination

Publisher state records request digest, lifecycle state, expiry, operation ownership, timestamps, remote identifiers, expected and observed SHAs, and cleanup result. Terminal receipts are canonical JSON signed by a publisher key held outside Docker. The Agent Server receives only the receipt and verification public key.

The digest is the idempotency key. State transitions are monotonic, execution is locked per digest, and replay returns the existing terminal receipt. Logs and receipts pass through explicit redaction and never include credentials, authorization headers, credential-helper output, unrelated files, or command environments.

**Why:** The graph needs durable truth after restart without gaining privileged credentials or the ability to fabricate successful publication.

### 7. Keep the publisher outside the existing general sidecar

The launcher manages the publisher as a distinct host process with its own PID, restrictive state directory, health check, and redacted log. The existing sidecar may proxy only unprivileged status needed by the browser, but it does not inherit the publisher credential or execute publication commands.

**Why:** A small privileged computing base is easier to audit and prevents unrelated folder-picker or sidecar endpoints from inheriting GitHub authority.

## Risks / Trade-offs

- **[Two-stage external operation]** Repository creation can succeed while push or verification fails. → Disclose the condition before approval, attempt narrowly scoped cleanup, and report residual uncertainty rather than claiming atomicity.
- **[Host confirmation fatigue or spoofing]** Autonomous code could attempt to trigger nuisance prompts. → Require matching pending interrupt state, exact digest display, rate limits, one active prompt, expiry, and no remote effect without explicit host confirmation.
- **[Broad host GitHub login permissions]** The existing account credential may authorize more than this feature permits. → Enforce owner and operation in code, use fixed argv, test adversarial inputs, and prefer the narrowest host credential GitHub supports.
- **[Source race]** Repository state can change after the approval card renders. → Revalidate immediately, freeze the exact commit before mutation, and require new approval on mismatch.
- **[Publisher compromise]** The host publisher is privileged. → Keep it small, non-agentic, loopback-only, shell-free, dependency-minimal, separately logged, and unable to perform arbitrary repository or GitHub operations.
- **[Platform coupling]** Host-native confirmation and Keychain use are macOS-specific. → Treat this change as a local macOS deployment feature; do not silently fall back to container credentials on other platforms.
- **[Existing autonomous shell exposure]** `LocalShellBackend` can access any path and process data visible inside its container. → Keep all publisher credentials and state outside Docker, preserve masked credential mounts, and track broader autonomous sandbox hardening separately.

## Migration Plan

1. Add policy, canonicalization, digest, receipt, and publisher tests with a fake GitHub adapter; keep publication disabled.
2. Add the interrupted publication-request tool and specialized approval presentation while retaining the current graph topology.
3. Add the standalone host publisher with an in-memory/fake credential adapter, host confirmation abstraction, signed receipts, and no Docker access.
4. Wire launcher lifecycle and loopback health checks; verify the Agent Server has no publisher credential, state mount, SSH agent, GitHub configuration, or Docker socket.
5. Run adversarial, restart, idempotency, source-race, and failure tests against a disposable local/fake remote.
6. Perform an explicitly approved live canary using a unique test repository under `chapter-N3xtron`, verify the remote SHA and receipt, then remove the canary only through a separate human-authorized cleanup.
7. Enable the feature only after the canary and security inspection pass.

Rollback disables the publication tool and stops the host publisher. Existing local repositories, autonomous work, pending source changes, and retained non-secret receipts remain intact. No migration places credentials into the Agent Server.
