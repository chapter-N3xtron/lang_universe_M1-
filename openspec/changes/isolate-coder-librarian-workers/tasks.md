## 1. Baseline and Contracts

- [ ] 1.1 Capture the current Agent Server, Coder, and Librarian process, environment-name, mount, network, tool, provider-call, workspace, checkpoint, and lifecycle boundaries without reading or recording secret values; add failing tests that demonstrate credential/tool colocation. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 1.2 Define versioned typed worker request/result envelopes binding service identity, thread, run, task digest, canonical workspace, mode, capabilities, deadline, idempotency, cancellation, bounded output, and runtime evidence. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 1.3 Define the canonical trust-domain registry, separate tenant/domain/capability/scope/duration/authorization fields, `unclassified-authority` fail-closed behavior, and server-produced per-service capability manifest. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 1.4 Add contract and adversarial fixtures using fake credential markers so secret-exclusion tests never inspect or print real credentials. Governance reference: GOVERNANCE_FRAMEWORK.md.

## 2. Coder Worker Isolation

- [ ] 2.1 Select and document a task-bound OS/container/sandbox mechanism implementing the documented Deep Agents backend protocol; prove shell commands cannot escape the canonical selected repository before enabling autonomous execution. Do not rely on prompts, virtual paths, or deny globs as the primary boundary. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 2.2 Build a dedicated non-root Coder worker image and typed service for repository reads/writes, local Git, dependency commands, formatting, linting, tests, builds, bounded execution, process-tree cancellation, and idempotent results. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 2.3 Replace Agent Server `LocalShellBackend` and local repository filesystem access with the remote worker backend while preserving Coder read-only, approval, autonomous, interrupt, checkpoint, and result semantics. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 2.4 Remove broad repository/home mounts and Coder toolchain state from the Agent Server; give Coder only task-bound workspace state, an explicit minimal child environment, private temporary/cache locations, resource limits, and no service-environment inheritance. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 2.5 Preserve the existing macOS host-operation request/receipt path in the control plane without exposing executor control, signing state, host credentials, Docker, SSH, or GitHub authority to Coder. Governance reference: GOVERNANCE_FRAMEWORK.md.

## 3. Librarian Worker Isolation

- [ ] 3.1 Preserve the existing `research` profile identity while exposing Librarian as its human-facing role; retain thread/session relationships, handoffs, provenance, evidence IDs, canonical reports, and saved-source reopening. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 3.2 Build a separate non-root Librarian worker image and typed service for bounded selected-workspace reads, approved uploaded-source processing, saved-evidence/report processing, and untrusted retrieved-content analysis, with no shell, local Git, package installation, or Coder access. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 3.3 Move Librarian filesystem, ingestion, and content-processing tools out of the Agent Server while keeping existing authenticated model/search provider calls as explicit bounded transitional control-plane adapters; pass no credential or reusable authenticated client to Librarian. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 3.4 Define future typed Librarian writes as unavailable capabilities in the manifest; retain deployed read-only behavior and require a later OpenSpec trust-domain change before enabling any write root. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 3.5 Add redirect, domain, size, content-type, private-address, output-bound, prompt-injection, and provenance tests for any credential-free Librarian retrieval allowed from its worker. Governance reference: GOVERNANCE_FRAMEWORK.md.

## 4. Docker Backend Group and Network Policy

- [ ] 4.1 Add `langgraph-api`, `coder-worker`, and `librarian-worker` to one stable Docker Compose backend project with separate images, users, filesystems, environments, resources, health checks, and networks. Grouped lifecycle must not create shared authority. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 4.2 Add explicit internal control-to-Coder and control-to-Librarian paths while denying worker-to-worker access, Docker socket access, host gateways, private/LAN ranges, cloud metadata, control-plane administration, host executor control, publisher control, and unrelated services. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 4.3 Add launcher commands for grouped start, stop, recreate/restart, status, bounded logs, and rollback; distinguish liveness, readiness, policy validity, configuration application, and per-agent availability. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 4.4 Ensure worker images, build contexts, layers, mounts, volumes, environments, logs, and caches contain no provider, GitHub, SSH, cloud, communication, host, or signing credentials; keep private executor state outside Docker. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 4.5 Preserve a stable extension point for later frontend containerization without adding a frontend service or sharing backend credentials in this change. Governance reference: GOVERNANCE_FRAMEWORK.md.

## 5. Trust Map and Anti-Coercive Impact Communication

- [ ] 5.1 Produce and verify runtime capability manifests for the control plane, Coder, Librarian, macOS executor, and configured publisher, distinguishing verified facts, intended policy, unavailable evidence, and current health. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 5.2 Add an accessible persistent Trust Map with plain-language summaries and inspectable details for tenants, domains, capabilities, scopes, data flows, network destinations, credential exposure, approvals, health, and redacted receipts. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 5.3 Add typed Trust Impact Notices for agent requests and proposed repository features, showing the stated request separately from inference, domain/tenant changes, data movement, acting boundary, new authority, affected people, material risks, reversibility, rollback limits, alternatives, no-action outcome, approval scope, and expected evidence. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 5.4 Enforce equal-access decline/defer/detail actions, no preselected approval or bulk cross-domain approval, no countdown or manufactured urgency, no repeated persuasion, no unrelated-service penalty after refusal, and invalidation when material fields change. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 5.5 Add browser and accessibility tests proving concise summaries do not hide material consequences and technical detail remains available without requiring approval. Governance reference: GOVERNANCE_FRAMEWORK.md.

## 6. Durability, Failure, and Compatibility

- [ ] 6.1 Add durable idempotency, timeout, cancellation, uncertain-result, duplicate-delivery, and worker-restart behavior that preserves Agent Server checkpoint authority and never silently replays a mutation. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 6.2 Verify Coder completion and nested HITL results, Librarian evidence/report durability, Jasper handoffs, direct specialist selection, model selection, and session provenance remain compatible. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 6.3 Verify macOS host-operation and future GitHub publication requests remain separate privileged domains returning only verified redacted receipts to workers. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 6.4 Add degraded-mode behavior that reports an unavailable specialist plainly and never silently reroutes its authority or represents partial backend health as complete health. Governance reference: GOVERNANCE_FRAMEWORK.md.

## 7. Security and Functional Verification

- [ ] 7.1 Run unit and integration tests for typed worker contracts, canonical workspace leases, path/symlink escape, environment construction, result bounds, manifests, registry classification, data-flow notices, cancellation, restart, and idempotency. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 7.2 Run adversarial built-image and deployed probes for `/proc`, environment, mounts, layers, caches, temporary files, sibling paths, network scanning, SSRF, metadata endpoints, Docker, host executor, GitHub/SSH/cloud configuration, credential helpers, forged worker results, and cross-worker calls using fake markers only. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 7.3 Verify Coder remains useful through read, write, edit, delete, local Git, dependency, formatting, lint, test, build, approval, autonomous, timeout, and cancellation tests inside the exact selected repository. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 7.4 Verify Librarian remains useful through selected-workspace reads, bounded authenticated-search result processing, permitted URL retrieval, uploaded-source processing, evidence provenance, report reopening, and explicit write/execute denial. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 7.5 Run backend, frontend, browser, production-build, Compose-render, image-policy, and rollback suites; report source-only evidence separately from rebuilt deployed evidence. Governance reference: GOVERNANCE_FRAMEWORK.md.

## 8. Operator Migration and Release Gate

- [ ] 8.1 Present the final trust-domain diff and exact operator migration plan before changing the running deployment; keep the backend stopped until the human explicitly authorizes rebuild/start. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 8.2 Build fresh images, inspect them before start, migrate without copying credential-bearing worker layers or volumes, and verify per-service environments, mounts, networks, image digests, policies, and health. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 8.3 Run separately approved read-only Coder and Librarian canaries, then a separately approved repository-local Coder write/test canary; do not start the macOS executor or perform host/GitHub mutations under this migration approval. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 8.4 Verify grouped stop/start/recreate, service-specific failure reporting, durable restart, and rollback. Rollback must never automatically restore the former credential-plus-shell monolith. Governance reference: GOVERNANCE_FRAMEWORK.md.
- [ ] 8.5 Install or restore the OpenSpec CLI, run strict validation for `isolate-coder-librarian-workers`, resolve all artifact errors, and record that CLI validation separately from implementation and deployment evidence. Governance reference: GOVERNANCE_FRAMEWORK.md.

## Deferred Changes

- Credential brokers for personal/work AI providers, personal/work GitHub, communications, and other trust domains.
- Enabling Librarian workspace writes.
- Frontend containerization.
- Additional host, publisher, cloud, communication, financial, or policy-administration authority.
