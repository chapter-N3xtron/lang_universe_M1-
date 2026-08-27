## Purpose

Defines a conservative, evidence-based contract for retiring only explicitly authorized, unreachable superseded Coder and Custodian paths while preserving operational and historical material and maintaining a tested rollback route.

## ADDED Requirements

### Requirement: Retirement candidates are precisely inventoried

The retirement process SHALL identify every candidate by exact repository-relative path and candidate class, and SHALL record whether the proposed action is deletion or relocation. A directory, filename pattern, age, legacy label, dormancy, or apparent duplication MUST NOT by itself establish that a candidate is obsolete, unreachable, or authorized for retirement.

#### Scenario: Candidate is proposed through a broad pattern
- **WHEN** a proposed retirement identifies files only by directory, glob, naming convention, age, dormancy, or legacy label
- **THEN** the process rejects the proposal until every candidate has been individually inventoried by exact path

#### Scenario: Dormant code is inventoried
- **WHEN** an inventoried path appears dormant but lacks complete replacement and unreachability evidence
- **THEN** the process records the evidence gap and preserves the path without characterizing dormancy as an active danger

### Requirement: Candidate scope is limited to superseded Coder and Custodian paths

The process SHALL consider only legacy Magic Coder runtime, route, and UI aliases; orphaned standalone Coder persistence; custom Custodian worker, client, orchestrator, and primary Compose wiring; and former executor, broker, approval-card, or signed-receipt remnants. A candidate in one of these classes MUST still satisfy every evidence, authorization, and rollback requirement before retirement.

#### Scenario: Candidate is outside the permitted classes
- **WHEN** an inventoried path does not belong to one of the permitted candidate classes
- **THEN** the process excludes it from this change and performs no deletion or relocation

#### Scenario: Permitted-class candidate lacks evidence
- **WHEN** a path belongs to a permitted candidate class but any retirement gate is unsatisfied
- **THEN** the process preserves that path and records the unsatisfied gate

### Requirement: Replacement deployment and parity are prerequisites

Before each candidate removal, the process SHALL identify the intended replacement and SHALL verify that all replacement phases relevant to that candidate are deployed and have passed their defined acceptance checks. Legacy Magic Coder candidates MUST be proven replaced by the deployed Coder path. Custodian worker, client, orchestrator, or primary Compose candidates MUST additionally have documented MCP functional and operational parity. If no replacement is required because a remnant has no supported function, the process SHALL document that conclusion with evidence rather than assume it.

#### Scenario: Replacement exists only in source or planning
- **WHEN** a candidate's replacement is planned or implemented but is not verified in the deployed target environment
- **THEN** the candidate remains preserved and is not authorized for removal

#### Scenario: Custodian MCP parity is incomplete
- **WHEN** a custom Custodian candidate lacks evidence that the host MCP replacement provides the required functions and deployed operational behavior
- **THEN** the Custodian candidate and its Compose wiring remain preserved

#### Scenario: Remnant has no replacement
- **WHEN** a former executor, broker, approval-card, or signed-receipt candidate is asserted to have no remaining supported function
- **THEN** the process requires reference and deployment evidence proving that assertion before the candidate can advance

### Requirement: Reference and deployed-use checks precede every removal

Immediately before each removal, the process SHALL run and record static reference checks and deployment-use checks appropriate to the exact candidate. Checks MUST cover imports and exports, route and UI registration, configuration and environment references, persistence readers and writers, startup and operational scripts, build/package inputs, the primary Compose model, and deployed runtime entry points as applicable. A match, ambiguous result, inaccessible deployment surface, or stale evidence SHALL block removal until resolved.

#### Scenario: Static reference remains
- **WHEN** a current reference check finds a live or ambiguous reference to a candidate
- **THEN** removal is blocked and the candidate is preserved pending explicit resolution

#### Scenario: Deployment configuration cannot be checked
- **WHEN** the deployed target or a relevant runtime configuration cannot be inspected sufficiently to prove the candidate unused
- **THEN** the lack of evidence is recorded and removal does not proceed

#### Scenario: Evidence has become stale
- **WHEN** repository or deployment configuration changes after a candidate's reference evidence was collected and before removal
- **THEN** the process invalidates the affected evidence and repeats the checks before seeking or using authorization

### Requirement: Unreachability is demonstrated per candidate

The process SHALL produce candidate-specific evidence that no supported route, UI action, runtime registration, persistence flow, worker invocation, client call, orchestration path, deployment service, or approved operational procedure can reach or depend on the candidate. Shared files or files containing both current and superseded behavior MUST NOT be wholly removed under evidence that applies only to the superseded portion.

#### Scenario: Candidate is reachable through an operational procedure
- **WHEN** a supported startup, recovery, maintenance, or deployment procedure can invoke or depend on a candidate
- **THEN** the candidate is classified as reachable and is preserved

#### Scenario: Current and superseded behavior share a file
- **WHEN** an exact file includes both still-reachable behavior and a superseded path
- **THEN** the file is not authorized for whole-file deletion, and any later code edit requires separately scoped planning and authorization

### Requirement: Protected material is never inferred disposable

The process MUST preserve operational scripts, captures, conversation records, tool outputs, logs, all files under any `tmp` directory, data volumes, `local-deployment-sandbox`, and alternate Compose files. Membership in, similarity to, or references from a retirement candidate MUST NOT imply authorization to delete or relocate protected material. Any deletion or relocation of protected material requires explicit human authorization naming each exact file and exact action, separate from authorization for a source-path candidate or directory.

#### Scenario: Protected file appears unused
- **WHEN** a protected file has no discovered references or appears old, duplicated, generated, or dormant
- **THEN** the process preserves it and does not infer that it is disposable

#### Scenario: Authorization names only a directory or category
- **WHEN** proposed authorization for protected material names a directory, wildcard, volume, category, or collection rather than every exact file and action
- **THEN** no protected file is deleted or relocated

#### Scenario: Exact protected file receives separate authorization
- **WHEN** a human explicitly authorizes deletion or relocation of one named protected file with the exact action
- **THEN** that authorization applies only to that file and action and grants no authority over sibling files or related records

### Requirement: Human authorization is candidate-specific

After all evidence gates pass and before each removal, the process SHALL present the exact path, action, candidate class, replacement and deployment evidence, reference/deployment check results, unreachability rationale, expected impact, and rollback plan for explicit human authorization. Authorization MUST NOT be inferred from approval of this proposal, approval of a phase, approval of an inventory, or authorization for another candidate.

#### Scenario: Evidence is complete but no candidate authorization exists
- **WHEN** all technical gates pass for a candidate but a human has not authorized its exact path and action
- **THEN** the process preserves the candidate and reports it as awaiting authorization

#### Scenario: One candidate in a cohort is authorized
- **WHEN** a human authorizes one exact candidate from a proposed cohort
- **THEN** only that candidate may proceed and all other cohort members remain preserved

### Requirement: Every removal has a verified rollback plan

Before authorization and removal of each candidate, the process SHALL document a candidate-specific rollback trigger, restoration source, restoration procedure, deployment procedure if applicable, and verification checks. The restoration source MUST be confirmed available and the rollback procedure MUST be feasible without relying on material scheduled for the same removal.

#### Scenario: Restoration source is unavailable
- **WHEN** the candidate cannot be restored from a confirmed source or the restoration procedure cannot be verified as feasible
- **THEN** removal is blocked and the candidate remains preserved

#### Scenario: Post-removal verification fails
- **WHEN** focused checks detect a regression, missing supported behavior, deployment failure, or unexpected reference after removal
- **THEN** the process stops further removals, executes the candidate's rollback plan, and verifies restoration before any reassessment

### Requirement: Retirement execution is incremental and auditable

Authorized candidates SHALL be removed one at a time or in a human-authorized atomic set, with the evidence record retained and focused build, route, UI, persistence, MCP, primary Compose, and deployed smoke checks run as applicable after each removal. A failed or inconclusive check MUST halt subsequent removals. The resulting record SHALL distinguish candidates removed, candidates preserved, blocked candidates, and candidates not found.

#### Scenario: Candidate named in the plan is not present
- **WHEN** later inventory finds that a named candidate class or remnant is absent
- **THEN** the process records it as not found and performs no substitute or neighboring removal

#### Scenario: Focused verification is inconclusive
- **WHEN** post-removal verification cannot establish that supported behavior and deployment remain intact
- **THEN** the process treats verification as failed, halts the sequence, and follows the rollback plan
