## Why

The deployed Agent Server currently combines credential-bearing model/provider clients with Coder's unrestricted `LocalShellBackend`, broad host-path mounts, and Librarian/Research file and retrieval tools. Path-deny rules and child-process environment filtering are useful safeguards, but they are not a security boundary: arbitrary code in the same container can inspect the server process, mounted files, and inherited deployment state. The deployment is currently stopped because restarting that arrangement would preserve this credential-exposure risk.

Coder and Librarian must remain useful without receiving raw API keys, passwords, tokens, signing keys, credential files, or equivalent authority. Their risky capabilities need distinct containers, while credential brokerage is designed and implemented as a later change.

This change also establishes a human-readable trust posture. The human must be able to see which container can perform which actions, where personal and work authority is separated, what a request or proposed feature would change, and what material risks remain. Communication must support understanding and refusal rather than pressure approval.

## What Changes

- Split the current monolithic runtime into a credential-bearing Agent Server control plane, a dedicated uncredentialed Coder worker, and a separate uncredentialed Librarian worker.
- Keep model invocation, LangGraph orchestration, checkpoints, interrupts, and existing credentialed provider adapters in the control plane during this transitional phase; move Coder filesystem/shell execution and Librarian filesystem/content-processing capabilities behind typed worker contracts.
- Preserve Coder's useful repository-local reads, writes, local Git, dependency commands, tests, and builds without exposing Agent Server secrets, host credentials, Docker control, or unrelated private paths.
- Preserve the existing Librarian/Research profile, provenance, web evidence workflow, uploaded-source handling, saved evidence, and selected-workspace reads in a separate container. Keep workspace mutation disabled by default while defining an independently gated typed write capability for a later authorization change.
- Place the Agent Server, Coder worker, and Librarian worker in one Docker Compose backend project with grouped start, stop, restart/recreate, status, health, and rollback behavior. Keep the workers in separate containers and networks even though lifecycle operations are grouped.
- Add a canonical trust-domain registry, server-produced per-agent capability manifests, a persistent human-readable Trust Map, and neutral trust-impact notices for requests and proposed repository features.
- Preserve the standalone macOS host executor and any future GitHub publisher as separate trust domains; neither worker receives their control authority.
- Leave frontend containerization as a documented future extension of the Docker project, not part of this change.

## Capabilities

### New Capabilities

- `isolated-agent-workers`: Credential-separated Coder and Librarian capability workers, grouped backend lifecycle, explicit trust-domain manifests, and human-readable trust-impact communication.

### Modified Capabilities

None. Existing Coder, Research, macOS host-operation, and proposed GitHub publication contracts remain applicable and are constrained by this new isolation boundary.

## Impact

- Docker Compose topology, worker images, backend launcher, health checks, networking, mounts, environment construction, and rollback.
- Deep Agents backend integration for remote Coder filesystem and execution operations.
- Librarian/Research file access, source ingestion, retrieval-result processing, evidence persistence, and provider-call boundaries.
- LangGraph handoff state, cancellation, timeout, idempotency, worker restart recovery, and execution manifests.
- Frontend runtime status, Trust Map, trust-impact review, accessibility, and anti-coercive decision presentation.
- Security and adversarial tests proving workers cannot recover Agent Server, GitHub, host-executor, SSH, cloud, or host credentials.
- Deployment remains unavailable until an operator-approved rebuild passes the non-secret environment, mount, network, health, and functional canaries.

## Deferred Work

- AI-provider, GitHub, communication, and other credential brokers.
- Granting Librarian workspace-write authority.
- Frontend containerization.
- New host-operation or GitHub-publication authority.
- A universal service mesh, custom graph runtime, or replacement for documented LangGraph persistence and interrupts.
