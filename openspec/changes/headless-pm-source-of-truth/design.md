## Context

A headless project-management authority is needed for durable work records, while the LangGraph Agent Server remains the execution boundary and TanStack/Jasper remains a projection and explanation surface. This change selects Plane and Temporal, but authorizes planning only. Existing changes separately describe visualization presentation/editing, durable interaction records, session anatomy, and human-centered session review. None establishes a PM authority or integration contract.

## Goals / Non-Goals

**Goals:**

- Establish Plane as the authoritative self-hosted project-management system and keep Plane's native browser UI first-class for complete human editing.
- Establish Temporal as the self-hosted workflow/orchestration system for future integration jobs, retries, schedules, and durable workflow history; it is not a PM record store.
- Capture a reviewable dependency, persistence, security, configuration, readiness, image provenance, rollback, and verification plan before implementation.
- Preserve explicit attribution, audit, preview, approval, revision/conflict, and deep-link requirements.
- Keep OpenSpec and agent-run relationships reference-based and rebuildable.

**Non-Goals:**

- Installing or starting Plane, Temporal, Docker Compose, or any dependency.
- Building deployment files, a PM engine, an integration adapter, a dashboard, a ticket database, or a synchronization job.
- Moving PM data into LangGraph checkpoints, Temporal workflow history, todos, governance artifacts, or the existing session catalog.
- Inventing exact image tags, service health endpoints, licensing conclusions, or production guarantees.

## Decisions

1. **Plane is the PM authority.** Plane's self-hosted application and native UI own PM records. The future adapter reads and writes through an explicit supported API boundary; TanStack/Jasper keeps only bounded, rebuildable projections and stable references.

2. **Temporal is orchestration, not authority.** Future Plane integration operations run as explicitly scoped Temporal workflows and activities. Temporal may retain workflow inputs, outputs, retry history, and bounded PM identifiers required for execution, but must not become a copied PM database or the authority for PM fields.

3. **Self-hosted components are explicit.** Plane's official Docker Compose topology commonly includes web, admin, space, API, worker, beat-worker, migrator, live, PostgreSQL, Redis, RabbitMQ, MinIO, and Caddy/reverse proxy. Exact service set and versions remain a decision task. Plane persistent volumes are required for database, queue/cache where applicable, and object-storage data in a local evaluation; production guidance should be evaluated with external managed PostgreSQL, Redis, RabbitMQ, and object storage. Plane configuration belongs in environment variables or `.env`; sample secrets must never be reused.

4. **Temporal dependency boundary is explicit.** Temporal uses `temporalio/server` as the core image with configured roles rather than separate role-specific images, and may use `temporalio/ui`. It requires PostgreSQL, MySQL, or Cassandra; Elasticsearch is optional for visibility. `temporalio/auto-setup` is an initialization/migration option, not an assumed production role. Temporal state persists in its backing database. Frontend gRPC (commonly port 7233) and UI ports must be reachable only on trusted internal networks unless a later reviewed boundary says otherwise.

5. **Local Compose differs from production.** A local Compose plan may run the documented dependency topology with named persistent volumes for repeatable evaluation. Production must separately decide managed database, cache, broker, object storage, search/visibility, backups, upgrades, ingress, and secret-management services. Local Compose success is not evidence of production readiness.

6. **LangGraph Agent Server integration is narrow.** The Agent Server requests read or proposes a mutation through an integration boundary; it does not query Plane's database, own PM records, or directly control Temporal internals. A future adapter submits attributed Temporal work with a bounded PM record identifier, revision basis, and correlation identifier. The Agent Server may receive status and links, not an unbounded workflow or PM dump.

7. **Identity and human control are explicit.** The eventual integration uses a named least-privileged Jasper/service identity distinct from the requesting person. Every mutation records actor, target, revision basis, preview/result, workflow correlation, and audit reference. Approval classes, authorization, and conflict UX remain implementation decisions, but no stale read may silently overwrite a newer human edit.

8. **Health and readiness are acceptance contracts, not invented endpoints.** Official Plane material supplied for this change does not establish a complete health/readiness contract. Temporal gRPC health indicates process responsiveness, not full dependency readiness. A later implementation task must define service-specific probes, dependency checks, startup ordering, failure semantics, and human verification using the chosen versions. Until then, no endpoint or status path is normative.

9. **Image and configuration provenance is mandatory.** Later implementation must record image repository, exact selected version/tag, immutable digest, source URL, retrieval date, configuration schema/version, and upgrade notes for every Plane, Temporal, and dependency image. No exact tag is selected here. Secrets must be generated per deployment, supplied through an approved secret mechanism, excluded from committed artifacts and logs, and never copied from examples.

10. **References, not copies, cross system boundaries.** OpenSpec changes, runs, and checkpoints carry stable Plane identifiers/URLs and bounded workflow references as context. Authoritative details are fetched from Plane, keeping checkpoint size and rebuild semantics independent of PM and Temporal storage.

11. **Projection semantics are intentionally lightweight.** Lists, filters, tickets, timelines, links, node views, and Jasper explanations/prioritizations are navigation and sensemaking surfaces, not replacement for Plane editing or implicit authorization to mutate.

## Risks / Trade-offs

- **A projection or Temporal history becomes a shadow database** → Store references and bounded execution context only; prohibit copied PM records in LangGraph or workflow state.
- **Jasper overwrites a human edit** → Require revision-aware writes, conflict detection, previews, approvals, and an auditable correlation ID.
- **Local Compose is mistaken for production readiness** → Separate local-volume acceptance from production externalization, backup, recovery, and capacity tasks.
- **Untrusted access reaches Plane or Temporal internals** → Keep databases, brokers, object storage, Temporal gRPC, and internal UI paths on trusted networks; expose only reviewed ingress paths.
- **A sample secret or mutable tag is reused** → Generate deployment secrets and record immutable image digests; fail review when provenance is incomplete.
- **Readiness is overstated** → Treat process health and dependency readiness as separate evidence and leave exact probes TBD until versions are selected.
- **Topology drifts from upstream** → Pin and review the official Compose source for the selected Plane release rather than copying an unversioned example.

## Migration Plan

No migration or runtime change is authorized. A future implementation must first confirm Plane and Temporal versions, supported API and workflow boundaries, identity/authorization and revision contracts, persistence and backup strategy, network exposure, and health/readiness probes. It should then validate read-only links and projections before enabling attributed writes. Rollback must disable new integration workflows and writes, stop or drain future work according to the selected Temporal policy, preserve authoritative Plane records and audit evidence, and never delete PM data or checkpoint references as an automatic rollback side effect.

## Open Questions / Decision Tasks

- Choose exact Plane and Temporal release versions, images, digests, upgrade windows, and license review owners; do not infer them from the research URLs.
- Confirm the minimum Plane Compose service set and supported external-database/object-storage configuration for the chosen release.
- Choose Temporal persistence database, optional visibility/search design, initialization/migration process, namespace/task-queue model, retention, and worker deployment model.
- Define health versus readiness probes and acceptance evidence for Plane services, dependencies, Temporal frontend, UI, and workers without assuming undocumented endpoints.
- Define the Agent Server adapter protocol, bounded payloads, idempotency, polling/event behavior, timeout/retry policy, and failure reporting.
- Define secret delivery, rotation, backup/restore, TLS/ingress, network policy, and least-privilege identities for local and production environments.
- Define Plane-to-OpenSpec and Plane-to-agent-run reference schema and conflict-resolution UX.

## References

- Plane self-hosting overview: https://developers.plane.so/self-hosting/overview
- Plane Docker Compose method: https://developers.plane.so/self-hosting/methods/docker-compose
- Plane official Compose source: https://github.com/makeplane/plane/blob/preview/docker-compose.yml
- Temporal self-hosted deployment guide: https://docs.temporal.io/self-hosted-guide/deployment
- Temporal official Compose repository: https://github.com/temporalio/docker-compose
- Temporal Server image: https://hub.docker.com/r/temporalio/server
- Temporal UI image: https://hub.docker.com/r/temporalio/ui

These sources are research inputs. They do not, by themselves, establish exact versions, complete readiness contracts, licensing decisions, or production guarantees.