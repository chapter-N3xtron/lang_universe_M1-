## Context

The current `langgraph-api` container loads model and research-provider credentials, mounts broad host paths, constructs Coder with Deep Agents `LocalShellBackend`, and constructs Librarian/Research with local filesystem and retrieval tools. `LocalShellBackend` explicitly provides no sandboxing; its virtual path mode does not constrain shell commands. Because these capabilities share one process/container security boundary, Coder can potentially inspect credentials needed by the Agent Server even if its immediate child environment is filtered.

The existing macOS host executor correctly lives outside Docker and exposes only a public receipt-verification key to the Agent Server. The proposed GitHub publisher similarly requires a separate privileged boundary. This change must preserve those separations.

“Librarian” in this change is the intended human-facing name for the existing `research` profile. Migration must not create a second hidden research identity or lose existing Research provenance, thread relationships, evidence IDs, or reports.

## Goals / Non-Goals

**Goals:**

- Remove file, shell, content-ingestion, and untrusted-content processing authority from the credential-bearing Agent Server.
- Run Coder and Librarian capabilities in separate uncredentialed Docker containers with independent policy, mounts, networking, resources, and health.
- Preserve useful Coder and Librarian behavior and existing LangGraph checkpoint/HITL semantics.
- Start, stop, recreate, inspect, and roll back the backend services as one Docker Compose project without collapsing their security boundaries.
- Make the actual trust boundary, tenant, capability scope, data flow, residual risk, and authorization need understandable to the human.
- Fail closed when the runtime manifest and actual deployment disagree.

**Non-Goals:**

- Implementing a credential broker or passing provider credentials to workers.
- Moving the model loop into a worker while cloud inference still requires a raw credential.
- Giving Librarian general shell access or enabling workspace writes in this change.
- Giving either worker Docker control, macOS host authority, GitHub publication authority, SSH, credential-helper, Keychain, or policy-administration authority.
- Containerizing the frontend now.
- Treating Docker Compose grouping as permission sharing.

## Architecture

```text
                         personal/work provider credentials
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────┐
│ Agent Server control plane                                      │
│ LangGraph graphs · model calls · checkpoints · HITL · manifests │
│ no repository shell · no local agent filesystem backend         │
└───────────────┬──────────────────────────────┬───────────────────┘
                │ typed worker protocol        │ typed worker protocol
                ▼                              ▼
┌───────────────────────────┐     ┌───────────────────────────────┐
│ Coder worker              │     │ Librarian worker              │
│ selected repository       │     │ bounded sources/workspace     │
│ read/write/local Git      │     │ reads and content processing  │
│ shell/tests/builds        │     │ no shell; writes disabled     │
│ no injected credentials   │     │ no injected credentials       │
└───────────────────────────┘     └───────────────────────────────┘

        separately operated boundaries, not members of worker networks
        ┌──────────────────────┐   ┌────────────────────────────┐
        │ macOS host executor  │   │ future GitHub publisher    │
        └──────────────────────┘   └────────────────────────────┘
```

All three Docker services belong to one Compose project for lifecycle management. They remain separate services with separate filesystems, process namespaces, environment allowlists, resource limits, and network paths.

## Decisions

### 1. Split the agent control plane from capability workers

LangGraph orchestration, model invocation, selected-model policy, checkpoints, Store access, and human interrupts remain in the Agent Server. Coder's Deep Agents filesystem and execute operations use a remote backend implementing the documented backend protocol. Librarian's file/source-processing operations use a separate bounded worker contract.

The workers receive typed task envelopes, canonical workspace identity, bounded inputs, cancellation/deadline data, and opaque correlation identifiers. They do not receive prompts or state fields containing credentials. Results are bounded, typed, and labeled with worker and runtime identity.

This is deliberately described as moving the agents' **capability execution**, not pretending that cloud model invocation can move without credentials. A later broker can allow more of each model loop to move without changing worker authority.

### 2. Keep Coder useful but uncredentialed

Coder retains selected-repository reads and writes, local Git operations, package/dependency commands, tests, builds, and bounded shell execution. The worker starts commands with an explicit minimal environment and never inherits the service or control-plane environment.

The worker receives no `.env` deployment file, API key, provider token, GitHub/SSH configuration, credential helper, host home directory, Docker socket, macOS executor state, signing material, cloud configuration, browser profile, or arbitrary host path. Sensitive path rules remain defense in depth and are not represented as the primary isolation mechanism.

A task-bound workspace lease identifies one canonical repository and allowed mode. The implementation must prove that shell execution cannot escape to sibling repositories or control-plane files. If a secure task-bound mount, namespace, or documented sandbox mechanism cannot be demonstrated, autonomous shell mode remains disabled rather than relying on prompt instructions or virtual paths.

### 3. Isolate Librarian independently from Coder

Librarian does not share Coder's image, filesystem, network, shell, process namespace, caches, or writable volumes. It retains bounded selected-workspace reads, approved uploaded-source processing, saved-evidence/report reopening, and processing of bounded provider results supplied through the control plane.

During this transitional change, authenticated search/model provider calls remain control-plane operations because placing their API keys in Librarian would defeat isolation. Raw or bounded retrieved content is treated as untrusted before it enters Librarian. Direct credential-free retrieval may run in Librarian only through an explicit URL/domain/size/redirect policy.

The worker contract reserves typed write operations with independently configurable roots, but the deployed Librarian manifest declares them unavailable. Enabling them requires a later OpenSpec change, human-visible trust-domain diff, policy, and tests; it is not activated by container migration.

### 4. Use deny-by-construction deployment boundaries

Worker images use a non-root runtime user, read-only root filesystem where compatible, `no-new-privileges`, dropped Linux capabilities, bounded PIDs/CPU/memory/output, private temporary storage, and explicit environment allowlists. No service receives the Docker socket. Control-plane and worker images are separately inspectable and pinned by digest in deployment records.

Coder and Librarian use distinct internal networks. They cannot call one another. Worker egress is denied by default and enabled only for a declared capability. Access to host gateways, LAN/private ranges, cloud metadata endpoints, control-plane administrative routes, and unrelated Compose services is denied. Grouped lifecycle does not imply a shared default network.

### 5. Preserve existing LangGraph authority and durable behavior

The Agent Server remains the sole owner of graph transitions, checkpoints, interrupts, and human authorization state. Worker requests are idempotent and bound to thread, run, task, workspace, mode, deadline, and request digest. A worker restart must not silently repeat a mutation. Cancellation targets only request-owned work.

Coder's existing approval/read-only/autonomous modes remain visible. Host-operation requests remain ordinary interrupted tools in the control plane and return only verified receipts. Librarian retains Research provenance and durable evidence IDs. Workers cannot approve, resume, or rewrite graph state.

### 6. Group lifecycle without grouping authority

The launcher owns one stable Compose project containing `langgraph-api`, `coder-worker`, and `librarian-worker`. `start`, `stop`, `restart`/recreate, `status`, logs, and rollback target the full backend group. Health checks distinguish process liveness, readiness, policy/configuration validity, and dependency availability.

The Agent Server does not report ready until both required workers are ready for their declared capabilities. A degraded mode may keep Jasper available only when the UI clearly identifies which specialist is unavailable and no request is silently rerouted. Recreate is used when configuration or images change; a plain process restart must not be described as applying new deployment configuration.

The future frontend container may join the project through a later change, but this proposal adds no frontend service, credential sharing, or network privilege in anticipation of it.

### 7. Establish a canonical trust-domain registry

The registry begins with these stable domain IDs:

1. `governance-policy`
2. `identity-credential-custody`
3. `agent-orchestration`
4. `ai-model-compute`
5. `code-execution`
6. `filesystem-workspace-artifacts`
7. `source-control-hosting`
8. `research-web-network`
9. `software-supply-chain`
10. `host-machine`
11. `cloud-deployment`
12. `durable-data-memory`
13. `private-communications`
14. `productivity-collaboration`
15. `public-publishing`
16. `device-sensory-attention`
17. `physical-connected-devices`
18. `financial-commercial-legal`
19. `sensitive-high-impact-records`
20. `security-observability-audit`
21. `extension-integration-administration`
22. `cross-domain-transfer`
23. `unclassified-authority`

Personal and work are separate security tenants, not permission labels. Capabilities such as read, write, execute, send, delete, publish, and administer remain distinct from domains. Exact resource scope and expiry remain distinct from capabilities. Unknown authority maps to `unclassified-authority` and cannot operate until human review and a versioned registry change.

### 8. Make trust impact understandable without coercion

A server-produced capability manifest is compared with deployment evidence and displayed in a persistent Trust Map. For each agent it shows container/runtime, tenant, trust domains, allowed actions, denied actions, resource scope, network destinations, credential exposure (`none` for workers), approval requirements, and health.

Before a request or proposed feature materially changes authority, a Trust Impact Notice separates the human's stated request from model inference and identifies affected domains/tenants, data movement, broker or executor involved, new capabilities, affected people, side effects, reversibility, rollback limits, lower-authority alternatives, no-action outcome, approval scope, and expected audit evidence.

The primary presentation is brief and plain-language, with inspectable technical details. Decline and defer are as accessible as acceptance. No countdown, preselected approval, emotional loading, repeated persuasion, or degraded unrelated service is permitted. Silence, attention, prior approval, or an agent's confidence never authorizes a new domain or capability.

### 9. Defer credential brokers without creating a hidden broker

This change does not add a generic proxy that accepts arbitrary provider, GitHub, email, or host actions. Existing control-plane model/provider adapters may perform only their existing typed calls and return bounded results. They must not expose authorization headers or general credential use to workers.

Future brokers will be separate changes organized by trust domain and personal/work tenant. Worker contracts use capability identities and receipts so a later broker can be introduced without placing raw secrets in worker environments.

## Risks / Trade-offs

- **[Control plane still holds credentials]** Isolation protects credentials from worker tools, but compromise of the Agent Server remains consequential. → Remove shell and broad workspace mounts from it, minimize its tools, and defer stronger provider isolation to broker changes.
- **[Workspace confinement complexity]** A persistent Compose worker cannot safely claim confinement merely because a library uses virtual paths. → Require task-bound OS/container isolation evidence; disable autonomous shell if it cannot be proven.
- **[Authenticated research remains mediated]** Librarian cannot independently call credentialed providers until a broker exists. → Keep existing typed provider calls in the control plane and disclose this transitional data flow.
- **[More moving services]** Group restart can hide which dependency failed. → Report per-service health and never collapse partial readiness into a green group status.
- **[Network exfiltration]** An uncredentialed worker may still expose repository or research data. → Use explicit egress policy, destination controls, bounded outputs, and cross-domain transfer notices.
- **[Trust UI overload]** A complete registry can overwhelm the human. → Use a short current-impact summary with optional details, never omit material consequences.
- **[False sense of completion]** Containerization alone does not implement credential brokerage or guarantee that selected repositories contain no human-authored secrets. → State residual risk and keep broker and repository-secret handling as explicit follow-up work.

## Migration Plan

1. Record the current process, environment, mounts, networks, capabilities, and agent behavior without exposing credential values.
2. Add worker contracts and fake workers; preserve graph, HITL, provenance, and evidence behavior under tests.
3. Build Coder and Librarian images and prove independent confinement before removing local tool execution.
4. Remove repository mounts, local shell, Librarian filesystem/content processing, and worker-only dependencies from the Agent Server.
5. Add grouped Compose lifecycle, per-service health, capability manifests, Trust Map, and impact notices.
6. Rebuild without reusing credential-bearing worker images or volumes; verify mounts and environments before starting user traffic.
7. Run read-only canaries first, then separately authorized Coder write/test and Librarian retrieval canaries.
8. Keep the macOS executor stopped until its existing native canary gate is separately approved.

Rollback stops the full backend group, restores the last known credential-isolated images and configuration, and preserves LangGraph/PostgreSQL state. Rollback must never restore the monolithic credential-plus-shell container as an automatic fallback. If no safe isolated version is available, backend specialists remain unavailable and the UI explains the boundary plainly.
