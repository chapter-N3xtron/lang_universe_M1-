# Image/source manifest

Selected for the first local Compose evaluation on 2026-08-23. The repository records the exact tag inputs and official source; the approved Docker host receipt records the immutable SHA-256 digest resolved by the runtime. A deployment is not release-accepted if the receipt cannot prove the digest for every image.

| Component | Image/tag | Immutable digest | Official source | Upgrade/rollback note |
|---|---|---|---|---|
| Plane API | `makeplane/plane-backend:stable` | Host receipt | https://developers.plane.so/self-hosting/methods/docker-compose | Re-pin after release compatibility review; stop and preserve volumes to roll back |
| Plane web | `makeplane/plane-frontend:stable` | Host receipt | https://developers.plane.so/self-hosting/methods/docker-compose | Re-pin with API; do not mix release lines |
| Plane database | `postgres:15.7-alpine` | Host receipt | https://hub.docker.com/_/postgres | Logical backup before upgrade; preserve named volume |
| Plane Redis | `redis:7.2.5-alpine` | Host receipt | https://hub.docker.com/_/redis | Preserve append-only volume; verify restore |
| Plane RabbitMQ | `rabbitmq:3.13.7-management-alpine` | Host receipt | https://hub.docker.com/_/rabbitmq | Drain/stop before upgrade; preserve broker volume |
| Plane object storage | `minio/minio:RELEASE.2024-08-17T01-24-54Z` | Host receipt | https://hub.docker.com/r/minio/minio | Back up object data before upgrade |
| Temporal server | `temporalio/auto-setup:1.27.2` | Host receipt | https://github.com/temporalio/temporal | Local initialization only; do not treat auto-setup as production policy |
| Temporal UI | `temporalio/ui:2.34.0` | Host receipt | https://github.com/temporalio/ui | Keep UI local-only; pin with server compatibility |
| Temporal database | `postgres:16.4-alpine` | Host receipt | https://hub.docker.com/_/postgres | Logical backup before upgrade; preserve named volume |
| Placeholder UI base | `nginx:1.27.1-alpine` | Build receipt | https://hub.docker.com/_/nginx | Unrelated health-only placeholder; remove when reviewed UI exists |

Plane uses the documented Community Edition `stable` channel for both public Plane services because the previously selected `v1.26.0` references are not the current documented image/tag strategy. The authoritative references are the official Docker Compose guide (https://developers.plane.so/self-hosting/methods/docker-compose), backend repository (https://hub.docker.com/r/makeplane/plane-backend), and tag list (https://hub.docker.com/r/makeplane/plane-backend/tags). Temporal remains a separate deployment: `temporalio/auto-setup:1.27.2` is retained for local database initialization, and `temporalio/ui:2.34.0` is the separately pinned official UI image. No Plane-Temporal integration is added.

The local `.env` is generated per deployment and ignored by Git. It contains database and object-storage credentials only; credentials are never copied into Compose, manifests, logs, or reports. Production requires separately reviewed managed persistence, secret delivery, backups, TLS, ingress, and capacity decisions.
