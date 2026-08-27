## 1. Baseline and policy gates

- [ ] 1.1 Inventory the deployed Agent Server Store version and public operations, checkpoint persistence boundary, namespace/list/filter behavior, update guarantees, existing verified-identity source, membership/grant checks, and available non-semantic lexical mechanisms; record observed facts separately from proposed behavior.
- [ ] 1.2 Map Agent Server-owned PostgreSQL schemas/tables and application-owned storage, then prove the proposed memory and documentation service identities cannot directly write Agent Server internal tables.
- [ ] 1.3 Obtain human approval for personal/work tenant construction, trust-domain identifiers, owner types, capability operation grants, corpus grants, and the deny-by-default access matrix. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 1.4 Obtain human-owned values for record/query/result/candidate limits, memory-kind allowlist, memory and audit retention classes, expiry, purge service level, backup/legal-hold interaction, restore policy, and audit access. Stop implementation if any required decision is absent. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 1.5 Select and document a supported bounded lexical mechanism and, if production documentation reads are planned, identify an independently approved pre-existing corpus snapshot; accept and report an empty corpus rather than adding ingestion.

## 2. Verified authorization and namespace isolation

- [ ] 2.1 Implement the trusted authorization context from verified principal, context kind, tenant, trust domain, owner grants, capability operations, corpus grants, correlation ID, and delegation expiry; reject caller overrides and stale or contradictory identity.
- [ ] 2.2 Implement separate namespace encoders for `cross-session-memory` and `documentation-retrieval`, including tenant, trust domain, owner, record kind, and corpus components as applicable, with normalization and hard length limits.
- [ ] 2.3 Implement independent `read`, `write`, and exact-record `delete` enforcement for memory plus explicit per-corpus documentation `read`; keep personal and work contexts in different security tenants and deny mixed-scope requests.
- [ ] 2.4 Implement scope-bound, integrity-protected, short-lived pagination/delegation tokens that contain no persistence credentials and are reauthorized on use.
- [ ] 2.5 Add namespace and policy tests that vary capability, tenant, context kind, trust domain, owner, operation, and corpus one dimension at a time and prove no cross-scope enumeration, existence leak, partial authorization, or filter-after-fetch behavior.

## 3. Cross-session memory Store layer

- [ ] 3.1 Implement the application-owned memory envelope with immutable ID, schema version, server-derived scope, allowlisted kind, bounded content/metadata, provenance, timestamps, retention/expiry, lifecycle state, revision, and deterministic operation ID.
- [ ] 3.2 Implement validated memory writes through supported Agent Server Store APIs only, including idempotent retries, immutable revision resolution, stale-write handling, and reconciliation without assuming CAS or checkpoint/Store atomicity.
- [ ] 3.3 Implement scoped exact-key, allowlisted metadata, and bounded lexical memory reads with documented normalization/ranking, stable tie-breaking, hard candidate/response limits, provenance, and truthful match-mode labels.
- [ ] 3.4 Implement explicit write-only memory creation so checkpoint, thread, message, tool, report, and artifact persistence never auto-promotes content into cross-session memory; add checkpoint-save regression tests.
- [ ] 3.5 Implement expiry enforcement and exact, authorized, idempotent memory deletion with immediate read exclusion, approved physical-purge scheduling, denied restore unless policy permits it, and non-content audit events.
- [ ] 3.6 Add memory contract tests for required fields, unknown provenance, prohibited content classes, oversize rejection without partial writes, duplicates, reordered/stale revisions, query bounds, expiry, purge handoff, and personal/work isolation.

## 4. Read-only documentation retrieval

- [ ] 4.1 Implement a read-only application-owned corpus adapter using the approved Store or application PostgreSQL boundary, with no direct Agent Server internal-table access and no fallback to cross-session memory.
- [ ] 4.2 Implement exact-identifier, allowlisted metadata, and bounded lexical retrieval against synthetic fixtures, with documented tokenizer/normalization/scoring, stable tie-breaking, corpus-revision binding, and explicit non-semantic match modes.
- [ ] 4.3 Return bounded provenance-bearing results with corpus, document, fragment/locator, title, approved URI or opaque locator, source revision, digest, source-time status, retrieval time, lifecycle state, and match mode; preserve `unknown` rather than inferring provenance.
- [ ] 4.4 Enforce lifecycle-at-read by excluding deleted, expired, quarantined, withdrawn, or unverifiable records and reporting sanitized partial/failure status without implementing corpus mutation.
- [ ] 4.5 Treat retrieved text as untrusted data and test that embedded instructions cannot widen scope, alter grants, invoke capabilities, request another tenant, or expose credentials.
- [ ] 4.6 Return explicit unsupported-capability responses for semantic/vector search, ontology logic, Librarian population, source acquisition, ingestion, parsing, chunking, corpus population, reindexing, and document/corpus deletion.
- [ ] 4.7 If an approved pre-existing corpus snapshot exists, run the same read-only authorization, bounds, provenance, lifecycle, and ranking tests against it; otherwise verify the production path reports an empty corpus without claiming ingestion.

## 5. Credentials, audit, and operational safety

- [ ] 5.1 Provision least-privilege service roles or equivalent Store authorization so memory and documentation repositories cannot mutate each other or Agent Server internal tables; verify infrastructure operators have no default content access.
- [ ] 5.2 Keep Store, database, source-system, future index, and embedding-provider credentials exclusively in trusted server infrastructure and add tests proving agent requests, contexts, results, errors, and telemetry contain no credential or connection-secret material.
- [ ] 5.3 Implement bounded allowed/denied audit events with verified identity, authorized scope, operation, decision/reason class, correlation ID, time, match mode, and counts, excluding memory/document bodies, credentials, and internal reasoning.
- [ ] 5.4 Add revoked-membership, revoked-corpus-grant, spoofed namespace/owner, read-versus-write-versus-delete, pagination reauthorization, operator denial, backend failure, and existence-oracle tests.
- [ ] 5.5 Add disposable test safeguards that require synthetic isolated namespaces or fixture-owned application storage and refuse production data, broad credentials, Agent Server internal-table writes, or corpus mutation.

## 6. Release and scope verification

- [ ] 6.1 Run all capability contract, namespace isolation, authorization, bounds, provenance, lifecycle, retry/race, lexical ranking, injection, audit, credential-leak, and internal-table isolation tests and record exact pass/fail results.
- [ ] 6.2 Run `openspec validate phase-5-cross-session-memory-and-documentation-rag --strict` and resolve every validation error before implementation approval.
- [ ] 6.3 Obtain release approval for the selected lexical mechanism, measured limits, identity and tenant isolation, retention/deletion behavior, least-privilege roles, audit policy, and any production read-only corpus snapshot. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [ ] 6.4 Enable `cross-session-memory` and `documentation-retrieval` grants for a limited tenant, monitor sanitized denial/failure classes and bound utilization, and roll back by revoking grants and disabling adapters without modifying Agent Server internal persistence.
- [ ] 6.5 Confirm the implementation did not change Coder graph topology, report handoff, MCP, UI, checkpoints, Librarian wiring, ingestion, chunking, corpus population, reindexing, documentation deletion, vector indexing, semantic-search claims, or ontology logic.
