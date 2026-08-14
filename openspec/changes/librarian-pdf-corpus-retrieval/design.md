## Context

See `proposal.md` and `specs/librarian-pdf-corpus-retrieval/spec.md` for motivation and behavior requirements.

**Repository observation (selected workspace):** `backend/PERSISTENCE.md` states that LangGraph checkpoints are authoritative for thread execution, LangGraph Store is authoritative for session manifests and related references, and application-owned PostgreSQL `session_catalog` is a rebuildable query projection. `openspec/TERMINOLOGY.md` likewise separates repository binding from LangGraph runtime persistence. No current PDF corpus, `pages.jsonl` importer, Librarian exact-corpus tool, or PGVector integration was established by the inspected OpenSpec files; this change therefore does not claim one exists.

**Supplied prior-repository context:** `Late_victorian_holocost` is the established repository/path name and is the source of page-aware `pages.jsonl` extraction artifacts. Its current location and exact JSONL schema remain to be verified during implementation.

**Documented-fact boundary:** Official LangChain documentation describes vector stores/retrievers and a PostgreSQL PGVectorStore integration; PostgreSQL documents ordered query behavior, data types, transactions, and extension/database concerns; LangGraph documents checkpoint/store persistence concepts. These references inform boundaries, not an assertion that this repository has installed or configured any of them.

**Context/reference note — dedicated conversation thread:** This conversation is the dedicated thread for the Late Victorian Holocausts book, the source PDF, the PDF extraction pipeline, and the Librarian/PostgreSQL retrieval design. The actual thread ID is unavailable from the repository/tool context and should be populated by the host system if exposed.

## Goals / Non-Goals

**Goals:**

- Define an appendable, provenance-first path from PDF and page-aware JSONL to a PostgreSQL read/query projection.
- Make exact retrieval deterministic, bounded, source-ordered, citation-ready, and visibly distinct from semantic candidate retrieval.
- Preserve an integration seam for a future LangChain PGVectorStore/embedding adapter without coupling it to exact-text authority.
- Provide implementation sequencing and review gates that can prove LangStore isolation.

**Non-Goals:**

- Implementing ingestion, schemas, SQL, migrations, runtime tools, embeddings, vector indexes, retrievers, or UI behavior.
- Reconstructing a PDF or inventing missing page/coordinate/OCR data.
- Changing Agent Server checkpoints, LangGraph Store tables/namespaces/keys, `workspace_id`, session ownership, or existing persistence semantics.
- Treating semantic similarity as evidence, exact quotation, or a substitute for page-aware source retrieval.

## Decisions

### 1. Keep three evidence layers explicit

The source layer is the original PDF plus its page-aware JSONL extraction records. The exact corpus is a PostgreSQL projection that copies source content and provenance for bounded queries. The future semantic layer stores embeddings/derived searchable representations and links back to exact records. A result must state which layer produced it.

**Alternative considered:** make PostgreSQL or the vector index the only source of truth. Rejected because it would erase extraction lineage or make approximate retrieval responsible for quotation fidelity.

### 2. Use stable composite identity with immutable source lineage

The implementation should derive deterministic identifiers from a declared book identity, source page ordinal/source page key, extraction version, and deterministic chunk boundary. It must document collision/version behavior before loading data. A page/chunk identity must not be silently reused for a different extraction version. Source links and digests are metadata, not substitutes for preserving text.

**Alternative considered:** database-generated IDs alone. Rejected because they are not sufficient for reproducible citations or idempotent re-imports.

### 3. Store exact text and metadata separately from retrieval presentation

The exact record contains the declared source representation and metadata (page order, boundaries, footnotes, optional coordinates, OCR/extraction provenance). A later presentation layer may add highlighting or labels only in separate fields. No SQL result order is assumed: retrieval must request an explicit source-order key and test it.

**Alternative considered:** normalize whitespace and merge footnotes during ingest. Rejected because it changes the evidence and makes word-for-word citation impossible.

### 4. Define logical tool contracts before implementation names

The spec describes an exact retrieval operation by inputs, bounded selectors, outputs, status, and citation behavior. It intentionally does not name or claim a Python function, HTTP route, LangChain tool, or existing Librarian API. A later implementation can expose one or more adapters while retaining the same observable contract.

### 5. Make semantic retrieval opt-in and subordinate to exact retrieval

A later embedding adapter will accept only approved derived text/metadata and return candidate IDs plus relevance metadata. A future LangChain `PGVectorStore` adapter may provide a retriever boundary, but it must resolve candidates to the exact corpus before quotation and must preserve mode/provenance labels. Exact and semantic calls should be separately observable so vector availability cannot silently change exact answers.

**Alternative considered:** one hybrid endpoint with implicit fallback. Rejected because it obscures evidence class and can turn a semantic miss into an untraceable exact result.

### 6. Isolate database ownership

Any future corpus schema must be application-owned under a newly agreed namespace and must have explicit ownership, migration, backup, and rollback policy. It must not reuse or alter LangStore/checkpoint tables. The first implementation gate is a schema/table inventory and read-only compatibility test against the existing persistence setup; the final gate verifies no Store/checkpoint semantic changes.

## Risks / Trade-offs

- **[Risk] Prior repository path or JSONL fields differ from recollection** → Verify `Late_victorian_holocost` and inspect representative PDF/JSONL fixtures before implementation; record discrepancies as unresolved rather than guessing.
- **[Risk] OCR can contain errors while still being verbatim extracted output** → Preserve OCR method/version/confidence where available and label extraction quality; do not silently correct text.
- **[Risk] Coordinates vary by extractor** → Treat coordinates as optional, versioned source metadata and make region retrieval unavailable when absent.
- **[Risk] Database ordering is nondeterministic without an explicit key** → Require page ordinal plus deterministic chunk/region ordering in every exact query and test reordered insertion fixtures.
- **[Risk] Vectorized text leaks or loses provenance** → Apply an approved-field/redaction policy before embedding, retain exact IDs in vector metadata, and never cite a vector document without exact resolution.
- **[Risk] Corpus tables are confused with LangStore** → Use separate ownership/schema documentation, migration review, table inventory checks, and a no-write-to-Store test harness.
- **[Risk] Official libraries evolve** → Pin and verify the future adapter against current official LangChain/PostgreSQL documentation at implementation time; this planning artifact does not freeze an unverified API signature.

## Migration Plan

This change has no migration. A future implementation should proceed in stages: (1) verify source fixtures and establish source-of-truth/retention decisions; (2) design and review an isolated PostgreSQL schema and read-only importer; (3) load a fixture corpus and run fidelity/order/provenance tests; (4) expose exact retrieval in a read-only Librarian tool boundary; (5) audit LangStore/checkpoint isolation; and only then (6) separately propose and implement optional embeddings/PGVectorStore and semantic retrieval. Rollback before semantic work is deletion or disablement of the corpus projection under its own approved policy; rollback must not touch LangGraph persistence. Semantic rollback disables the vector adapter/index while exact retrieval remains available.

## Open Questions

- What is the verified current filesystem/remote URI and exact schema of `Late_victorian_holocost/pages.jsonl`?
- Which text encoding and normalization policy constitutes “verbatim” for storage and returned payloads?
- What stable book identifier and source digest policy should govern re-extraction and duplicate editions?
- How are PDF logical page labels mapped to physical page ordinals, and how are inserts/unpaginated pages represented?
- Which coordinate model and region selector are supportable across the chosen extraction tools?
- Which OCR confidence/provenance fields are available and approved for citation display?
- What exact PostgreSQL schema/ownership namespace and access controls will be approved without touching existing LangStore tables?
- Which text/metadata fields are approved for future embedding, and which embedding model/version and refresh policy will be selected?
- Should a future Librarian response return a continuation token, hard failure, or both when a bound is exceeded?

## References

- LangChain PGVectorStore: https://docs.langchain.com/oss/python/integrations/vectorstores/pgvector
- LangChain retrievers: https://python.langchain.com/docs/concepts/retrievers/
- LangGraph persistence concepts: https://langchain-ai.github.io/langgraph/concepts/persistence/
- PostgreSQL current documentation: https://www.postgresql.org/docs/current/
