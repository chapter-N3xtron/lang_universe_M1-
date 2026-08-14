## 1. Exact Workspace and Runtime Identity

- [x] 1.1 Add tests proving an existing empty selected directory is valid, remains canonical across refresh/reopen/resume, and is never replaced by the home directory, `/workspace`, or a sibling repository. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [x] 1.2 Preserve the exact selected workspace through frontend state, thread updates, Jasper handoff, direct Coding selection, nested interrupts, and Coding completion without repopulating it from an unrelated default.
- [x] 1.3 Add a server-produced execution manifest distinguishing Mac-host filesystem origin, exact selected repository, Linux-container command runtime, and approved-host-operation availability.
- [x] 1.4 Update Jasper and Coding instructions and result formatting to use the execution manifest, prohibit repository discovery outside the selected path, and request a host operation for macOS-only work rather than claiming host mutation.

## 2. Typed Host-Operation Contract

- [x] 2.1 Define strict request and receipt schemas, canonical action categories, immutable argv/path/URL/hash/mutation/privilege/timeout/rollback fields, expiry, deterministic digest, and monotonic lifecycle states. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [x] 2.2 Implement canonical path and executable resolution, authorized-root checks, symlink and alias rejection, content hashing, mutable-input revalidation, bounded output, redaction, and single-use locking.
- [x] 2.3 Implement independent policies for host inspection, HTTPS download/verification, Homebrew operations, application staging/installation, and native application invocation.
- [x] 2.4 Add fail-closed denials for shell strings, shell metacharacters, arbitrary interpreters or executables, model-provided environment variables, automatic privilege escalation, persistence, credential access, GitHub publication, remote Git, SSH, security-policy changes, and Docker control.

## 3. Standalone macOS Executor

- [x] 3.1 Create a separate non-agent host process with loopback-only bounded endpoints, minimal environment, restrictive state/staging directories, health reporting, rate limiting, one active confirmation, and no general command endpoint.
- [x] 3.2 Implement the read-only host inspection adapter for macOS version, architecture, disk space, approved path metadata, and application presence/version with bounded fact-only output.
- [x] 3.3 Implement bounded HTTPS download, redirect/domain/size policy, checksum and archive verification, provenance recording, private staging, and approved-destination copy behavior.
- [x] 3.4 Implement exact Homebrew formula/cask operations with resolved executable and denied taps, services, broad upgrades/cleanup, arbitrary options, and shell hooks.
- [x] 3.5 Implement typed DMG/archive application staging and installation using fixed host operations, signature/notarization assessment, approved destination policy, detach, verification, and no automatic administrator authorization.
- [x] 3.6 Implement native Blender/application invocation with fixed executable/argv, approved working and output paths, hash-bound scripts/configuration, timeout, process-group cancellation, and outcome verification.
- [x] 3.7 Implement category-specific rollback accounting, partial-state reporting, idempotent restart recovery, and signed redacted terminal receipts.

## 4. Host User Presence and LangGraph HITL

- [x] 4.1 Add one typed `request_macos_host_operation` tool to the existing one-node Coding agent without adding graph nodes, edges, supervisors, approval models, or a custom graph runtime.
- [x] 4.2 Configure documented Deep Agents `interrupt_on` approve/reject behavior for the host-operation tool in autonomous and approval modes while preserving uninterrupted autonomous repository-local work. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [x] 4.3 Add independent pending-interrupt verification and native macOS confirmation displaying the digest, action, argv, paths, downloads, hashes, mutations, privilege level, timeout, and rollback limits before host execution.
- [x] 4.4 Verify signed receipts after standard LangGraph resume and reject missing, forged, replayed, expired, mismatched, changed-input, non-terminal, or unverifiable receipts.
- [x] 4.5 Preserve rejection, cancellation, expiry, restart, duplicate resume, frontend resume failure, and executor recovery through the existing parent checkpoint and `Command` decision path.

## 5. Human Approval Interface

- [x] 5.1 Add a specialized macOS operation approval card that clearly distinguishes Mac-host effects from Linux-container effects and displays every immutable review field. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [x] 5.2 Coordinate host-native confirmation and signed receipt creation while the LangGraph interrupt remains pending, then submit the ordinary approve decision only for the matching request.
- [x] 5.3 Exclude host operations from bulk approval, generic resolve behavior, implicit approval, and edit-in-place; changed fields must create a new request.
- [x] 5.4 Present required manual authorization, GUI interaction, rejection, cancellation, expiry, timeout, partial mutation, rollback uncertainty, and verified success without claiming unverified installation.

## 6. Deployment and Security Boundary

- [x] 6.1 Add executor lifecycle management, restrictive permissions, PID handling, health checks, cancellation, and redacted logs to the launcher without giving executor authority to the general sidecar.
- [x] 6.2 Verify Docker receives no executor control secret, signing key, writable state, staging directory, host credential, Keychain access, private key, SSH agent, GitHub configuration, or Docker socket.
- [x] 6.3 Verify the macOS executor cannot invoke GitHub publishing, remote push, SSH, Docker, arbitrary shells, credential helpers, login items, launch agents, or automatic privilege escalation.
- [x] 6.4 Update security, persistence, deployment, runtime-identity, manual-interaction, and rollback documentation with the hybrid trust model and macOS-specific limitations.

## 7. Verification and Release Gates

- [x] 7.1 Run unit tests for workspace preservation, execution manifests, schema validation, action policy, canonicalization, hashing, digest stability, expiry, locking, signing, redaction, timeout, cancellation, rollback, and restart recovery.
- [x] 7.2 Run HITL integration tests proving autonomous local work remains uninterrupted, only host actions interrupt, exact approval survives restart, rejection has no host effect, and receipts return to Coding without granting host authority.
- [x] 7.3 Run browser tests for exact workspace persistence, runtime labeling, immutable approval details, disabled bulk/resolve/edit paths, native-confirmation coordination, manual-step presentation, and receipt states.
- [x] 7.4 Run adversarial tests from the Agent Server for sibling-repository discovery, direct executor calls, prompt flooding, forged/replayed receipts, path and script races, arbitrary executable/argv/environment injection, credential probes, GitHub/SSH/Docker attempts, and unrelated-process cancellation.
- [x] 7.5 Run fake-adapter failure tests for download redirects and size limits, checksum failure, Homebrew failure, DMG mount/copy/detach failure, signature uncertainty, Blender timeout, partial installation, cancellation, and unverifiable rollback.
- [ ] 7.6 Inspect the rebuilt deployment boundary, then run a separately approved read-only macOS inspection canary before any mutation; confirm the receipt reports the physical Mac while ordinary Coding still reports Linux-container execution. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 7.7 Run a Blender staging or installation canary only after separate explicit human approval and all non-mutating gates pass; do not automate administrator, Gatekeeper, license, or GUI consent. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 7.8 Run strict OpenSpec validation, focused backend/frontend checks, full available suites, production build, deployed health checks, and rollback verification; report unrelated failures separately.
