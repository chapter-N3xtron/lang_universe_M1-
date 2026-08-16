# LangGraph integration boundary (read-only contract)

Status: design-only. No dispatcher, Temporal workflow, agent execution, or Plane sync is implemented.

## Future topology

1. A human creates/approves a Plane project-management event.
2. One authenticated dispatcher/gateway validates the event, authorization, approval state, and idempotency key.
3. The dispatcher starts or signals a Temporal workflow/schedule. Temporal owns retries, concurrency limits, durable state, and audit correlation IDs.
4. The workflow calls the LangGraph Agent Server through its documented API.
5. LangGraph receives read-only repository access. It may inspect OpenSpec/Git references but may not mutate this repository, create credentials, or contact production.

## Contract shape

- Input: `event_id`, `plane_project_id`, `issue_id`, `approved_by`, `requested_action`, `openspec_ref`, `git_ref`, `correlation_id`.
- Required checks: authenticated caller, human approval, allowed repository/ref, explicit action allow-list, idempotency on `event_id` + `requested_action`, and bounded payload size.
- Output: accepted/rejected status plus `correlation_id`; workflow results are written only by an explicitly approved future adapter.
- Concurrency: one workflow per idempotency key; Temporal task queues and workflow IDs must prevent duplicate execution.
- Failure: retry only transient errors; route authorization, validation, and policy failures to a durable review state.
- Repository boundary: mount or fetch the repository read-only at a pinned Git ref; never mount the working tree read-write.
- OpenSpec/Git: references are inputs for review and traceability, not an automatic Plane synchronization command.

## Non-goals for this run

No agent execution, Plane webhook, Temporal worker, credentials, external record creation, production endpoint, or automatic OpenSpec-to-Plane synchronization is configured.
