## 1. Authority and integration contract (future implementation planning)

- [ ] 1.1 Confirm self-hosted Plane as the PM authority and document the selected release, supported API boundary, native UI access, record taxonomy, and stable record-link format.
- [ ] 1.2 Define Jasper's named least-privileged integration identity, person-to-integration attribution, authorization scopes, approval classes, audit events, previews, idempotency, and revision/conflict handling.
- [ ] 1.3 Define self-hosted Temporal's namespace, task queues, workflow/activity boundaries, retry and timeout policy, retention, worker model, bounded payloads, and the Plane-reference-only state rule.
- [ ] 1.4 Define the LangGraph Agent Server adapter boundary, including read/propose/apply operations, correlation identifiers, status reporting, failure semantics, and prohibition on direct Plane database or Temporal-internal access.

## 2. Dependencies, persistence, and security (first local phase completed; production externalization deferred)

- [x] 2.1 Compare the chosen Plane release's official Compose topology with the minimum local topology; this phase records API/web plus PostgreSQL, Redis, RabbitMQ, and MinIO dependencies, while reverse proxy and additional Plane workers remain deferred pending release-specific review.
- [x] 2.2 Select PostgreSQL for Temporal local persistence; optional Elasticsearch visibility, production migration, and the `temporalio/auto-setup` production role remain deferred. Local initialization is performed by the pinned auto-setup image only.
- [x] 2.3 Define local Compose named volumes and restart/recovery checks for Plane database/object storage and Temporal backing-database state; acceptance evidence is recorded by the deployment verification artifacts.
- [ ] 2.4 Define production externalization for PostgreSQL, Redis, RabbitMQ, object storage, backups, restore, upgrades, ingress/TLS, and disaster recovery; explicitly distinguish it from local Compose acceptance.
- [x] 2.5 Define trusted network policy for databases, broker, object storage, Temporal frontend gRPC (commonly 7233), UI/admin paths, and reviewed public ingress; Compose uses internal networks and localhost-only reviewed UI/diagnostic bindings.
- [x] 2.6 Define environment/configuration schema and per-deployment secret delivery; `.env` is ignored and required at startup, samples are non-secret placeholders, and secrets are excluded from manifests and logs. Rotation remains a production follow-up.

## 3. Readiness, provenance, and verification (first local phase completed; integration verification deferred)

- [x] 3.1 For the selected local versions, define separate Compose process-health and dependency-readiness probes for Plane services, dependencies, Temporal frontend, and UI; the documented Plane probe is limited to the selected image's `/api/health/` route, and Temporal gRPC is not treated as dependency readiness.
- [x] 3.2 Define image/version/digest tracking for every Plane, Temporal, and dependency image, including repository, exact selected tag/version, immutable digest receipt, source URL, retrieval date, compatibility evidence, and upgrade notes; acceptance remains blocked if the runtime receipt lacks a digest.
- [ ] 3.3 Validate read-only Plane links/projections, Temporal status reporting, bounded references, attribution, authorization, restart persistence, and failure behavior before enabling mutations.
- [ ] 3.4 Define rollback and verification steps that disable or safely drain new integration writes/workflows, preserve Plane records/audit evidence/checkpoint references/Temporal history, and confirm no stale or duplicate mutation succeeded.
- [ ] 3.5 Define stable Plane links from OpenSpec changes and agent runs, with bounded checkpoint references and rebuild behavior; do not duplicate PM records in LangGraph or Temporal.

## 4. Implementation phase boundary

- [x] 4.1 Implement and validate the local Docker Compose deployment foundation for separate Plane and Temporal services, documented dependencies, named persistence, trusted internal networks, configuration/secret boundaries, image tracking, and health/readiness evidence. Keep the LangGraph Agent Server disconnected.
- [ ] 4.2 In a later explicitly authorized phase, implement the authenticated Plane/Temporal integration boundary, dashboard projections, production externalization, and data migration. Do not treat local Compose acceptance as production readiness.

## References

- Plane self-hosting overview: https://developers.plane.so/self-hosting/overview
- Plane Docker Compose method: https://developers.plane.so/self-hosting/methods/docker-compose
- Plane official Compose source: https://github.com/makeplane/plane/blob/preview/docker-compose.yml
- Temporal self-hosted deployment guide: https://docs.temporal.io/self-hosted-guide/deployment
- Temporal official Compose repository: https://github.com/temporalio/docker-compose
- Temporal Server image: https://hub.docker.com/r/temporalio/server
- Temporal UI image: https://hub.docker.com/r/temporalio/ui
