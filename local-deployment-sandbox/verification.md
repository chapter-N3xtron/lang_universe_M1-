# First-phase deployment verification

This record is safe to commit and contains no credentials.

- Change: `openspec/changes/headless-pm-source-of-truth`
- Scope: local Compose foundation only; LangGraph Agent Server integration is disconnected.
- Compose file: `local-deployment-sandbox/compose.yaml`
- Required service domains: Plane (`plane-db`, `plane-redis`, `plane-rabbitmq`, `plane-minio`, `plane-api`, `plane-web`) and Temporal (`temporal-db`, `temporal`, `temporal-ui`).
- Persistence: five named volumes are declared for database, queue/cache, broker, object storage, and Temporal database state.
- Network boundary: `plane`, `temporal`, and `frontend` are internal networks. Published ports bind to `127.0.0.1` only.
- Secret boundary: deployment-specific `.env` values are required for database and object-storage passwords; `.env` is ignored and no secret value is recorded here.
- Image provenance: selected tags, official sources, retrieval date, and rollback notes are in `source-revisions.md`; immutable digests must come from the runtime receipt before release acceptance.

## Required runtime evidence

Run through the approved Docker sandbox route from the repository root:

1. `docker compose -f local-deployment-sandbox/compose.yaml config`
2. `docker compose -f local-deployment-sandbox/compose.yaml up --detach --build --wait`
3. `docker compose -f local-deployment-sandbox/compose.yaml ps`
4. Verify the health checks and the localhost-only Plane, Temporal UI, and placeholder health endpoints.
5. Record every resolved image digest in the host receipt and retain named volumes across a stop/start check.

## Current run

The image investigation confirmed the public Community Edition Plane images `makeplane/plane-backend:stable` and `makeplane/plane-frontend:stable`; the Temporal images remain the separate official `temporalio/auto-setup:1.27.2` and `temporalio/ui:2.34.0` references. These are recorded in `compose.yaml`, `deployment-manifest.yaml`, and `source-revisions.md` with their authoritative source links.

The brokered Compose deployment action ran the exact command order `docker compose -f local-deployment-sandbox/compose.yaml up --detach`. Existing database, Redis, RabbitMQ, MinIO, Plane API, and Temporal containers were found; Compose then failed while building the placeholder UI because Docker Buildx could not create `/Applications/Docker.app/Contents/Resources/buildx` (`operation not permitted`). The Plane API remains unhealthy while waiting for migrations, Temporal remains unhealthy under its configured health check, and the dependent web and Temporal UI containers remain unstarted. Local endpoint checks for ports 8080, 8088, and 8090 therefore failed to connect. Named volume declarations remain present, but no new persistence acceptance evidence was established. This record is not deployment acceptance, and no credentials or runtime secrets were printed or recorded.
