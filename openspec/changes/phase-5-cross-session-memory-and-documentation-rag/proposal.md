# Phase 5: Cross-session memory and documentation RAG

## Why

Sessions need permissioned continuity without treating checkpoints as user memory, and agents need grounded access to an approved documentation corpus without conflating documents with personal memory. This change fixes those boundaries for private, one-person installations.

## What Changes

- Define cross-session memory through public Agent Server Store APIs in application-owned namespaces; application code never selects or writes Agent Server internal PostgreSQL tables.
- Define a logically separate documentation corpus with independent namespaces, provenance, authorization, and lifecycle enforcement.
- Fix the deployment model to one person and one separate database per installation, with a server-generated opaque tenant ID, trust domain `local-installation-v1`, and server-configured `person` owner ID. Shared/work memory and work-member policy are excluded.
- Grant the owner memory read, explicit write, exact delete, seven-day restore, permanent delete, and owner-only content-free audit access. Jasper, Coder, and Librarian may receive bounded memory delegations; OCR may not. Jasper, Coder, Librarian, and OCR may receive documentation-read delegations.
- Fix memory kinds and bounds: `user preferences`, `user-provided facts`, `project decisions`, `task outcomes`, and `reusable instructions`; 15 MB per kind; 32 KB content; 8 KB/32 metadata fields; 4 KB query; 1000 authorized candidates; 20 results; 256 KB response; and 10 records per write batch.
- Retain memory until owner deletion or a kind limit requires an explicit owner decision; never evict automatically. Deletion excludes content from normal reads immediately, permits exact owner restore for exactly seven days, and then permanently purges it. Owner permanent delete purges immediately. Content-free audits are owner-only and retained for 90 days.
- Define bounded same-word lexical matching with deterministic ranking and no vector, semantic, ontology, or inference claim.
- Keep checkpoints as execution state rather than memory.
- Authorize documentation ingestion only through the existing supervisor: Librarian may request approved research sources and Coder may submit qualifying artifacts; the supervisor routes accepted documents through existing OCR and then a bounded trusted corpus write. Specialists never communicate directly.
- Approve Librarian sources as public HTTPS pages, public PDFs, owner-uploaded documents, and explicitly source-approved private-workspace documents. Approve Coder artifacts as explicitly selected Markdown, plain text, PDF, or DOCX reports that pass sensitive-data checks. Production starts empty; tests use synthetic fixtures.
- Keep persistence and source credentials in trusted infrastructure and out of agent contexts, results, errors, and logs.

## Capabilities

### New Capabilities

- `cross-session-memory`: Identity-bound private memory with bounded records, provenance, immediate delete exclusion, exact seven-day owner restore, permanent purge, and 90-day content-free audits.
- `documentation-retrieval`: Permissioned retrieval and supervisor-mediated ingestion for a distinct, provenance-bearing documentation corpus using exact, metadata, or lexical matching.

### Modified Capabilities

- None.

## Impact

Eventual implementation may affect trusted Agent Server-side Store adapters, verified-identity authorization, application-owned namespaces, memory lifecycle processing, documentation retrieval/ingestion, supervisor-to-OCR routing, sanitized audits, and tests. It must not add shared memory, direct specialist communication, MCP, vector indexing, semantic claims, ontology logic, reindexing, or document/corpus deletion.
