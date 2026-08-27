## Context

See `proposal.md` for motivation and `specs/focused-architecture-verification/spec.md` for the behavior contract. Phases 1–9 span graph registration and execution, auth, persistence, retrieval, reporting, MCP transports, streaming, and removal work. A single undifferentiated test command would obscure which runtime boundary was actually exercised, and the phase-10 plan must remain valid without treating imported source tests as evidence from a container or deployed environment.

The repository already contains unrelated working-tree changes. Phase-10 implementation must inspect and modify only its authorized verification surfaces and must not use those unrelated changes as evidence.

## Goals / Non-Goals

**Goals:**

- Build a claim-to-evidence matrix in which each architecture claim has one narrow positive case, one relevant negative case, an execution layer, deterministic fixtures, and explicit pass evidence.
- Exercise real graph composition for routing, inheritance, interrupt, resume, and stream behavior while substituting nondeterministic model output with controlled responses.
- Exercise real service and PostgreSQL boundaries only for claims that cannot be established in-process.
- Produce evidence that is machine-readable enough to prevent accidental promotion from source or mocked results to deployed claims.

**Non-Goals:**

- Reimplement or repair phase 1–9 behavior under the guise of verification.
- Run final acceptance against a deployed environment, approve release, or modify deployed data.
- Add real-browser STT/TTS scenarios, live-model assertions, exhaustive UI journeys, load testing, or broad backend/frontend regression suites.
- Make test-only shortcuts part of production authorization, tenant, persistence, or MCP behavior.

## Decisions

### 1. Use a claim matrix as the suite boundary

A versioned matrix will map each phase claim to: claim ID, exact invariant, positive and negative fixture, minimum evidence layer, command or probe, prerequisite, expected observation, and artifact path. The focused runner will select only entries in this matrix. Shared setup is acceptable, but a passing aggregate must retain per-claim outcomes.

Alternative considered:

- Run every existing backend and frontend test: rejected because unrelated failures and successes would not prove the architecture boundaries in scope.
- Use a manual checklist only: rejected because repeatability and negative-case coverage would be weak.

### 2. Use four non-promotable evidence classes

Evidence records will use an enum-like layer field: `unit_mocked`, `graph_integration`, `container`, or `deployed`. A record also carries target identity, fixture seed/IDs, command or probe, start and finish time, exit state, relevant configuration fingerprint, and artifact references. Aggregation may report a claim only at the layer actually executed; it cannot infer a higher layer from lower-layer success.

`deployed` is represented in the schema so phase 11 can consume comparable records. Phase 10 does not generate final deployed acceptance and reports deployed coverage as `not-run/out-of-scope` unless an independently supplied probe record is being classified rather than accepted.

Alternative considered:

- Treat tests that import production source as deployed-equivalent: rejected because packaging, service configuration, network, auth middleware, and persistence wiring remain untested.
- Use only free-form markdown logs: rejected because layer promotion and missing provenance are hard to detect.

### 3. Keep fixtures deterministic and adversarial

The suite will use fixed tenant, user, assistant, thread, run, document, memory, report, MCP request, and event identifiers in isolated namespaces. Model decisions and tool outputs will be deterministic fixtures; waits will use observable state transitions with bounded deadlines rather than arbitrary sleeps. Negative fixtures deliberately collide tenant keys and query text, repeat stream cursors, use a wrong thread, omit auth, target an unregistered graph, and supply invalid MCP arguments.

Alternative considered:

- Use live model output and generated IDs everywhere: rejected because failures would be difficult to reproduce and assertions would drift.

### 4. Prove graph behavior through parent invocation and traceable checkpoints

The graph/integration harness will invoke the registered Jasper entry graph and route a fixture request into the compiled Coder child. It will capture graph events or state snapshots sufficient to establish the parent-child path, inherited configurable identities, interrupt location, and same-thread continuation. Direct Coder calls remain useful unit checks but cannot satisfy the genuine-subgraph claim.

Alternative considered:

- Mock the Coder call at Jasper's boundary: rejected because it cannot prove graph composition, inherited runtime context, or nested interrupt behavior.

### 5. Reserve container checks for wiring and authority claims

A minimal container profile will start only the Agent Server, PostgreSQL, and any narrowly required MCP or retrieval dependency. Probes will use public service boundaries. The persistence check creates an interrupt/checkpoint, restarts Agent Server without replacing PostgreSQL, resumes it, and then verifies explicit failure when PostgreSQL is unavailable. Effective configuration and service logs will be captured with secrets redacted.

Alternative considered:

- Infer PostgreSQL authority from configuration text: rejected because an unused setting or hidden fallback could still pass.
- Restart every service in the repository: rejected as broader than the authority claim.

### 6. Normalize contracts before comparing MCP backends and reports

MCP backend parity will compare a normalized contract rather than transport-specific envelopes: advertised tool identity/schema, result payload, stable error class, cancellation/timeout state where supported, authorization decision, side-effect marker, and redaction result. Typed Coder reports will be validated before Jasper summary assertions; summaries will be checked for required material facts and sentinel raw-report content rather than brittle prose equality.

Alternative considered:

- Byte-compare transport responses or Jasper prose: rejected because harmless envelope and wording differences would make the suite fragile.

### 7. Test stream rejoin with event cursors and reconstructed output

A deterministic run will pause after emitting a known event, the client transport will disconnect, and the server-side run will continue. Rejoin will use stable run/thread identity and the last acknowledged cursor. Assertions will compare ordered event IDs and the reconstructed committed output, not socket lifetime or wall-clock timing. A cross-tenant rejoin provides the security case.

Alternative considered:

- Simulate reconnection only in a frontend reducer: rejected because it cannot prove server run continuity or authorization on rejoin.

### 8. Prove removal with a reviewed forbidden-reference manifest

Phase 9's removed identities, routes, stores, adapters, imports, configuration keys, and entrypoints will be listed explicitly. Checks will scan only executable source, active configuration, container definitions, and runtime entrypoints. Historical planning/archive text may be allowlisted by exact path and rationale; broad glob exclusions are not allowed. A self-test fixture will establish that the matcher fails when a forbidden token is present.

Alternative considered:

- Rely on code review or a generic search with undocumented exclusions: rejected because absence claims need reproducible scope and precise exceptions.

### 9. Keep quality checks proportional to changed files

Strict OpenSpec validation is mandatory for this proposal. Later implementation will derive changed phase-10 files, group them by configured checker, and invoke file-scoped lint/type commands where supported or the narrowest containing project target otherwise. Inapplicable checks will be recorded as such, not as passes. None of these checks changes the evidence layer of an architecture claim.

Alternative considered:

- Run every repository checker and suite: rejected because it violates the focused boundary and can couple acceptance to unrelated code.

## Risks / Trade-offs

- [Controlled model responses hide provider-specific behavior] → Keep claims at graph routing and contract boundaries; provider behavior is not a phase-10 invariant.
- [Container probes become flaky] → Use health/state polling, fixed fixtures, bounded deadlines, and isolated resources; avoid sleep-based ordering.
- [A source assertion is mislabeled as runtime evidence] → Require a layer field and target/configuration provenance, and reject evidence promotion during aggregation.
- [PostgreSQL failure testing damages unrelated data] → Use an isolated container profile and disposable database/schema namespace.
- [Tenant negative tests leak fixture content into logs] → Use non-sensitive sentinels, redact captured output, and assert no foreign sentinel appears.
- [Forbidden-reference allowlists conceal regressions] → Require exact paths, rationale, and zero broad exclusions; test the scanner with a known forbidden fixture.
- [Transport differences make MCP parity overstrict] → Compare normalized semantic fields and separately retain transport-specific diagnostics.
- [Phase 10 drifts into phase 11] → Mark deployed execution and final acceptance out of scope and hand the evidence schema and pending deployed claim set to phase 11.

## Migration Plan

1. Review the claim matrix and forbidden-reference manifest against the completed phase 1–9 contracts before adding tests.
2. Add unit/mocked and graph/integration checks, then run only their matrix selections.
3. Add the minimal isolated container profile and authority/rejoin probes; retain logs and machine-readable evidence by claim.
4. Run strict OpenSpec validation and applicable changed-file lint/type checks.
5. Publish the classified phase-10 evidence summary with deployed claims explicitly unexecuted and reserved for phase 11.
6. If the harness causes instability, remove or disable only the phase-10 runner/profile and its disposable fixtures; no production data migration or runtime rollout is part of this change.
