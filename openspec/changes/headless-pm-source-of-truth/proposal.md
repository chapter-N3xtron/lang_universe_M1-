## Why

Jasper needs a durable, human-editable project-management record without turning LangGraph checkpoints or the chat UI into a second PM database. This change now selects self-hosted Plane as the headless project-management source of truth and Temporal as the durable workflow/orchestration component around integration work. Both remain separately operated services; neither changes the authority boundary of the LangGraph Agent Server.

## What Changes

- Select self-hosted Plane for authoritative PM records and its native browser UI for complete human editing.
- Select self-hosted Temporal for durable, retryable, observable orchestration of future Plane synchronization and integration workflows; Temporal workflow state is not a copy of Plane records.
- Define and implement the first local Compose deployment phase: separate Plane and Temporal services, documented dependencies, durable volumes, trusted internal networks, configuration and secret boundaries, health/readiness checks, image/version/digest tracking, rollback, and verification evidence.
- Define a clearly identified integration identity for Jasper, with attribution, auditability, previews, approval gates where appropriate, and conflict-aware edits.
- Define TanStack/Jasper projections for lists, filters, lightweight tickets, links, timelines, node visualizations, and conversational explanation/prioritization.
- Link OpenSpec changes and agent runs to PM records through bounded references without duplicating the PM database in LangGraph checkpoints or Temporal workflow state.
- Distinguish local Docker Compose evaluation from production deployments with externalized managed dependencies.
- Defer vendor-specific integration code, production migration, endpoint contracts beyond selected local probes, and licensing or production guarantees that authoritative sources do not establish. The first phase records selected local image tags and deployment files without claiming production readiness.

## Capabilities

### New Capabilities

- `headless-pm-source-of-truth`: Future contract for self-hosted Plane authority, Temporal orchestration, human-native editing, attributed Jasper integration, safe projections, and cross-links to OpenSpec and agent runs.

### Modified Capabilities

- None. `visualization-board-alignment` covers visual artifact presentation/editing, while `durable-interaction-records` covers durable interaction records and rebuildable projections; neither owns a PM system, Plane, Temporal, or their integration boundary.

## Impact

Future work may affect Plane API integration, Temporal workflows and workers, identity and authorization, audit/revision records, TanStack projection views, OpenSpec/agent-run linking, and deep-link navigation. Plane commonly requires application services plus PostgreSQL, Redis, RabbitMQ, object storage, and a reverse proxy; Temporal requires a supported persistence database and may use Elasticsearch for visibility. These are planning inputs, not an approved topology or production guarantee. This first implementation phase authorizes only the local Docker Compose deployment foundation: separate Plane and Temporal services with their documented dependencies, durable local volumes, trusted internal networks, configuration and secret boundaries, pinned image tracking, and health/readiness verification. It does not wire the LangGraph Agent Server, create integrations, alter checkpoints, or implement a dashboard. Production migration and mutation workflows remain deferred.