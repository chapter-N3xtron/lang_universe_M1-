## Why

Jasper needs a durable, human-editable project-management record without turning LangGraph checkpoints or the chat UI into a second PM database. A self-hosted PM engine can remain the headless source of truth while Jasper and TanStack provide safe projections, explanations, and links into the human's existing work.

## What Changes

- Preserve a future architecture in which a self-hosted PM engine is Jasper's headless source of truth and its native browser UI remains available for complete human editing.
- Define a clearly identified integration identity for Jasper, with attribution, auditability, previews, approval gates where appropriate, and conflict-aware edits.
- Define TanStack/Jasper projections for lists, filters, lightweight tickets, links, timelines, node visualizations, and conversational explanation/prioritization.
- Link OpenSpec changes and agent runs to PM records without duplicating the PM database in LangGraph checkpoints.
- Explicitly defer vendor selection, PM-engine construction, integrations, dashboard implementation, and production migration.

## Capabilities

### New Capabilities

- `headless-pm-source-of-truth`: Future contract for a self-hosted PM authority, human-native UI, attributed Jasper integration, safe projections, and cross-links to OpenSpec and agent runs.

### Modified Capabilities

- None. `visualization-board-alignment` covers visual artifact presentation/editing, while `durable-interaction-records` covers durable interaction records and rebuildable projections; neither owns a PM system or its integration boundary.

## Impact

Future work may affect PM integration APIs, identity and authorization, audit/revision records, TanStack projection views, OpenSpec/agent-run linking, and deep-link navigation. This proposal changes planning artifacts only and does not select a vendor, add a PM engine, create integrations, alter checkpoints, or implement a dashboard.
