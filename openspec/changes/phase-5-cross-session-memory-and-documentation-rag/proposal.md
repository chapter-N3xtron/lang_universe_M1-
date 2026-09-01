# Phase 5: Cross-session memory and documentation RAG

## Why

Sessions need permissioned continuity without treating checkpoints as user memory, and agents need grounded access to an approved documentation corpus without conflating documents with personal memory. This change fixes those boundaries for private, one-person installations.

## What Changes

- Define cross-session memory through the supported Agent Server-injected `BaseStore` interface in application-owned namespaces; application code never selects or writes Agent Server internal PostgreSQL tables.
- Define one canonical installation-wide documentation corpus in the Agent Server-injected `BaseStore`, with independent namespaces, provenance, authorization, and lifecycle enforcement and no per-session duplication of document content.
- Define canonical document-level tags shared across every session, plus bounded thread-scoped links that contain only the authoritative thread/session identity and a stable document ID. Multiple threads may link the same document, and reopening a thread restores its linked-document list without turning those references into cross-session memory.
- Add only the narrow Installation Library and Session Documents UI. Human metadata, semantic, exact-resolution, owner-upload, and public-URL operations use authenticated custom Agent Server FastAPI routes whose documented `langgraph.config.get_store()` access obtains the injected `BaseStore`; graph agents continue using bounded `Runtime.store` tools. The browser never calls Phase 5 Store namespaces, and TanStack Query caches only metadata projections under non-secret auth-partitioned keys. Current-thread link mutation remains a stateful graph run. Local Ollama `embeddinggemma` performs native fragment ranking inside the approved installation trust boundary; graph code retrieves only relevant excerpts rather than placing linked full documents in model context.
- Fix the deployment model to one person and one separate database per installation, with a server-generated opaque tenant ID, trust domain `local-installation-v1`, and server-configured `person` owner ID. Shared/work memory and work-member policy are excluded.
- Grant the owner memory read, explicit write, exact delete, seven-day restore, permanent delete, and owner-only content-free audit access. Jasper, Coder, and Librarian may receive bounded memory delegations; OCR may not. Jasper, Coder, Librarian, and OCR may receive documentation-read delegations.
- Fix memory kinds and bounds: `user preferences`, `user-provided facts`, `project decisions`, `task outcomes`, and `reusable instructions`; 15 MB per kind; 32 KB content; 8 KB/32 metadata fields; 4 KB query; 1000 authorized candidates; 20 results; 256 KB response; and 10 records per write batch.
- Retain active memory without a default TTL and never evict automatically. Keep exactly one current Store item per memory ID. Delete overwrites it as deleted, excludes it immediately, and applies native TTL; owner restore is allowed through the inclusive seven-day logical cutoff and clears TTL, while later restore is denied independently of asynchronous physical sweeping. Permanent delete physically deletes the exact item. Content-free audits are owner-only, logically retained for 90 days, and use per-item native TTL.
- Keep bounded same-word lexical matching for memory. For documentation content, configure the supplied LangGraph Store index through the documented custom async embedding-function path to embed only fragment `content` with local Ollama `embeddinggemma` (768 dimensions and zero keep-alive), pass the query to `BaseStore.asearch`, and preserve Store ranking and scores without custom lexical ranking or reranking. Ontology, reindexing workflows, and unrelated/custom vector infrastructure remain excluded.
- Keep checkpoints as execution state rather than memory.
- Implement authenticated manual owner ingestion in the custom Phase 5 route and Installation Library view for either an explicitly selected browser upload or an explicitly submitted public HTTPS page/PDF. The browser sends only the upload boundary fields for a file, or a bounded HTTPS URL, title, and optional bounded tags for a public source. Auth-first server code obtains the injected Store with `get_store()`, derives all authority/source/identity/routing fields, and returns only document ID/count without auto-linking. Public retrieval uses a trusted bounded downloader with fresh all-global DNS validation and IP-pinned TLS connections on each validated redirect hop, no proxies or automatic redirects, and fixed limits/failures before preserving bytes through the existing opaque upload boundary. This narrow SSRF control does not claim safety for arbitrary networking.
- Persist complete normalized Docling Markdown as deterministic ordered lossless fragments no larger than 1,800 UTF-8 bytes, below deployed `embeddinggemma`'s 2,048-token context, while retaining the 32 KiB Store absolute limit and preserving original source bytes. Librarian public/private/network and Coder artifact production handoffs remain pending and fail closed; isolated candidate-policy mocks are not deployed proof. The completed manual owner public route is not a Librarian handoff.
- Keep persistence and source credentials in trusted infrastructure and out of agent contexts, results, errors, and logs.

## Capabilities

### New Capabilities

- `cross-session-memory`: Identity-bound private memory with bounded records, provenance, immediate delete exclusion, exact seven-day owner restore, permanent purge, and 90-day content-free audits.
- `documentation-retrieval`: Permissioned retrieval and supervisor-mediated ingestion for one canonical installation-wide, provenance-bearing documentation corpus using exact lookup, canonical metadata filtering, or Store-native semantic fragment search, with canonical document tags and bounded thread-scoped document links.

### Modified Capabilities

- None.

## Impact

Eventual implementation may affect trusted Agent Server-side Store adapters, verified-identity authorization, application-owned namespaces, memory lifecycle processing, documentation retrieval/ingestion, authoritative thread state, the narrowly scoped Installation Library and Session Documents UI, supervisor-to-OCR routing, sanitized audits, and tests. It must not add unrelated UI, shared memory, direct specialist communication, MCP, custom vector infrastructure, ontology logic, reindexing workflows, or document/corpus deletion. The documented LangGraph Store index and local semantic document retrieval are the sole documentation-search exception; removing a thread link does not delete its canonical document.
