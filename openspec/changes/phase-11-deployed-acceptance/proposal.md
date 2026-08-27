# Phase_11_Deployed_acceptance

## Why

The completed Coder architecture needs final acceptance at the actual deployment boundary, not another source-only or mocked verification pass. This change defines reproducible, typed evidence that the deployed system remains truthful, durable, idempotent, cancellable, and credential-isolated through real user and service disruptions.

## What Changes

- Add a deployed acceptance contract for the frontend served from this worktree on port 3002, Agent Server, PostgreSQL, Redis signaling, the Temporal outer bridge when enabled, and the native macOS MCP host service.
- Require a deterministic Coder task that performs and verifies real repository work over multiple conversation turns while crossing browser disconnect/rejoin, API, worker, and container restarts, and MCP interruption/recovery.
- Require proof across separate process and resource boundaries that stable identifiers and idempotency prevent duplicate runs and mutations, cancellation propagates, and authority reconciliation reports durable truth rather than optimistic UI state.
- Require credential-canary evidence that secrets and provider credentials never enter agent-visible inputs, outputs, prompts, state, events, logs, or repository mutations.
- Require Jasper to be the only human-facing agent and to summarize typed evidence accurately, including failures, unknowns, optional-component status, and source-versus-deployment provenance.
- Make rebuilding, recreating, and restarting the required in-scope containers and services an explicit authorized part of acceptance preparation and execution; unrelated services are not deployed or disturbed.
- Separate source evidence, container/build evidence, and live deployed evidence, and reject substitutions between those classes.
- Exclude real-browser speech testing and any acceptance claim based on port 3001 or a root `start.command` path.

## Capabilities

### New Capabilities
- `deployed-coder-acceptance`: Defines final deployed-boundary acceptance, disruption and recovery scenarios, evidence typing, idempotency, cancellation, authority, credential isolation, and Jasper-facing reporting.

### Modified Capabilities

None.

## Impact

This is an acceptance-planning change. It affects the acceptance harness and operational verification procedures for the port-3002 frontend, Agent Server API and workers, PostgreSQL, Redis, optional Temporal bridge, and native macOS MCP host service. Applying it may add dedicated acceptance fixtures, instrumentation, and reports and will rebuild/recreate/restart only those required services; it does not authorize unrelated deployment, source implementation outside the acceptance need, real-browser speech testing, port-3001 claims, or root `start.command` claims.
