## Context

Agent Server checkpoints are durable execution state, not cross-session memory. Private memory must use public Agent Server Store operations in application-owned namespaces. Documentation requires an independently authorized corpus boundary. Phase 5 supports one person per private installation and one separate database per installation; it defines no work members or shared/work memory.

## Goals / Non-Goals

**Goals:**

- Centralize server-side authorization for memory and documentation.
- Derive the opaque tenant, `local-installation-v1` trust domain, and `person` owner from trusted server configuration.
- Preserve bounded memory, immutable provenance, explicit creation, deterministic non-semantic retrieval, and enforceable deletion.
- Preserve a separate, grounded documentation corpus and the approved supervisor-mediated OCR ingestion path.
- Keep application code away from Agent Server internal PostgreSQL tables and all persistence credentials away from agents.

**Non-Goals:**

- Shared/work memory, work-member policy, checkpoint migration, checkpoint-derived memory, direct specialist communication, MCP, general UI work, vector/semantic retrieval, ontology, reindexing, and document/corpus deletion.

## Decisions

### 1. Separate memory and documentation authorities

Memory and documentation both use supported Agent Server public Store APIs, in separate server-derived application namespace families. This is an approved architecture decision: there are no direct PostgreSQL corpus tables and neither capability may select or write Agent Server internal tables or query the other. Production documentation starts empty.

### 2. Use service-level PostgreSQL least privilege, not model identities

The trusted standalone Agent Server service is the PostgreSQL principal for its migrations and runtime operations. Browser, owner, Jasper, Coder, Librarian, and OCR identities are HTTP/auth-capability principals, not SQL roles, and receive no database URI. Because PostgreSQL reserves object-definition changes to owners, the smallest role that supports the observed startup migrations is a non-superuser login that owns only the Agent Server `public` schema and its observed relations, with database `CONNECT`, `CREATE`, and `TEMPORARY`; it does not own the database, extensions, roles, or the application projection schema.

The existing application-owned `session_catalog` code opens a separate connection through `POSTGRES_URI` and runs idempotent DDL. A second non-superuser service login therefore owns only that schema. The later rollout must map documented standalone `DATABASE_URI` to the Agent Server role and repository `POSTGRES_URI` to the projection role, resolve the currently duplicated URI aliases, and retain the same database and volume. This service-role split does not make untrusted graph code a database principal or a secure process sandbox; credentials must remain outside model-visible requests, state, results, errors, and telemetry.

Both memory and documentation use the same supported Agent Server `BaseStore` and the same physical `store` relation. The public Store integration supplies namespaces, not a per-namespace SQL principal or connection selector. PostgreSQL grants therefore cannot enforce memory-versus-document row privileges behind this boundary. Phase 5 relies on default-deny capabilities and server-derived namespace isolation and does not add RLS, direct SQL, a custom Store/checkpointer, or graph/database infrastructure.

### 3. Resolve one private installation scope server-side

Trusted configuration generates or loads one opaque tenant ID and owner ID, fixes owner type `person` and trust domain `local-installation-v1`, and supplies the only valid scope. Prompts, browser values, tools, and agent output cannot select scope. Missing, conflicting, shared, or work scope fails closed.

### 4. Enforce independent least-privilege operations

The owner may receive memory read, explicit write, exact delete, exact restore, permanent delete, and owner-only audit access. Jasper, Coder, and Librarian may receive bounded delegated memory operations; OCR cannot. Jasper, Coder, Librarian, and OCR may receive explicit documentation-read delegation. Corpus writes require a current supervisor-created ingestion delegation. Infrastructure operators have no default content access.

### 5. Use explicit namespace families

- Memory: `app / v1 / cross-session-memory / tenant:{id} / trust:{id} / owner:person:{id} / kind:{kind}`
- Documentation: `app / v1 / documentation-retrieval / tenant:{id} / trust:{id} / owner:person:{id} / corpus:{id} / record:{type}`
- Sanitized audit: separately permissioned and never a content namespace.

Identifiers are normalized, opaque, bounded, and server-derived. Prefix enumeration is not agent-visible.

### 6. Store bounded memory envelopes with explicit creation

An envelope includes schema version, immutable ID, kind, bounded content/metadata, server scope, provenance, timestamps, lifecycle state, revision, and deterministic operation ID. Kinds are exactly `user preferences`, `user-provided facts`, `project decisions`, `task outcomes`, and `reusable instructions`. Per-kind and request limits are those in the capability spec. Limits never trigger automatic eviction.

No checkpoint, thread, message, tool result, report, or artifact becomes memory merely by existing. Store behavior must be contract-tested; the design assumes neither compare-and-swap nor atomic checkpoint/Store writes.

### 7. Make retrieval inspectable and non-semantic

Memory and documentation support exact lookup, allowlisted metadata filters, and bounded same-word lexical matching over no more than 1000 already-authorized candidates. Normalize case/tokens; rank by descending count of query words present, then stable record ID. Return match mode and provenance. Do not claim vector, semantic, conceptual, ontology, or inference behavior.

Documentation results include corpus, document, fragment/locator, title, approved URI or opaque locator, source revision, digest, source-time status, retrieval time, and match mode. Unknown provenance stays `unknown`. Retrieved text is untrusted data and cannot affect authorization.

### 8. Enforce the approved memory lifecycle

Memory remains until owner deletion. Exact deletion immediately excludes content from every normal read. The exact owner can restore it for exactly seven days. Once that window ends, content is permanently purged and cannot be restored. Owner-authorized permanent delete purges the exact deleted item immediately. Content-free memory audit events are owner-only and retained 90 days. They contain identifiers, operation, decision/reason class, correlation, time, and counts, never memory bodies, credentials, or internal reasoning.

### 9. Preserve approved documentation ingestion

Librarian may request public HTTPS pages, public PDFs, owner-uploaded documents, or explicitly source-approved private-workspace documents. Coder may submit explicitly selected Markdown, plain text, PDF, or DOCX reports that pass sensitive-data checks. The existing supervisor validates each request, routes accepted content through existing OCR, and requests a bounded trusted corpus write only after OCR succeeds. Specialists neither communicate directly nor receive persistence credentials. Production starts empty; synthetic fixtures validate the path.

## Risks / Trade-offs

- Namespace mistakes could disclose content; derive all scope server-side and test each namespace dimension.
- Store races could lose revisions; use deterministic operations and tested revision resolution without assumed atomicity.
- Lexical matching may miss concepts; label it truthfully and keep hard candidate/response bounds.
- Deletion timing can regress; test immediate exclusion, both sides of the exact seven-day boundary, restore ownership, and permanent purge.
- Documents can contain prompt injection; treat text as data and keep policy outside retrieval content.
- Failed ingestion can pollute a corpus; require source approval, OCR success, complete provenance, and bounded all-or-nothing writes.

## Migration Plan

1. Inventory deployed public Store behavior, identity/configuration, PostgreSQL ownership, and lexical support read-only.
2. Prepare but do not apply exact-owner service-role SQL; validate it statically and rehearse it against a restored clone of the existing database with the pinned image.
3. Prove browser/agent identities receive no SQL credential and that the two service URIs select only their intended schemas; accept that one BaseStore cannot enforce per-namespace SQL grants.
4. Implement disabled authorization and namespace boundaries, then memory and synthetic documentation adapters.
5. Add lifecycle, audit, ingestion, isolation, race, bounds, injection, credential-leak, and deployed role-denial tests.
6. Enable only after backup/restore proof, migration/startup rehearsal, focused acceptance testing, and human release approval. Preserve the database, named volume, and sessions; rollback requires a reviewed inverse ownership/configuration plan and must not recreate or merge persistence.

## Verified implementation inventory and rollout facts

- Source environment inventory recorded `langgraph==1.2.11` and `langgraph-api==0.11.2`; the read-only deployed-container audit on 2026-08-29 found `langgraph==1.2.11` and `langgraph-api==0.13.0`. The installed SDK documents `Auth.authenticate`, global default-deny `Auth.on`, thread `create_run`, assistant handlers, and Store `get`/`put`/`delete`/`search`/`list_namespaces` handlers. Raw namespace listing is denied.
- The public Store surface used here is synchronous and asynchronous `get_item`, `put_item`, `delete_item`, `search_items`, and namespace listing. Phase 5 uses only get/put/delete/bounded search in application Store namespaces. Checkpoints are a separate execution-persistence surface and are never promoted.
- Store has no assumed compare-and-swap primitive. Memory uses immutable revision keys, deterministic highest-revision reconciliation, explicit stale-revision rejection, and physical removal of content-bearing revisions on purge. Operation records are excluded from the 15 MiB live-envelope accounting.
- Read-only catalog queries found PostgreSQL 16.15, one login role (`postgres`) with superuser/role/database-creation powers, database owner `postgres`, Agent Server relations in `public`, application projection relations in `session_catalog`, and all observed relations owned by `postgres`. Existing extensions are `btree_gin`, `ltree`, and `plpgsql`, also operator-owned. The current Compose configuration supplies the same superuser URI under `DATABASE_URI`, `POSTGRES_URI`, `DATABASE_URL`, and `POSTGRES_URI_CUSTOM`; IAM is not enabled.
- The observed Agent Server tables are `assistant`, `assistant_versions`, `checkpoint_blobs`, `checkpoint_delete_queue`, `checkpoint_writes`, `checkpoints`, `cron`, `run`, `schema_migrations`, `store`, `thread`, and `thread_ttl`, plus the checkpoint-delete sequence and their indexes. Current migrations and runtime can be served by a non-superuser owner of only these objects and `public`, with database connect/create/temporary privileges; database and extension ownership are unnecessary for the audited version. The application projection requires its own schema owner because `ensure_catalog_schema()` executes DDL.
- `backend/deploy/postgres/phase5_least_privilege.sql` and its static tests are unapplied preparation only. Actual role creation, ownership transfer, credential provisioning, URI cutover, restored-clone migration rehearsal, deployed internal-table denial, production enablement, and release approval remain unchecked rollout work. A future Agent Server version can add migrations or extension requirements, so each upgrade must be rehearsed and the allowlist re-audited.
- The single physical `public.store` relation holds every Store namespace. The documented public integration has no per-namespace SQL identity boundary; memory/document separation is capability/namespace isolation only, not a PostgreSQL grant claim.
- Source-level synthetic verification uses an injected Store double and an empty documentation corpus. Lexical matching is NFKC/casefolded same-word ranking over at most 1000 already-authorized candidates, with stable record-ID ties; it is not semantic retrieval.
