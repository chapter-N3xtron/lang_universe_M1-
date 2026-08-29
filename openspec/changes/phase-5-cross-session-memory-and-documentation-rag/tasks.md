## 1. Baseline and approved policy

- [ ] 1.1 Inventory deployed Agent Server Store public operations, checkpoint boundaries, namespace/list/filter behavior, update guarantees, verified identity, and non-semantic lexical mechanisms; separate observed facts from proposals.
- [ ] 1.2 Map Agent Server-owned PostgreSQL objects and application-owned storage, and prove application identities cannot directly select or write internal tables. (A 2026-08-29 read-only catalog audit mapped the current `public` Agent Server relations, `session_catalog` projection relations, role attributes, owners, and extensions. Browser/agent principals have no intended SQL role, and exact non-superuser service-role preparation exists, but deployed credential cutover and denial proof remain unapplied.)
- [x] 1.3 Record the human-approved private-installation policy: separate database per person; opaque server tenant; `local-installation-v1`; server-configured `person` owner; no shared/work memory; owner read, explicit write, exact delete, exact restore, and permanent delete; Jasper/Coder/Librarian memory delegation but not OCR; documentation read for Jasper/Coder/Librarian/OCR. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [x] 1.4 Record the human-approved memory kinds and bounds, no automatic eviction, immediate exclusion after deletion, exact seven-day owner restore followed by permanent purge, immediate owner permanent delete, and owner-only content-free audits retained 90 days. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [x] 1.5 Record the human-approved bounded same-word retrieval policy and documentation ingestion decisions: approved source/artifact classes, existing-supervisor-to-OCR routing, empty production corpus, and synthetic test fixtures.

## 2. Authorization and namespace isolation

- [x] 2.1 Implement a trusted authorization context using only server-derived installation, tenant, trust-domain, owner, capability, corpus, correlation, and delegation-expiry values; reject caller overrides.
- [x] 2.2 Implement distinct namespace encoders for memory and documentation with normalization and hard limits.
- [ ] 2.3 Enforce independent memory read/write/exact-delete/restore/permanent-delete permissions and explicit corpus read/write delegation; reject shared, work, mixed-scope, and unverified requests. (Core contracts are implemented; deployed grant provisioning remains fail-closed rollout work.)
- [x] 2.4 Implement pagination only if paginated capability operations are exposed. Current completed operations reject over-limit requests and expose no pagination token; integrity-protected expiring delegation-token primitives remain available but no pagination claim is made.
- [ ] 2.5 Test every namespace dimension and prove no cross-scope enumeration, existence leak, partial authorization, or filter-after-fetch. (Focused owner/tenant/trust/family tests exist; deployed existence-oracle proof remains.)

## 3. Cross-session memory

- [x] 3.1 Implement bounded provenance-bearing memory envelopes and public-Store-only writes with idempotent retries and immutable revision reconciliation without assuming CAS or checkpoint/Store atomicity.
- [x] 3.2 Implement scoped exact, metadata, and bounded lexical reads with deterministic ordering and truthful match-mode labels.
- [x] 3.3 Prove checkpoints, threads, messages, tools, reports, and artifacts never become memory without a separate authorized write. (An isolated graph/checkpointer contract persists synthetic messages, tool results, reports, and artifacts while the memory Store family remains empty, then confirms only a separate authorized capability write creates memory.)
- [x] 3.4 Implement exact deletion with immediate normal-read exclusion, exact owner restore through day seven, scheduled purge eligibility after the boundary, and immediate exact permanent delete.
- [x] 3.5 Add contract tests for fields, provenance, prohibited content, bounds, no partial writes, retries, stale revisions, lifecycle boundaries, no eviction, and installation isolation. (Focused synthetic contracts now cover stale lifecycle rejection without mutation and same-Store tenant/owner isolation in addition to the existing envelope, provenance, prohibited-content, exact-boundary, preflight no-partial-write, idempotent-retry, lifecycle, and no-eviction cases.)

## 4. Documentation retrieval and ingestion

- [x] 4.1 Implement a separate application-owned Store corpus adapter with no fallback to memory and no direct Agent Server internal-table access.
- [x] 4.2 Implement bounded exact, allowlisted metadata, and lexical retrieval against synthetic fixtures with stable ordering and provenance.
- [x] 4.3 Treat documents as untrusted data and enforce lifecycle-at-read; retrieved content cannot select capability scope.
- [x] 4.4 Implement only supervisor-mediated ingestion in the existing OCR node: approved Librarian sources and explicitly selected qualifying Coder artifacts pass through existing Docling-authoritative OCR before an expiring delegated trusted write.
- [x] 4.5 Complete the remaining source-approval and unsupported-operation matrix. Focused tests cover every approved Librarian source class, qualifying and rejected Coder artifacts, sensitive-file rejection, delegation, OCR failure/no record, provenance, direct-write denial, empty-corpus behavior, and every explicitly unsupported operation.

## 5. Credentials, audit, and safety

- [ ] 5.1 Provision least privilege so memory and documentation cannot mutate each other or access Agent Server internal tables. (Unapplied preparation now gives the trusted Agent Server a narrowly owned non-superuser role and the direct-SQL session projection a separate non-superuser role. Browser/agent identities receive neither. The supported single BaseStore/`store` relation cannot enforce different PostgreSQL grants per memory/document namespace, so their mutual isolation is capability/namespace-only; no RLS, direct SQL adapter, custom Store, or graph infrastructure will be invented. Actual rollout and deployed denial checks remain pending.)
- [ ] 5.2 Prove persistence/source credentials never enter agent requests, contexts, results, errors, or telemetry.
- [x] 5.3 Implement bounded content-free owner-only memory audits with 90-day retention and sanitized documentation access audits under approved policy. (Synthetic contracts verify the exact 90-day boundary, pruning, bounded event fields, absence of payload/query/credential fields, documentation read/write scope and match-mode events, and denial of audit reads to a non-owner even if manually given an audit grant.)
- [x] 5.4 Add spoofing, permission separation, pagination, backend-failure, injection, and existence-oracle tests using only isolated synthetic fixtures. (Focused tests reject unverified/caller-selected scope, exercise independent grants, prove no offset/page-token surface, sanitize memory and ingestion backend failures, keep injected document instructions from widening capability access, and prove unauthorized known-shaped/missing exact lookups return the same denial without touching Store.)

## 6. Release verification

- [ ] 6.1 Run capability, isolation, authorization, bounds, provenance, lifecycle, retry/race, lexical-ranking, ingestion, audit, credential-leak, and internal-table-isolation tests and record exact results. (Source-level Phase 5 synthetic suite: `cd backend && .venv/bin/python -m pytest -q tests/test_phase5_capabilities.py tests/test_phase5_acceptance.py tests/test_phase5_ingestion.py` = 62 passed. This aggregate remains unchecked: synthetic Store doubles cannot prove deployed PostgreSQL role denial against Agent Server internal tables, deployed request/context/result/error/telemetry credential exclusion, or deployed Store behavior and existence-oracle isolation.)
- [x] 6.2 Run the project-local strict OpenSpec validator and resolve errors before implementation approval. (`npx --yes @fission-ai/openspec@latest validate phase-5-cross-session-memory-and-documentation-rag --strict`: valid.)
- [ ] 6.3 Obtain release approval for the observed Store mechanism, measured limits, least-privilege roles, and any production corpus snapshot.
- [x] 6.4 Confirm the implementation retained the existing supervisor graph and added no direct specialist communication, shared memory, MCP, vector/semantic behavior, ontology, reindexing, or document/corpus deletion. Source inspection and the focused unsupported-operation/ingestion tests confirm these boundaries.
