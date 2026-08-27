# Phase_9_Obsolete_path_removal

## Why

After replacement phases are deployed and verified, precisely identified superseded Coder and Custodian paths may be retired to reduce duplicate implementation surfaces. Retirement must be evidence-led and reversible: dormant code is not itself an active danger, and no path is removable merely because its name or location appears old.

## What Changes

- Introduce a gated retirement process that inventories each candidate at file-level granularity and records its replacement, reference checks, deployed-use checks, unreachability evidence, rollback method, and human authorization before removal.
- Permit consideration of only these candidate classes: legacy Magic Coder runtime, routes, and UI aliases if proven replaced; orphaned standalone Coder persistence; custom Custodian worker, client, orchestrator, and primary Compose wiring after MCP parity; and former executor, broker, approval-card, or signed-receipt remnants if present and proven unreachable.
- Require replacement deployment and verification, including MCP parity where applicable, before any candidate can be authorized for retirement.
- Require static reference checks and deployment/runtime configuration checks before every removal, with ambiguity or evidence gaps resulting in preservation rather than removal.
- Require a candidate-specific rollback plan and restoration verification before every removal.
- **BREAKING**: An individually authorized retirement may remove a legacy route, UI alias, runtime entry point, persistence path, worker/client/orchestrator path, or primary Compose service only after all gates pass; consumers of that proven-unreachable path would no longer be supported.
- Explicitly exclude operational scripts, captures, conversation records, tool outputs, logs, files under `tmp`, data volumes, `local-deployment-sandbox`, and alternate Compose files from inferred disposal. Deletion or relocation of any such file requires separate, explicit, file-by-file human authorization.
- Keep this change planning-only: it does not delete, relocate, or edit source/runtime files, operational records, `todos.json`, or other OpenSpec changes.

## Capabilities

### New Capabilities

- `obsolete-path-retirement`: Evidence, authorization, preservation, execution, verification, and rollback requirements for retiring precisely inventoried superseded Coder and Custodian paths.

### Modified Capabilities

- None.

## Impact

Planning artifacts are limited to `openspec/changes/phase-9-obsolete-path-removal/`. A later, separately authorized apply may affect only inventoried Coder/Custodian runtime, route, UI alias, persistence, Custodian/MCP transition, primary Compose, executor/broker, approval-card, or signed-receipt files that satisfy the capability gates. APIs or deployments are impacted only where an explicitly authorized, proven-unreachable legacy entry point is retired. Protected operational material and non-primary deployment variants remain preserved unless each exact file receives separate human authorization.
