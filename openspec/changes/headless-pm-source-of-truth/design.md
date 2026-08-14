## Context

See `proposal.md` and `specs/headless-pm-source-of-truth/spec.md`. Existing changes separately describe visualization presentation/editing, durable interaction records, session anatomy, and human-centered session review. None establishes a PM authority or integration contract.

## Goals / Non-Goals

**Goals:**

- Establish a future authority boundary between a self-hosted PM engine, Jasper's integration identity, human editing, and TanStack projections.
- Preserve explicit attribution, audit, preview, approval, revision/conflict, and deep-link requirements before implementation begins.
- Keep OpenSpec and agent-run relationships reference-based and rebuildable.

**Non-Goals:**

- Implementing Plane, Temporal, a repository/issue integration, or any LangGraph/Jasper/Coding/Research/Librarian integration.
- Making a final GitHub-versus-GitLab choice before the documented extension and Plane-fit evaluation.
- Building a PM engine, adapter chain, dashboard, ticket database, or synchronization job.
- Moving PM data into LangGraph checkpoints, todos, governance artifacts, or the existing session catalog.

## Decisions

1. **Create a standalone change.** The concern crosses authority, identity, integration safety, projections, and OpenSpec/agent-run linking. It is broader than `visualization-board-alignment` and is not a requirement of `durable-interaction-records`; those changes are referenced as context only.

2. **PM engine owns PM records.** The future adapter reads authoritative records and writes only through an explicit PM API/UI boundary. TanStack/Jasper stores caches or bounded projections, never a shadow PM ledger.

3. **Human UI remains first-class.** Native PM links are part of every useful projection so a person can inspect and edit the complete record outside Jasper's limited projection surface.

4. **Jasper identity is explicit and least-privileged.** The eventual integration must use a named integration identity rather than impersonating the person. Every mutation carries actor, target, revision basis, preview/result, and audit correlation; approval policy and permissions are deferred to implementation design but are normative safety boundaries.

5. **References, not copies, cross system boundaries.** OpenSpec changes, runs, and checkpoints carry stable PM identifiers and links as bounded context. Authoritative details are fetched from the PM engine, keeping checkpoint size and rebuild semantics independent of PM storage.

6. **Projection semantics are intentionally lightweight.** Lists, filters, tickets, timelines, links, node views, and Jasper explanations/prioritizations are navigation and sensemaking surfaces, not a replacement for native PM editing or an implicit authorization to mutate.

7. **Use a sandboxed deployment/evaluation environment first.** Plane and Temporal are proposed as self-hosted services in an isolated environment with synthetic or explicitly approved test data, constrained network and credentials, observable boundaries, and teardown/rollback. No production access or migration is implied.

8. **Separate human PM authority from durable orchestration.** Plane owns human-authored PM records, prioritization, status, and approvals. Temporal owns durable scheduling, retries, timers, workflow state, and orchestration history. LangGraph remains the execution/runtime boundary; Jasper coordinates human-facing work and existing Coding, Research, and Librarian specialists retain their defined roles. None of these systems becomes a second OpenSpec ledger.

9. **Prefer one small trigger/dispatcher boundary.** External events and approved human actions enter one narrow, authenticated dispatcher that validates scope, records an idempotency key and correlation ID, then starts or signals the appropriate Temporal workflow/LangGraph handoff. Separate point-to-point adapter chains are rejected because they multiply retries, ownership ambiguity, and duplicate writes.

10. **Make repository integration a decision gate.** Evaluate GitHub and GitLab against the documented community OpenSpec extension, webhook/API surface, authentication and least-privilege model, event/idempotency behavior, operational weight, and Plane integration fit. Select the lighter-weight option only after evidence is recorded; this repository currently establishes neither a final provider nor that the extension is installed.

11. **Keep OpenSpec authoritative per repository.** Plane references OpenSpec change/artifact/task identities and may mirror status for prioritization, but it cannot originate or silently rewrite development intent. Repository-local OpenSpec artifacts remain authoritative; synchronization is explicit, attributable, revision-aware, and conflict-safe.

12. **Require a staged proof of concept.** Progress from architecture and threat-model review, to isolated read-only Plane/Temporal connectivity, to one idempotent trigger/dispatcher path with synthetic data, to approval/concurrency/failure/replay tests, and only then a separately authorized limited pilot. Production rollout requires a new approved change.

## Data ownership and safety invariants

- Plane owns PM and prioritization data; Temporal owns workflow/scheduling state; LangGraph checkpoints and Store retain their existing execution/session authorities; OpenSpec owns repository development intent; repository/issue systems own repository and issue records; projections and links are rebuildable caches, not authorities.
- Every cross-system request carries a stable correlation ID, deterministic idempotency key, source revision, actor/integration identity, authorization/approval state, and bounded payload. Retries must converge without duplicate PM issues, workflow starts, mutations, or OpenSpec intent.
- Concurrent human edits, stale revisions, duplicate deliveries, out-of-order events, and partial failure are detected and reconciled explicitly; no last-writer-wins overwrite is assumed.
- Credentials stay in the approved secret boundary and are never copied into PM records, checkpoints, OpenSpec artifacts, logs, or telemetry. Services receive least-privilege scoped access, network isolation, audit events, rate/concurrency limits, cancellation, and safe failure behavior.

## Risks / Trade-offs

- [A projection becomes a shadow database] → Keep stable references and rebuildable caches only; prohibit PM authority in LangGraph checkpoints.
- [Jasper overwrites a human edit] → Require revision-aware writes, conflict detection, previews, and approval gates.
- [Integration identity is mistaken for the human] → Display and audit the named integration identity separately from the requesting person.
- [Temporal retries or duplicate triggers create duplicate work] → Use one dispatcher boundary, deterministic idempotency keys, workflow IDs, correlation IDs, and replay/concurrency tests.
- [Sandbox credentials or data escape] → Isolate deployment, use synthetic data and least privilege, prohibit credential persistence/logging, and require teardown evidence.
- [Plane becomes a second development-intent ledger] → Keep OpenSpec authoritative per repository and synchronize by explicit references and revision-aware proposals only.
- [Visualization work expands into PM implementation] → Keep board artifacts and PM records separate and defer all adapter/engine/dashboard code to a future implementation change.

## Migration Plan

No production migration is authorized. A future implementation must first establish the sandbox, threat model, Plane/Temporal ownership and API boundaries, the single dispatcher contract, and identity/authorization, revision, idempotency, concurrency, and security controls. It must then complete read-only connectivity and synthetic-data proof-of-concept stages before any attributed mutation or limited pilot. Rollback must disable dispatch and integration writes without deleting authoritative Plane, Temporal, OpenSpec, repository, or LangGraph records.

## Open Questions

The exact Plane deployment profile, Temporal workflow/task-queue model, PM protocol, record taxonomy, identity provider, approval policy, conflict resolution UX, cache retention, trigger/event strategy, and OpenSpec/agent-run/repository reference schema remain implementation decisions for a later change. The GitHub-versus-GitLab choice is also unresolved pending documented community OpenSpec-extension evidence and Plane integration-fit evaluation; the lighter-weight option should be selected only after that review. None of these open questions alters the authority, idempotency, security, or non-duplication contract.
