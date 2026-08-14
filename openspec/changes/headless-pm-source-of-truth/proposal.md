## Why

Jasper needs a durable, human-editable project-management record without turning LangGraph checkpoints or the chat UI into a second PM database. The newly authorized direction is a sandboxed, self-hosted evaluation environment in which Plane is the human project-management and prioritization layer, Temporal is the durable scheduling/orchestration layer, and the existing LangGraph/Jasper/Coding/Research/Librarian system remains the execution and specialist boundary. OpenSpec remains authoritative for development intent within each repository; PM and repository integrations must point to that intent rather than replace it.

## What Changes

- Record the proposed sandboxed deployment/evaluation architecture: self-hosted Plane for human PM/prioritization and self-hosted Temporal for durable scheduling/orchestration.
- Define integration with the existing LangGraph runtime and Jasper, Coding, Research, and Librarian roles without moving their authority into Plane or Temporal.
- Preserve a future architecture in which Plane is the human-facing PM authority and native browser UI, while Jasper and bounded projections provide safe explanations, links, and proposals.
- Define a single small trigger/dispatcher boundary between systems rather than a chain of separate adapters.
- Make data ownership, idempotency, approval, concurrency, security, and no-duplicate-source-of-truth constraints explicit.
- Establish a GitHub-versus-GitLab evaluation gate for repository/issue integration. The lighter-weight option is to be selected only after verifying the documented community OpenSpec extension and its fit with Plane; current repository evidence does not establish the final choice.
- Require a staged proof of concept before any production integration or migration.

## Capabilities

### New Capabilities

- `headless-pm-source-of-truth`: Proposed contract for sandboxed self-hosted Plane/Temporal evaluation, a human PM authority, a single trigger/dispatcher boundary, attributed integration with the existing agent system, safe projections, and cross-links to OpenSpec and repository work.

### Modified Capabilities

- None. `visualization-board-alignment` covers visual artifact presentation/editing, while `durable-interaction-records` covers durable interaction records and rebuildable projections; neither owns a PM system or its integration boundary.

## Impact

Future work may affect Plane/Temporal deployment boundaries, PM integration APIs, identity and authorization, audit/revision records, TanStack projection views, OpenSpec/repository/agent-run linking, and deep-link navigation. This proposal changes planning artifacts only. It does not deploy Plane or Temporal, select GitHub or GitLab, add any integration, alter LangGraph checkpoints, or implement a dashboard. Plane, Temporal, repository integration, and agent integration remain proposed until the staged proof of concept and its explicit decision gates pass.

## Authority and decision status

This is a proposed architecture and documentation contract, not a claim that Plane, Temporal, a community OpenSpec extension, or a GitHub/GitLab integration exists in this repository. OpenSpec remains the per-repository authority for development intent; Plane may track and prioritize work but cannot silently supersede an OpenSpec proposal, design, specification, or task state. The repository evidence reviewed for this change does not establish a final GitHub/GitLab choice.
