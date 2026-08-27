# Phase_9_Obsolete_path_removal

## Context

See `proposal.md` for motivation and `specs/obsolete-path-retirement/spec.md` for the behavior contract. This is a cross-cutting retirement design spanning possible backend runtime and persistence paths, frontend routes and aliases, Custodian/MCP integration, and deployment configuration. No exact removal candidate is established by this plan; candidate discovery and evidence collection occur only during a later apply, after relevant replacement deployments and acceptance evidence are available.

The repository also contains operational and historical material whose location or lack of code references does not establish disposability. The design therefore treats uncertainty as a preservation result and separates candidate evidence from deletion authorization.

## Goals / Non-Goals

**Goals:**

- Provide one repeatable, reviewable evidence packet for each exact retirement candidate.
- Make replacement deployment, reference/deployment checks, unreachability, human authorization, focused verification, and rollback hard gates rather than informal judgments.
- Support incremental retirement without broad cleanup operations or collateral changes.
- Preserve a clear audit result for removed, preserved, blocked, and not-found candidates.

**Non-Goals:**

- This planning work does not inspect the repository to nominate exact files, prove any path obsolete, or authorize any removal.
- It does not delete, relocate, or modify source/runtime files, deployment files, data, records, operational artifacts, `todos.json`, or other changes.
- It does not redesign replacement Coder, MCP, streaming, persistence, approval, or deployment behavior.
- It does not classify dormant code as an active danger or use code age, names, generated status, or apparent duplication as removal evidence.
- It does not clean operational scripts, captures, conversation records, tool outputs, logs, `tmp`, data volumes, `local-deployment-sandbox`, or alternate Compose files.

## Decisions

### 1. Use a candidate ledger with one evidence packet per exact path

A later apply will first create a reviewable ledger. Each row will contain an immutable candidate ID, exact repository-relative path, candidate class, proposed action, current role, replacement (or evidence that no supported role remains), deployed acceptance evidence, reference/deployment checks, unreachability conclusion, protected-material classification, expected impact, rollback plan, human decision, execution result, and verification result. Directory-level entries may organize review but cannot authorize child paths.

This format keeps evidence and authority aligned with the exact object affected. Shared files are marked blocked for whole-file deletion; removing code within a shared file is a separate source edit requiring its own scoped plan rather than being smuggled into a file-retirement action.

Alternatives considered:

- A directory or glob-based cleanup list: rejected because it can include unreviewed siblings and cannot support file-by-file authorization.
- Immediate deletion followed by test discovery: rejected because tests cannot replace pre-removal reference, deployment, and rollback checks.

### 2. Model retirement as a fail-closed state machine

Each candidate advances through `inventoried`, `replacement-verified`, `references-cleared`, `deployment-cleared`, `unreachable`, `rollback-ready`, `authorized`, `removed`, and `verified`. It may instead end as `preserved`, `blocked`, `authorization-pending`, `not-found`, or `rolled-back`. Missing, ambiguous, inaccessible, or stale evidence transitions to `blocked` or `preserved`, never to the next gate.

Authorization is requested only after the evidence packet and rollback plan are complete. A repository or deployment change affecting the evidence invalidates downstream states and requires checks to be rerun before authorization can be used.

Alternatives considered:

- A confidence score: rejected because high aggregate confidence can hide a missing mandatory gate.
- One phase-level approval: rejected because approval of planning or inventory is not approval of an exact destructive action.

### 3. Build unreachability evidence from independent static and deployed views

Static checks will be candidate-specific and cover relevant imports/exports, call sites, routes, UI registrations and navigation, configuration/environment references, persistence readers/writers, startup and operational scripts, package/build inputs, and primary Compose references. Deployment checks will inspect the effective target configuration, registered runtime paths, service topology, supported operational procedures, and focused behavior probes.

Magic Coder candidates require evidence that the deployed replacement Coder path owns the supported behavior. Custodian worker/client/orchestrator or primary Compose candidates require an MCP parity matrix covering required functions and operational characteristics, linked to deployed acceptance evidence. Former executor/broker/approval-card/signed-receipt remnants require positive evidence of no supported role rather than an assumption that a replacement must exist.

A check transcript may be retained as evidence but does not become disposable because it was generated during retirement work.

Alternatives considered:

- Static search alone: rejected because dynamic registration, configuration, deployments, and operational procedures may not appear as direct code references.
- Runtime smoke tests alone: rejected because unexercised routes and recovery procedures can still be supported dependencies.

### 4. Maintain a non-inference boundary for protected material

The ledger will classify operational scripts, captures, conversation records, tool outputs, logs, every file under a `tmp` directory, data volumes, `local-deployment-sandbox`, and alternate Compose files as protected. These can be inspected as evidence when authorized, but they are excluded from retirement actions under this change. Even if a protected file references a retiring candidate, appears generated, or has no references, it remains preserved.

If a human later wants a protected item deleted or relocated, it must be proposed separately with the exact file and action named; authorization does not cascade to a directory, sibling, volume, or category. Primary Compose wiring can be a candidate only when it is precisely inventoried and all Custodian/MCP gates pass; alternate Compose files remain protected.

Alternatives considered:

- Automatically exclude only version-controlled data: rejected because operational value is independent of version-control status.
- Treat generated output as reproducible and disposable: rejected because captures, logs, and tool outputs can be unique evidence or records.

### 5. Execute authorized removals incrementally with stop-the-line verification

A later apply may remove one candidate at a time, or an explicitly human-authorized atomic set when independently removing members would make verification invalid. Before the action, it rechecks evidence freshness and confirms the restoration source. Afterward, it runs only the applicable focused checks—build/type checks, routes, UI navigation, persistence, MCP behavior, effective primary Compose configuration, deployment health, and supported smoke paths—and records results in the ledger.

Any failed or inconclusive result stops subsequent actions and triggers the candidate rollback. A not-found candidate is recorded without substituting a nearby path. Completion reporting lists preserved and blocked paths as deliberately as removed paths.

Alternatives considered:

- One large removal commit: rejected because it obscures causality and makes rollback less precise.
- Continue after a noncritical failure: rejected because the plan cannot safely infer which failures are unrelated.

## Risks / Trade-offs

- [Dynamic or external references escape discovery] → Require both static and deployed-use evidence, inspect supported operational procedures, and block when a relevant surface is inaccessible.
- [Evidence becomes stale between review and action] → Record repository/deployment identity, invalidate affected gates on change, and rerun checks immediately before removal.
- [Replacement behaves differently under production conditions] → Require deployed acceptance evidence and candidate-specific smoke checks; require an MCP parity matrix for Custodian candidates.
- [A broad authorization is misunderstood] → Use exact path/action prompts and record each human decision; directory, category, inventory, and phase approvals are non-authorizing.
- [Rollback source is coupled to the removal] → Verify the restoration source and procedure before authorization and prohibit reliance on material in the same removal set.
- [Conservative gates leave old paths in place] → Accept preservation as the intended outcome when proof is incomplete; dormant code is not presented as an active danger.
- [Evidence artifacts expose or disturb protected records] → Limit inspection to what is authorized and necessary, retain outputs under existing policies, and never infer that evidence can be deleted afterward.

## Migration Plan

1. Confirm all replacement phases relevant to a candidate are deployed and their acceptance results identify the target environment and deployment revision.
2. Build the exact-path candidate ledger only from the permitted classes; mark protected, shared, outside-scope, and not-found items without changing them.
3. For each candidate, complete replacement/parity evidence, fresh static references, effective deployment-use checks, and a candidate-specific unreachability conclusion.
4. Prepare and verify the restoration source, rollback triggers, restoration/deployment procedure, and restoration checks for that exact candidate.
5. Present the completed packet and exact delete-or-relocate action for explicit human authorization. Preserve candidates that are denied, pending, ambiguous, stale, or incompletely evidenced.
6. Execute one authorized candidate or explicitly authorized atomic set, then run and record focused local and deployed verification before considering the next candidate.
7. If a check fails or is inconclusive, stop, restore from the confirmed source, redeploy if applicable, verify restoration, and record `rolled-back`; do not resume without a new evidence review and authorization.
8. Publish a final ledger summary of removed, verified, preserved, blocked, authorization-pending, not-found, and rolled-back candidates. Do not alter protected material as part of closeout.
