## 1. Verification contract and fixtures

- [ ] 1.1 Create the phase 1–9 claim matrix with invariant, positive/negative fixture, minimum evidence layer, prerequisites, narrow command, expected observation, and artifact path for every scoped claim; verify a schema/check reports no missing or duplicate claim IDs.
- [ ] 1.2 Define machine-readable evidence records for `unit_mocked`, `graph_integration`, `container`, and `deployed`, including target and fixture identity, command/probe, timestamps, result, configuration fingerprint, and artifact references; verify schema tests reject missing provenance and attempted layer promotion.
- [ ] 1.3 Add isolated deterministic tenant, user, assistant, thread, run, report, document, memory, MCP, and stream fixtures with bounded state polling; verify repeated fixture runs produce equivalent normalized observations without live-model or arbitrary-sleep dependence.

## 2. Unit/mocked and graph/integration evidence

- [ ] 2.1 Add narrow graph identity and registration/authentication checks covering the authoritative configured graph, obsolete/unknown graph failure, unauthenticated registered access, authenticated unregistered access, and authenticated registered success; verify only the selected focused cases pass and evidence is classified no higher than its actual layer.
- [ ] 2.2 Add a graph/integration check that routes from the compiled Jasper parent into the genuine Coder child with inherited thread and tenant context, deterministic interrupt, same-thread resume, and wrong-thread/tenant rejection; verify trace/checkpoint evidence proves exactly-once child continuation through the parent.
- [ ] 2.3 Add deterministic memory and documentation-RAG checks with two tenants using colliding keys, names, and semantic text, including direct, semantic, reused-thread, crafted-filter, update, and delete attacks; verify each tenant sees only its own content/provenance and the foreign fixture remains unchanged.
- [ ] 2.4 Add typed Coder report fixtures for completed, blocked, failed, authorization-required, malformed, and invalid-transition results plus Jasper summary assertions; verify required facts and status survive while a sentinel raw-report body is not dumped.
- [ ] 2.5 Add the shared normalized MCP contract across every supported backend for discovery, allowed invocation, stable errors, and supported cancellation/timeout behavior; verify the parity selector reports per-backend semantic results rather than byte-equal transport envelopes.
- [ ] 2.6 Add MCP security cases for missing authentication, wrong tenant, disallowed tools, invalid traversal-style arguments, no-side-effect rejection, and sentinel-secret redaction; verify every supported backend enforces the same decisions and captured client/log evidence contains no sentinel secret.
- [ ] 2.7 Add a graph/integration stream case that disconnects after a known event, permits server-side continuation, rejoins by run/thread and cursor, repeats the acknowledged cursor, and attempts cross-tenant rejoin; verify ordered reconstruction has no duplicate committed event, exactly one terminal outcome, and no cross-tenant disclosure.

## 3. Container evidence

- [ ] 3.1 Add a minimal isolated container verification profile containing only Agent Server, PostgreSQL, and narrowly required scoped dependencies, with redacted configuration capture and health/state polling; verify startup does not require unrelated application suites or browser audio services.
- [ ] 3.2 Add the PostgreSQL authority probe that persists an interrupt/checkpoint, restarts Agent Server while retaining PostgreSQL, resumes the same authorized thread, and then makes PostgreSQL unavailable; verify restart continuity and explicit persistence failure with no legacy application-owned fallback.
- [ ] 3.3 Run the stream disconnect/rejoin and applicable auth/registration probes through the public container service boundary; verify their container evidence records identify actual service/configuration targets and are not derived from imported source tests.

## 4. Removal proof and focused aggregation

- [ ] 4.1 Build the reviewed forbidden-reference manifest for obsolete graph IDs, routes, persistence owners, adapters, configuration keys, imports, and runtime entrypoints, with only exact-path historical/migration exceptions and rationale; verify a manifest check rejects broad exclusions.
- [ ] 4.2 Add zero-match checks over executable source, active/effective configuration, container definitions, and runtime entrypoints plus a known-forbidden self-test fixture; verify clean surfaces produce zero non-allowlisted matches and the self-test reports the exact token and location.
- [ ] 4.3 Add the focused runner and evidence aggregator that execute only matrix-selected checks, retain per-claim results, and forbid promoting unit/mocked or graph/integration evidence to container/deployed status; verify deployed coverage is reported `not-run/out-of-scope` rather than accepted by phase 10.
- [ ] 4.4 Produce the phase-10 evidence summary split into unit/mocked, graph/integration, container, and deployed sections, listing failures as blockers without repairing phase 1–9 product behavior; verify it excludes real-browser STT/TTS, broad unrelated suites, and deployed final acceptance.

## 5. Validation

- [ ] 5.1 Run `npx --yes @fission-ai/openspec@latest validate phase-10-focused-verification --strict` from the repository root and verify strict validation succeeds.
- [ ] 5.2 Identify files changed by phase-10 implementation and run configured file-scoped lint and type checks, or the narrowest supported containing target where file scoping is unavailable; verify each applicable result or explicit inapplicability is recorded without claiming deployed validation.
- [ ] 5.3 Re-run only the claim-matrix selectors needed for final phase-10 evidence and verify all scoped results are reproducible, correctly layered, and ready to hand off to phase 11 without executing deployed final acceptance.
