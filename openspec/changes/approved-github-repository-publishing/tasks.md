## 1. Publication Contract and Policy

- [ ] 1.1 Define typed publication-request fields, canonical owner/name/path/ref rules, visibility values, derived URL/refspec, expiry, and deterministic digest behavior with no credential-bearing fields. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 1.2 Implement and test authorized-root resolution, symlink rejection, Git repository identity, clean-worktree checks, unresolved-operation checks, exact source-ref/SHA validation, and frozen snapshot staging before any remote effect.
- [ ] 1.3 Define monotonic request states, single-use locking, idempotent replay, terminal outcomes, redacted receipt fields, and canonical receipt signing/verification.
- [ ] 1.4 Add policy tests rejecting alternate owners, existing targets, arbitrary URLs or commands, extra refs or tags, force push, changed inputs, expired requests, and unsafe cleanup targets.

## 2. Credential-Isolated Host Publisher

- [ ] 2.1 Create a standalone non-agent host publisher process with loopback-only bounded endpoints, a restrictive state/staging directory, minimal environment, health reporting, rate limiting, and no general command endpoint.
- [ ] 2.2 Add an injectable GitHub adapter whose production implementation uses only the host `chapter-N3xtron` GitHub login and fixed argv operations for target-existence check, repository creation, exact first push, and remote-SHA verification.
- [ ] 2.3 Add independent pending-interrupt verification and host-native macOS confirmation that displays the canonical digest, owner/name, visibility, source SHA, target branch, and partial-failure cleanup warning before credentials are used. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 2.4 Persist signed, non-secret receipts and expose only bounded request status and receipt retrieval to unprivileged clients; keep signing material and writable publisher state outside Docker.
- [ ] 2.5 Implement partial-failure handling that attempts deletion only for a previously absent repository proven to have been created by the same request, and records unverifiable cleanup without claiming atomic rollback.

## 3. Documented LangGraph HITL Integration

- [ ] 3.1 Add one narrowly typed `request_github_repository_publication` tool to the existing one-node Coding agent without adding graph nodes, edges, supervisors, approval models, or a custom execution engine.
- [ ] 3.2 Configure documented Deep Agents `interrupt_on` approve/reject behavior for the publication tool in both autonomous and approval modes while preserving uninterrupted autonomous local filesystem, shell, test, build, `git init`, and local commit work. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 3.3 Canonicalize the tool request before presentation and verify the publisher-signed receipt after resume; reject missing, mismatched, expired, forged, or non-terminal receipts.
- [ ] 3.4 Verify nested publication interrupts, rejection, restart, duplicate resume, and terminal receipt recovery through the existing parent LangGraph checkpoint and `Command` resume path.

## 4. Human Approval Interface

- [ ] 4.1 Add a specialized publication approval card that displays every required immutable field, clearly distinguishes public from private visibility, identifies the exact commit/refspec, and discloses non-atomic create/push cleanup risk. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 4.2 Make the approval action coordinate host-native confirmation and publisher receipt creation while the LangGraph interrupt remains pending, then submit the ordinary approve decision only for the matching terminal receipt.
- [ ] 4.3 Exclude publication from bulk approval, generic resolve behavior, implicit approval, and edit-in-place; require a new request whenever a reviewed field changes.
- [ ] 4.4 Present rejection, cancellation, expiry, collision, partial failure, cleanup uncertainty, and successful verified receipt states without exposing credentials or coercing approval.

## 5. Deployment and Credential Boundary

- [ ] 5.1 Add publisher lifecycle management, restrictive permissions, health checks, PID handling, and redacted logs to the existing launcher without placing GitHub credentials in the Agent Server process.
- [ ] 5.2 Verify Docker configuration supplies no GitHub token, GitHub CLI configuration, private key, SSH agent socket, publisher signing key, writable publisher state, staging directory, Keychain access, or Docker socket to autonomous Coding.
- [ ] 5.3 Verify the publisher credential remains in the host Keychain/GitHub CLI boundary, the active account is exactly `chapter-N3xtron`, and credential text never appears in argv, files, logs, receipts, graph state, checkpoints, or error output.
- [ ] 5.4 Update security, persistence, deployment, and rollback documentation with the two-domain trust model and the residual non-atomic GitHub failure case.

## 6. Verification and Adversarial Tests

- [ ] 6.1 Run unit tests for canonicalization, digest stability, expiry, state transitions, locking, signing, redaction, source freezing, GitHub policy, and cleanup ownership using fake Git and GitHub adapters.
- [ ] 6.2 Run HITL integration tests proving autonomous long-horizon work remains uninterrupted, only publication interrupts, approve/reject survives restart, changed requests require new approval, and duplicate delivery is idempotent.
- [ ] 6.3 Run browser tests for exact approval fields, visibility clarity, host-confirmation coordination, disabled bulk/resolve paths, rejection, cancellation, expiry, failure, and receipt presentation.
- [ ] 6.4 Run adversarial tests from the Agent Server for environment and process probes, credential-file and socket access, direct publisher requests, forged or replayed digests and receipts, alternate owners/URLs/refspecs, prompt flooding, source races, and Docker access.
- [ ] 6.5 Run failure-injection tests for name collision, GitHub API timeout, creation failure, push failure, verification failure, publisher restart, Agent Server restart, frontend resume failure, cleanup success, and cleanup uncertainty.
- [ ] 6.6 Inspect the rebuilt deployed container and host publisher boundary, then perform a uniquely named live canary under `chapter-N3xtron` only after separate explicit human authorization; verify the remote SHA and receipt and require separate authorization for canary deletion. Governance reference: GOVERNANCE_FRAMEWORK.md.

## 7. Release Gate

- [ ] 7.1 Run strict OpenSpec validation, focused backend and frontend checks, full available test suites, production frontend build, deployed health checks, and exact source-versus-deployment verification; report unrelated failures separately.
- [ ] 7.2 Confirm rollback disables the publication tool and host publisher without affecting local repositories, autonomous Coding work, pending source changes, or retained non-secret receipts.
