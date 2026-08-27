## Context

See `proposal.md` and the two capability specs. Agent Server checkpoints already provide durable execution state, but durability does not make them cross-session memory. The memory layer must use public Agent Server Store operations, while documentation retrieval needs an independently authorized corpus boundary. Both may reside in one PostgreSQL deployment only if application ownership and Agent Server internal-table boundaries remain explicit.

The design must work without assuming Store compare-and-swap, checkpoint/Store atomicity, semantic search, a configured vector index, or Librarian ingestion. Exact deployed Store behavior, existing identity middleware, and safe lexical-query support must be inventoried before implementation.

## Goals / Non-Goals

**Goals:**

- Put one trusted server-side policy enforcement point in front of both capabilities.
- Encode capability, tenant, trust domain, owner, and (for documents) corpus into every authorized storage/retrieval scope.
- Keep personal and work scopes non-overlapping and re-check work membership on every operation and pagination request.
- Make memory writes, reads, retention, deletion, provenance, and audit behavior bounded and testable.
- Return grounded documentation results with inspectable lexical match information and source provenance.
- Permit physical co-location in PostgreSQL without logical co-mingling or direct application writes to Agent Server internal tables.

**Non-Goals:**

- No checkpoint migration, checkpoint-derived automatic memory, or duplicate checkpoint/message ledger.
- No Coder graph topology, Coder report handoff, MCP surface, or UI work.
- No Librarian wiring, source acquisition, parsing, ingestion, chunking, corpus population, reindexing, or documentation-deletion implementation.
- No vector/embedding index, semantic-search claim, ontology, knowledge graph, or custom inference logic.
- No agent-held database, Store, source-system, index, or embedding-provider credentials.

## Decisions

### 1. Use two storage authorities behind one policy-enforcement pattern

Cross-session memory is stored only through supported Agent Server Store APIs in application-owned namespaces. Documentation uses a separate application-owned corpus repository; an implementation may back it with supported Store APIs or dedicated application-owned PostgreSQL schema/tables, but never Agent Server internal tables. The selection is pinned after a read-only capability inventory and must preserve the same corpus contract.

Physical co-location is deployment convenience only. Neither repository can query or mutate the other, and each has a separate least-privilege service role or equivalent Store authorization path. If PostgreSQL roles cannot prevent direct access to Agent Server internal tables, rollout stops.

**Alternative rejected:** writing memory or documents into Agent Server persistence tables, because those tables are not an application API and upgrades, authorization, and ownership would be unsafe.

**Alternative rejected:** one mixed memory/document namespace, because personal recollections and governed source documents have different ownership, provenance, lifecycle, and access rules.

### 2. Resolve scope from verified identity, never from agent text

A trusted gateway receives authenticated identity and current context, resolves memberships and grants, and creates an internal authorization context:

- `principal_id` and principal type;
- `context_kind` (`personal` or `work`);
- `tenant_id`;
- `trust_domain_id`;
- permitted owner scopes;
- permitted capability operations;
- permitted corpus IDs for documentation;
- correlation ID and delegation expiry.

The gateway rejects missing, stale, contradictory, or caller-overridden scope. It mints an in-process or short-lived opaque delegation containing no persistence credential. Repository adapters accept only this authorization context, not arbitrary tenant/owner strings from model output. Pagination tokens are scope-bound, revision-bound, integrity-protected, short-lived, and reauthorized when used.

**Alternative rejected:** allowing prompts, graph state, or tool arguments to select raw namespaces, because unverified values would permit confused-deputy and cross-tenant access.

### 3. Apply a deny-by-default operation matrix

| Principal/context | Memory read | Memory write | Memory delete | Documentation read |
|---|---:|---:|---:|---:|
| Verified personal owner in personal tenant | Own scope with grant | Own scope with grant | Exact own record with grant | Explicitly granted personal corpora only |
| Verified work member | Granted work owner scopes only | Granted work owner scopes only | Exact granted work records only | Explicitly granted work corpora only |
| Delegated agent invocation | Current verified scope and delegated operation only | Current verified scope and delegated operation only | Only if separately delegated for exact record | Current verified scope and delegated corpora only |
| Infrastructure operator | Denied by default | Denied by default | Denied by default | Denied by default |
| Unverified or stale principal | Denied | Denied | Denied | Denied |

`read`, `write`, and `delete` are independent grants. A request cannot span personal and work tenants, multiple trust domains, or ungranted owners/corpora. A multi-corpus documentation request is allowed only when every corpus is explicitly granted in the same tenant and trust domain; otherwise the request fails closed rather than returning a partial authorization view.

**Alternative rejected:** filter-after-fetch authorization, because unauthorized records would already have crossed the storage boundary and existence could leak.

### 4. Use explicit logical namespace families

The authorization layer constructs namespace components after validation. The adapter encodes them into the deployed backend's supported tuple/key form:

- Memory: `app / v1 / cross-session-memory / tenant:{id} / trust:{id} / owner:{type}:{id} / kind:{kind}`
- Documentation: `app / v1 / documentation-retrieval / tenant:{id} / trust:{id} / owner:{type}:{id} / corpus:{id} / record:{type}`
- Sanitized audit: a separately permissioned audit sink keyed by capability and tenant, never a content namespace.

Identifiers are opaque, normalized, length-bounded, and server-derived. Prefix listing is never exposed to agents. Personal and work tenant IDs are different identifiers, not labels on a shared owner namespace. A namespace conformance test must prove that changing any capability, tenant, trust-domain, owner, or corpus component cannot return records from the original scope.

**Alternative rejected:** owner-only namespaces, because the same principal may have personal and multiple work identities with different trust and retention rules.

### 5. Store bounded memory envelopes and immutable provenance

A memory envelope contains schema version, immutable record ID, logical memory kind, bounded content and metadata, server-derived scope, provenance, server timestamps, retention policy/expiry, lifecycle state, revision, and deterministic operation ID. Provenance records the source session or approved external source, creator principal/service, creation method, and source time status; it does not copy checkpoint state or internal reasoning.

Writes validate the complete envelope before persistence. Retries reuse the operation ID. Implementations must not claim atomicity with checkpoints. Where the Store lacks conditional updates, immutable revision records plus deterministic read resolution and reconciliation prevent an older retry from silently replacing a newer revision; exact behavior must be contract-tested against the deployed Store adapter before enablement.

Secrets, credentials, auth headers, private keys, and internal reasoning are rejected content classes. Configured limits cover content, metadata, fields, batch size, candidate scan, query, result count, and response bytes. Limits are deployment configuration with reviewed safe maxima, not agent-controlled values.

**Alternative rejected:** mutable transcript or checkpoint blobs, because they are unbounded, mix execution with memory, obscure provenance, and make deletion unsafe.

### 6. Make memory creation an explicit authorized action

No checkpoint, thread, message, tool result, report, or artifact becomes memory merely by existing. A separate `cross-session-memory:write` operation validates scope, content class, provenance, bounds, and retention before writing. A session reference may be stored as provenance, but canonical execution state remains checkpoint-owned.

This phase defines no autonomous memory-extraction ontology. Memory kinds are a small allowlist used for validation and filtering, not an ontology or inference system.

**Alternative rejected:** automatically summarizing every session into memory, because consent, accuracy, tenant context, retention, and provenance would be ambiguous.

### 7. Implement inspectable non-semantic retrieval

Exact lookup resolves a scoped identifier. Metadata filtering accepts only allowlisted fields and values. Lexical retrieval uses a documented tokenizer, case/normalization rules, scoring formula, and stable record-ID tie-breaker over a hard-bounded authorized candidate set or a native lexical index whose behavior is pinned by tests. Responses label `exact`, `metadata-filtered`, and/or `lexical` modes.

The documentation response includes corpus, document, fragment/locator, title, approved URI/opaque locator, source revision, digest, source-time status, retrieval time, and match mode. Memory results include their record provenance. Unknown provenance remains `unknown`. Documents are treated as untrusted data; their text cannot modify authorization or invoke capabilities.

A future vector index can be additive only through a separate OpenSpec defining embedding model/version, index ownership, tenant isolation, reindex/deletion behavior, evaluation, and truthful semantic-search labeling. Ontology remains future custom logic.

**Alternative rejected:** using an embedding-capable API without a configured and evaluated index, because lexical results must not be mislabeled as semantic retrieval.

### 8. Enforce lifecycle before returning content

Memory records require an approved retention class or expiry. Normal reads first enforce lifecycle state and expiry. Exact, owner-authorized deletion writes an idempotent unavailable state, emits a sanitized audit event, and invokes the approved purge mechanism; restore is unavailable unless separately approved. Retention and audit-retention durations, purge service level, backup interaction, and legal-hold handling are release-gated configuration owned by human policy authorities.

Documentation retrieval consumes lifecycle metadata from an already approved corpus snapshot and excludes deleted, expired, quarantined, withdrawn, or unverifiable candidates. Creating that metadata and implementing document/corpus deletion are deferred; this phase only enforces available status during read.

**Alternative rejected:** delete-by-query or tenant-wide agent deletion, because broad mutable operations violate least privilege and make accidental cross-scope loss more likely.

### 9. Keep credentials and audits outside agent context

Only trusted services receive backend credentials. Agent-visible tools expose typed capability operations, bounded request fields, bounded results, and sanitized errors. Audit events contain verified identity, scope identifiers, operation, decision/reason class, match mode, correlation ID, time, and counts—never memory/document bodies, raw queries when policy forbids them, credentials, connection strings, or internal reasoning.

Audit storage has a separately approved access and retention policy. Error messages avoid record-existence and corpus-statistics leaks across denied scopes.

**Alternative rejected:** giving agents read-only database credentials, because read-only still permits uncontrolled enumeration and bypasses per-operation policy, bounds, and audit handling.

### 10. Librarian and corpus mutation remain disconnected

No Librarian path receives a corpus write operation in this phase. Documentation retrieval can be tested against synthetic fixtures and can read an externally approved, pre-existing corpus snapshot after authorization, but it cannot acquire, parse, chunk, populate, reindex, or delete corpus content. Capability responses report these mutations as unsupported rather than pretending they succeeded.

**Alternative rejected:** a placeholder ingestion path, because even dormant wiring would obscure source approval, chunk provenance, retention, reindex consistency, and deletion obligations that need their own design.

## Risks / Trade-offs

- [Shared PostgreSQL increases blast radius] → use application-owned schemas or supported Store namespaces, separate least-privilege roles, explicit grants, backup review, and tests proving no access to Agent Server internal tables.
- [Namespace mistakes cause cross-tenant disclosure] → derive scope server-side, centralize encoding, deny raw namespace input, test every namespace dimension, and fail closed.
- [Revoked work access persists in pagination or caches] → reauthorize every request/token use, bind tokens to scope and corpus revision, and keep result caches scope-bound and short-lived.
- [Store update races lose memory revisions] → use deterministic operation IDs, immutable revision strategy, stale-write tests, and reconciliation without assuming CAS or checkpoint/Store atomicity.
- [Application lexical scanning becomes expensive] → enforce candidate and response bounds; require a separately owned lexical index or stop rollout when measured limits cannot be met.
- [Lexical retrieval misses conceptual matches] → describe match mode truthfully; defer vector search rather than implying semantic quality.
- [Provenance exposes sensitive locators] → use approved opaque locators, field-level response policy, and no raw protected paths.
- [Deletion conflicts with backups or policy] → gate enablement on approved retention, purge, backup, legal-hold, and restore decisions; test immediate read exclusion separately from physical purge.
- [Documentation becomes prompt-injection material] → mark it as untrusted data, preserve citations, and keep authorization/capability decisions outside retrieved content.
- [No ingestion means an empty production corpus] → do not claim corpus population; validate retrieval with synthetic fixtures and enable production reads only for an independently approved existing snapshot.

## Migration Plan

1. Inventory the deployed Store API/version, namespace behavior, identity source, membership/grant checks, PostgreSQL ownership, internal Agent Server tables, and available lexical-query mechanisms using read-only inspection.
2. Obtain human approval for tenant/trust-domain definitions, owner types, operation grants, record limits, memory kinds, retention/expiry classes, purge and backup behavior, audit access/retention, and any pre-existing documentation snapshot. Stop if any required policy owner or isolation control is absent.
3. Implement the central authorization context and namespace encoder behind disabled capability entry points; provision only application-owned permissions and prove direct Agent Server internal-table access is impossible.
4. Implement and test the memory Store adapter, immutable provenance/revision behavior, bounded exact/metadata/lexical reads, lifecycle enforcement, exact deletion, and sanitized audits with synthetic isolated namespaces.
5. Implement documentation read-only retrieval against synthetic fixtures, then optionally an approved pre-existing corpus snapshot. Do not add Librarian or corpus mutation paths.
6. Run cross-tenant, revoked-membership, spoofed-scope, operation-separation, pagination, bounds, race/retry, expiry/deletion, prompt-injection, provenance, credential-leak, and internal-table isolation tests.
7. Enable capability grants for a limited tenant only after strict OpenSpec and focused acceptance validation. Monitor denial classes, bounded latency, candidate limits, and lifecycle failures without logging content.
8. Roll back by revoking capability grants and disabling the adapters. Preserve memory records for approved retention/deletion processing; do not delete documentation or modify Agent Server internal persistence as part of rollback.

## Open Questions

- Which approved pre-existing documentation snapshot, if any, will be available for production read-only retrieval? An empty corpus is valid and must be reported honestly until a separate ingestion change is approved.
- Which supported lexical mechanism meets the measured candidate and latency bounds in the deployed environment? The answer may select Store-backed bounded matching or an application-owned lexical index but cannot introduce semantic behavior or internal-table writes.
