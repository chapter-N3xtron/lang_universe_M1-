## Context

See `proposal.md` and `specs/headless-pm-source-of-truth/spec.md`. Existing changes separately describe visualization presentation/editing, durable interaction records, session anatomy, and human-centered session review. None establishes a PM authority or integration contract.

## Goals / Non-Goals

**Goals:**

- Establish a future authority boundary between a self-hosted PM engine, Jasper's integration identity, human editing, and TanStack projections.
- Preserve explicit attribution, audit, preview, approval, revision/conflict, and deep-link requirements before implementation begins.
- Keep OpenSpec and agent-run relationships reference-based and rebuildable.

**Non-Goals:**

- Selecting a PM vendor or protocol.
- Building a PM engine, integration adapter, dashboard, ticket database, or synchronization job.
- Moving PM data into LangGraph checkpoints, todos, governance artifacts, or the existing session catalog.

## Decisions

1. **Create a standalone change.** The concern crosses authority, identity, integration safety, projections, and OpenSpec/agent-run linking. It is broader than `visualization-board-alignment` and is not a requirement of `durable-interaction-records`; those changes are referenced as context only.

2. **PM engine owns PM records.** The future adapter reads authoritative records and writes only through an explicit PM API/UI boundary. TanStack/Jasper stores caches or bounded projections, never a shadow PM ledger.

3. **Human UI remains first-class.** Native PM links are part of every useful projection so a person can inspect and edit the complete record outside Jasper's limited projection surface.

4. **Jasper identity is explicit and least-privileged.** The eventual integration must use a named integration identity rather than impersonating the person. Every mutation carries actor, target, revision basis, preview/result, and audit correlation; approval policy and permissions are deferred to implementation design but are normative safety boundaries.

5. **References, not copies, cross system boundaries.** OpenSpec changes, runs, and checkpoints carry stable PM identifiers and links as bounded context. Authoritative details are fetched from the PM engine, keeping checkpoint size and rebuild semantics independent of PM storage.

6. **Projection semantics are intentionally lightweight.** Lists, filters, tickets, timelines, links, node views, and Jasper explanations/prioritizations are navigation and sensemaking surfaces, not a replacement for native PM editing or an implicit authorization to mutate.

## Risks / Trade-offs

- [A projection becomes a shadow database] → Keep stable references and rebuildable caches only; prohibit PM authority in LangGraph checkpoints.
- [Jasper overwrites a human edit] → Require revision-aware writes, conflict detection, previews, and approval gates.
- [Integration identity is mistaken for the human] → Display and audit the named integration identity separately from the requesting person.
- [Visualization work expands into PM implementation] → Keep board artifacts and PM records separate and defer all adapter/engine/dashboard code to a future implementation change.

## Migration Plan

No migration is authorized. A future implementation must first select an engine and API boundary, define identity/authorization and revision contracts, then build read-only projections and link validation before enabling any attributed mutation. Rollback must disable integration writes without deleting authoritative PM records or checkpoint references.

## Open Questions

The exact PM protocol, record taxonomy, identity provider, approval policy, conflict resolution UX, cache retention, webhook/polling strategy, and OpenSpec/agent-run reference schema remain implementation decisions for a later change. They do not alter this authority and non-duplication contract.
