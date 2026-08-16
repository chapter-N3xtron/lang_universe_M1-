# Image/source manifest

Prepared on 2026-08-15. These are version tags, not verified digests. Runtime was unavailable, so images were not pulled and tags were not resolved. Before activation, verify the selected versions against the official release compose files and record SHA-256 digests here.

| Component | Image/tag | Official source |
|---|---|---|
| Plane API | `makeplane/plane-backend:v1.26.0` | https://github.com/makeplane/plane |
| Plane web | `makeplane/plane-frontend:v1.26.0` | https://github.com/makeplane/plane |
| Plane database | `postgres:15.7-alpine` | https://hub.docker.com/_/postgres |
| Plane Redis | `redis:7.2.5-alpine` | https://hub.docker.com/_/redis |
| Temporal server | `temporalio/auto-setup:1.27.2` | https://github.com/temporalio/temporal |
| Temporal UI | `temporalio/ui:2.34.0` | https://github.com/temporalio/ui |
| Temporal database | `postgres:16.4-alpine` | https://hub.docker.com/_/postgres |
| Placeholder UI base | `nginx:1.27.1-alpine` | https://hub.docker.com/_/nginx |

Important: Plane's official self-hosted release topology and environment contract can change. Do not start this prepared compose until it has been reconciled with the exact Plane release documentation and its migration/worker services.
