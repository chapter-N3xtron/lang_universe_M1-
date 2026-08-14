## Why

The Librarian agent needs a source-faithful foundation for answering page-specific questions about the Holocaust corpus without conflating extracted evidence with conversational state or semantic guesses. This change records the staged design for carrying page-aware artifacts from the established `Late_victorian_holocost` source repository into a separate PostgreSQL exact-text corpus, while reserving—but not implementing—a future vector layer.

## What Changes

- Document the initial PDF extraction boundary and the `pages.jsonl` artifact contract, including page order, page boundaries, and source links.
- Define a first PostgreSQL corpus layer that preserves verbatim extracted/OCR text, footnotes, coordinates when present, provenance, stable book/page/chunk identifiers, and original PDF/JSONL references.
- Specify Librarian exact-corpus tools for bounded, contiguous page/region retrieval with explicit citations and safeguards against transformation, summarization, or reordering.
- Document a future, explicitly non-implemented PGVector/vector-database boundary for conceptual retrieval and a LangChain `PGVectorStore` adapter/retriever boundary; keep semantic and exact retrieval visibly distinct.
- Establish source-of-truth rules, acceptance criteria, unresolved decisions, and a staged implementation plan.
- Make no runtime code, migrations, dependency changes, LangGraph Store changes, checkpoint changes, or edits to existing files outside this change.

## Capabilities

### New Capabilities

- `librarian-pdf-corpus-retrieval`: Source-faithful PDF extraction lineage, PostgreSQL exact corpus, Librarian retrieval boundaries, and future semantic-retrieval separation.

### Modified Capabilities

- None.

## Impact

This is a planning/specification change only. It affects future corpus ingestion, PostgreSQL schema/query tooling, Librarian tool contracts, citation UX, and a possible later LangChain PGVectorStore integration. It deliberately does not claim that any of these APIs, tables, migrations, tools, or vector indexes currently exist, and it must not alter LangGraph Store/checkpoint tables or semantics.
