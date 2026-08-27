# Phase_5_Cross_session_memory_and_documentation_RAG

## Why

Sessions need permissioned continuity without treating execution checkpoints as user memory, and agents need grounded access to an approved documentation corpus without conflating documents with personal memory. This change defines those two durable boundaries before implementation so identity, isolation, provenance, retention, and least-privilege behavior are contractual rather than implicit.

## What Changes

- Define one Agent Server Store-based cross-session memory layer whose application records are addressed through public Store APIs and are never written directly into Agent Server internal PostgreSQL tables.
- Define a separate documentation retrieval-augmented generation corpus with its own tenant, trust-domain, owner, and corpus namespaces, even when it shares the same PostgreSQL deployment.
- Require verified identity, deny-by-default access, personal/work tenant separation, least-privilege server-mediated operations, bounded records/results, provenance, retention, deletion, and auditable access decisions.
- Define initial retrieval as exact-key, metadata-filtered, and lexical retrieval only; do not represent it as vector or semantic search. A vector semantic index is a future extension.
- Keep checkpoints as execution state rather than cross-session memory, and leave ontology/custom knowledge logic for a future change.
- Explicitly defer Librarian ingestion wiring, corpus population, source acquisition, chunking, reindexing, and corpus-deletion implementation.
- Keep credentials in trusted server infrastructure; agents receive capability-scoped operations and results, never database, Store, embedding-provider, or source-system credentials.
- This is planning only. It excludes Coder graph topology, report handoff, MCP, UI behavior, and ingestion implementation.

## Capabilities

### New Capabilities

- `cross-session-memory`: Permissioned, identity-bound durable memory across sessions with strict tenant isolation, provenance, bounded records, lifecycle controls, and explicit read/write/delete rules.
- `documentation-retrieval`: Permissioned retrieval from a distinct documentation corpus using exact, metadata, or lexical matching with provenance and bounded results.

### Modified Capabilities

- None.

## Impact

The eventual implementation will affect trusted Agent Server-side Store adapters, authorization and verified-identity middleware, application-owned namespace conventions, retention/deletion jobs, retrieval services, audit telemetry, and tests. It may use the existing PostgreSQL deployment through supported Agent Server Store interfaces, but it must not write application data into Agent Server internal tables or give agents credentials. No Coder topology, report-handoff, MCP, UI, ingestion, chunking, indexing, reindexing, or corpus-population implementation is authorized by this change.
