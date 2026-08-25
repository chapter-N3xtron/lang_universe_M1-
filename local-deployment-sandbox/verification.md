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

OpenSpec 1.7.0 strict validation passed. The typed Compose deployment action produced the exact command order `docker compose -f local-deployment-sandbox/compose.yaml up --detach`, but Compose stopped before container creation because the required local `.env` values were absent: `PLANE_DB_PASSWORD`, `PLANE_OBJECT_STORAGE_PASSWORD`, and `TEMPORAL_DB_PASSWORD`. No containers, runtime digests, health evidence, endpoint evidence, or persistence evidence exists; this record is not deployment acceptance. The credentials were not printed or recorded. A local `.env` with unique values must be supplied before retrying the one deployment action; it is ignored by Git and is not part of the committed deployment artifacts.
