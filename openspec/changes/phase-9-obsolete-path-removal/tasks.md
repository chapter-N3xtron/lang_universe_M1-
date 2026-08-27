# Phase_9_Obsolete_path_removal

## 1. Establish retirement gates and ledger

- [ ] 1.1 Identify the repository revision, target deployment revision, and acceptance evidence for every relevant replacement phase; verify each evidence link names the deployed environment and passed checks, and stop with all candidates preserved if any prerequisite is unavailable or inconclusive.
- [ ] 1.2 Create the exact-path retirement ledger with candidate ID, path, class, action, current role, replacement/parity evidence, static references, deployed-use evidence, unreachability result, protected/shared classification, rollback, human decision, execution, and verification fields; verify a schema review shows no directory, glob, or phase-level entry can authorize child paths.
- [ ] 1.3 Add the fail-closed candidate states and evidence-freshness rules described in `design.md`; verify sample missing, ambiguous, inaccessible, and stale evidence records resolve to `blocked` or `preserved`, never `authorized`.
- [ ] 1.4 Record the protected-material rule for operational scripts, captures, conversation records, tool outputs, logs, every `tmp` file, data volumes, `local-deployment-sandbox`, and alternate Compose files; verify the ledger marks such items preserved and requires separate exact-file/exact-action human authorization without granting authority to siblings or directories.

## 2. Inventory only permitted candidate classes

- [ ] 2.1 Inventory exact legacy Magic Coder runtime, route, and UI-alias paths without changing them; verify every row names an exact repository-relative path and links to deployed replacement-Coder evidence or is marked `blocked`, `preserved`, or `not-found`.
- [ ] 2.2 Inventory exact standalone Coder persistence paths and document their readers, writers, data ownership, and replacement authority without changing data or schemas; verify any path with a live, ambiguous, or unverified persistence dependency is marked `preserved` or `blocked`.
- [ ] 2.3 Inventory exact custom Custodian worker, client, orchestrator, and primary Compose wiring paths without changing Compose files; verify every row links to a completed MCP functional/operational parity matrix and deployed evidence or remains preserved.
- [ ] 2.4 Inventory exact former executor, broker, approval-card, and signed-receipt remnants if present; verify absent paths are recorded `not-found` with no substitute removal and paths lacking positive evidence of no supported role are preserved.
- [ ] 2.5 Review the inventory for outside-scope, shared, and protected files; verify outside-scope files are excluded, whole-file removal of mixed current/superseded code is blocked, and no operational record, script, output, log, `tmp` file, data volume, sandbox file, or alternate Compose file is proposed for inferred disposal.

## 3. Prove replacement and unreachability

- [ ] 3.1 For each remaining candidate, run and record candidate-specific import/export, call-site, route/UI registration, configuration/environment, persistence reader/writer, startup/operational script, build/package, and primary Compose reference checks as applicable; verify every live or ambiguous match blocks that candidate.
- [ ] 3.2 For each remaining candidate, inspect the effective deployed configuration, runtime registrations, service topology, and supported startup, recovery, maintenance, and deployment procedures; verify an inaccessible surface or possible invocation marks the candidate `blocked` or `preserved`.
- [ ] 3.3 Exercise focused replacement behavior for each remaining Magic Coder candidate and record the deployed results; verify supported runtime, route, and UI behavior succeeds only through the replacement Coder path before advancing the candidate.
- [ ] 3.4 Exercise the MCP parity matrix for each remaining Custodian candidate in the deployed target and inspect effective primary Compose behavior; verify all required functional and operational checks pass before advancing any worker, client, orchestrator, or primary Compose candidate.
- [ ] 3.5 Produce a candidate-specific unreachability conclusion from the independent static and deployed evidence; verify each conclusion rules out supported runtime, UI, route, persistence, worker/client, orchestration, deployment, and operational-procedure reachability as applicable, otherwise preserve the candidate.

## 4. Prepare rollback and obtain exact authorization

- [ ] 4.1 For each candidate that passed the evidence gates, document rollback triggers, a confirmed restoration source, exact restoration steps, redeployment steps if applicable, and restoration checks; verify the source exists and the procedure does not depend on any item in the proposed removal.
- [ ] 4.2 Recheck repository and deployment identity immediately before authorization review and rerun any evidence affected by changes; verify stale packets return to a blocked state rather than carrying forward prior approval eligibility.
- [ ] 4.3 Present each complete evidence packet with its exact path and delete-or-relocate action for explicit human decision; verify the ledger records authorization only for the named candidate/action and treats proposal, phase, inventory, directory, wildcard, and other-candidate approvals as non-authorizing.
- [ ] 4.4 Keep denied, pending, incompletely evidenced, shared, and protected candidates unchanged; verify any request concerning protected material is stopped for separate file-by-file human authorization and that no current task grants relocation or deletion authority for it.

## 5. Execute authorized retirements incrementally

- [ ] 5.1 For each explicitly authorized Magic Coder candidate, revalidate evidence freshness, remove only the exact authorized path/action one candidate at a time, and run applicable build, runtime, route, UI-navigation, and deployed smoke checks; verify a failed or inconclusive result stops the sequence and triggers the documented rollback and restoration checks.
- [ ] 5.2 For each explicitly authorized standalone Coder persistence candidate, revalidate evidence freshness, remove only the exact authorized path/action without altering retained data, and run persistence authority, reader/writer, restart, and deployed smoke checks; verify any failure stops work and restores the candidate from its confirmed source.
- [ ] 5.3 For each explicitly authorized Custodian worker, client, orchestrator, or primary Compose candidate, revalidate MCP parity and evidence freshness, remove only the exact authorized path/action, and run the parity suite, effective primary Compose validation, deployment health, and operational smoke checks; verify alternate Compose files and protected operational material remain unchanged and any failure rolls back.
- [ ] 5.4 For each explicitly authorized executor, broker, approval-card, or signed-receipt remnant, revalidate evidence freshness, remove only the exact authorized path/action, and run applicable backend, UI, approval-flow, receipt, and deployed regression checks; verify any unexpected reference or behavior stops work and restores the candidate.

## 6. Reconcile and report

- [ ] 6.1 Review the working-tree and deployment diff against the authorization ledger; verify every deletion or relocation maps one-to-one to an authorized exact candidate/action and that source/runtime edits outside those actions, `todos.json`, other changes, and all protected material are unchanged.
- [ ] 6.2 Run the complete focused regression set covering replacement Coder behavior, routes/UI, persistence, MCP/Custodian parity, effective primary Compose configuration, approval/receipt behavior, deployment health, and supported operational procedures as applicable; verify all results pass or execute rollback for the implicated candidate and record restoration.
- [ ] 6.3 Finalize the audit summary with separate lists for `verified`, `preserved`, `blocked`, `authorization-pending`, `not-found`, and `rolled-back` candidates plus evidence references; verify no dormant path is described as an active danger and no absence is treated as authorization for a neighboring removal.
