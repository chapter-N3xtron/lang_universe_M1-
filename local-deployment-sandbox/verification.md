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
2. `docker compose -f local-deployment-sandbox/compose.yaml up -d --build --wait`
3. `docker compose -f local-deployment-sandbox/compose.yaml ps`
4. Verify the health checks and the localhost-only Plane, Temporal UI, and placeholder health endpoints.
5. Record every resolved image digest in the host receipt and retain named volumes across a stop/start check.

## Current run

OpenSpec strict validation passed. The requested Docker action was attempted once through the available typed Compose boundary, but the boundary invoked the Docker command without the Compose subcommand and returned exit code 125 (`unknown shorthand flag: 'd'`). Therefore no containers were created or started, no runtime digests or service health evidence exists, and this record must not be treated as deployment acceptance. The exact blocker is the unavailable/incompatible requested `docker_sandbox` / `request_macos_host_operation` execution interface in this run.
