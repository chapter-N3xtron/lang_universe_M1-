## 1. Authority and integration contract (future implementation planning)

- [ ] 1.1 Confirm self-hosted Plane as the PM authority and document the selected release, supported API boundary, native UI access, record taxonomy, and stable record-link format.
- [ ] 1.2 Define Jasper's named least-privileged integration identity, person-to-integration attribution, authorization scopes, approval classes, audit events, previews, idempotency, and revision/conflict handling.
- [ ] 1.3 Define self-hosted Temporal's namespace, task queues, workflow/activity boundaries, retry and timeout policy, retention, worker model, bounded payloads, and the Plane-reference-only state rule.
- [ ] 1.4 Define the LangGraph Agent Server adapter boundary, including read/propose/apply operations, correlation identifiers, status reporting, failure semantics, and prohibition on direct Plane database or Temporal-internal access.

## 2. Dependencies, persistence, and security (future implementation planning)

- [ ] 2.1 Compare the chosen Plane release's official Compose topology (application services, PostgreSQL, Redis, RabbitMQ, MinIO/object storage, and reverse proxy) with the minimum local topology; do not assume every commonly listed service is required.
- [ ] 2.2 Select Temporal's supported persistence database and decide whether optional Elasticsearch visibility is needed; document initialization/migration handling without assuming `temporalio/auto-setup` is a production role.
- [ ] 2.3 Define local Compose named volumes and restart/recovery checks for Plane database/object storage and Temporal backing-database state.
- [ ] 2.4 Define production externalization for PostgreSQL, Redis, RabbitMQ, object storage, backups, restore, upgrades, ingress/TLS, and disaster recovery; explicitly distinguish it from local Compose acceptance.
- [ ] 2.5 Define trusted network policy for databases, broker, object storage, Temporal frontend gRPC (commonly 7233), UI/admin paths, and reviewed public ingress.
- [ ] 2.6 Define environment/configuration schema, per-deployment secret generation and rotation, approved secret delivery, log redaction, and a review that sample secrets are not reused.

## 3. Readiness, provenance, and verification (future implementation planning)

- [ ] 3.1 For the selected versions, define separate process-health and dependency-readiness probes for Plane services, dependencies, Temporal frontend, UI, and workers; do not invent undocumented Plane endpoints, and do not equate Temporal gRPC health with dependency readiness.
- [ ] 3.2 Define image/version/digest tracking for every Plane, Temporal, and dependency image, including repository, exact selected tag/version, immutable digest, source URL, retrieval date, compatibility evidence, and upgrade notes.
- [ ] 3.3 Validate read-only Plane links/projections, Temporal status reporting, bounded references, attribution, authorization, restart persistence, and failure behavior before enabling mutations.
- [ ] 3.4 Define rollback and verification steps that disable or safely drain new integration writes/workflows, preserve Plane records/audit evidence/checkpoint references/Temporal history, and confirm no stale or duplicate mutation succeeded.
- [ ] 3.5 Define stable Plane links from OpenSpec changes and agent runs, with bounded checkpoint references and rebuild behavior; do not duplicate PM records in LangGraph or Temporal.

## 4. Scope guard

- [ ] 4.1 Implement and validate deployment files, Plane/Temporal integration, dashboard projections, production migration, and data migration only in a later explicitly authorized change; this planning change installs and starts nothing.

## References

- Plane self-hosting overview: https://developers.plane.so/self-hosting/overview
- Plane Docker Compose method: https://developers.plane.so/self-hosting/methods/docker-compose
- Plane official Compose source: https://github.com/makeplane/plane/blob/preview/docker-compose.yml
- Temporal self-hosted deployment guide: https://docs.temporal.io/self-hosted-guide/deployment
- Temporal official Compose repository: https://github.com/temporalio/docker-compose
- Temporal Server image: https://hub.docker.com/r/temporalio/server
- Temporal UI image: https://hub.docker.com/r/temporalio/ui
