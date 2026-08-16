# Local Plane + Temporal topology (prepared, not started)

This directory is a sandbox deployment plan. It was **not started**: the Linux agent container has no `docker`, `podman`, or `nerdctl` executable. No macOS/host operation was attempted, and no host software was installed or changed.

## Contents

- `compose.yaml`: localhost-only Plane, Temporal, and placeholder UI topology.
- `frontend/`: health-serving placeholder only; it does not call Plane, Temporal, or LangGraph.
- `.env.example`: variable names and non-secret placeholders only. Never commit a real `.env`.
- `source-revisions.md`: exact selected tags and official source links; digests remain unresolved until a runtime is available.
- `contracts/langgraph-integration-contract.md`: future authenticated integration boundary.

## Preconditions before activation

1. Install/enable an approved container runtime outside this sandbox and confirm Docker Compose support.
2. Reconcile the Plane services, migrations, workers, and environment variables with the exact official Plane release compose file. The compact Plane service set here is intentionally not claimed as production-complete.
3. Resolve and record image digests in `source-revisions.md`; inspect any downloaded compose/source before use.
4. Check disk, memory, and that ports 8080, 7233, 8088, and 8090 are free.
5. Create a local `.env` from `.env.example` with unique random local database passwords. Do not add credentials to Git.

## Commands (after preconditions)

```sh
cp .env.example .env
# edit .env locally; do not paste values into source files

docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 plane-api temporal temporal-ui placeholder-ui

# local endpoints only:
# Plane UI:       http://127.0.0.1:8080
# Temporal UI:    http://127.0.0.1:8088
# Placeholder UI: http://127.0.0.1:8090/healthz
```

The first activation should verify health checks and HTTP reachability without logging in or creating records. No public bind addresses are permitted by this file.

## Stop, backup, teardown

```sh
docker compose stop
docker compose start
# logical backups (run only after the services are active and local credentials exist)
docker compose exec -T plane-db pg_dump -U "$PLANE_DB_USER" "$PLANE_DB_NAME" > plane-db.sql
docker compose exec -T temporal-db pg_dump -U "$TEMPORAL_DB_USER" "$TEMPORAL_DB_NAME" > temporal-db.sql
# remove containers/network, retain named volumes
docker compose down
# destructive teardown: remove only this stack's volumes after confirming backups
docker compose down -v
rm -f .env plane-db.sql temporal-db.sql
```

`docker compose down -v` is destructive. Backups may contain sensitive project data; keep them local and protected.

## Safety boundary

This is non-production local topology only. It does not mount the LangGraph repository, does not implement an agent dispatcher or Temporal worker, does not create Plane/Temporal records, and does not implement OpenSpec-to-Plane synchronization. See the contract document before any future integration work.
