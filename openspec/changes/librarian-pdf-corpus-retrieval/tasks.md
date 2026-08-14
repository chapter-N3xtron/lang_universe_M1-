## 1. Source verification and contract

- [ ] 1.1 Verify the established `Late_victorian_holocost` repository/path and inspect representative PDFs and `pages.jsonl` records; document the actual fields, page keys, encoding, and extraction/OCR provenance without guessing.
- [ ] 1.2 Resolve and record the source-of-truth policy for PDF, JSONL, PostgreSQL projection, extraction versions, digests, editions, logical labels, physical ordinals, and unpaginated pages.
- [ ] 1.3 Define fixture cases covering page order, page boundaries, footnotes, coordinates, OCR metadata, missing fields, empty/image-only pages, duplicate imports, and extraction-version conflicts.

## 2. Isolated PostgreSQL exact corpus

- [ ] 2.1 Design and review a corpus-owned PostgreSQL namespace/schema and stable book/page/chunk identifiers; inventory existing LangGraph Store/checkpoint/session tables before any migration is proposed.
- [ ] 2.2 Define the source-preserving representation, encoding/normalization policy, optional coordinate model, provenance fields, source links, digests, and deterministic chunk boundaries.
- [ ] 2.3 Implement a read-only/fixture importer only after approval, with idempotent version handling and explicit missing metadata; verify it does not write LangStore or checkpoint tables.
- [ ] 2.4 Add round-trip, page-boundary, footnote, ordering, provenance, source-link, duplicate, and extraction-version tests, including reordered database insertion fixtures.

## 3. Librarian exact retrieval boundary

- [ ] 3.1 Define the exact retrieval tool contract with bounded book/page/chunk/coordinate selectors, limits, errors, no-result behavior, and contiguous retrieval semantics without claiming an existing API.
- [ ] 3.2 Implement read-only exact retrieval against the corpus with explicit source ordering, preserved exact text, page boundaries, stable identifiers, and citation-ready PDF/page/JSONL provenance.
- [ ] 3.3 Add safeguards and tests proving no silent summarization, translation, normalization, deduplication, merging, inference, or reordering; make unsupported coordinates and ambiguous extraction versions explicit.
- [ ] 3.4 Add response tests for truncation/continuation behavior, unavailable provenance, malformed selectors, and deterministic citations.

## 4. Future semantic retrieval (separate follow-up)

- [ ] 4.1 Confirm current official LangChain PGVectorStore, retriever, embedding, and PostgreSQL extension documentation at implementation time; record verified version/API facts separately from proposals.
- [ ] 4.2 Propose and approve an embedding adapter boundary, approved derived fields/redaction policy, embedding version metadata, refresh behavior, and links from vector candidates to exact corpus records.
- [ ] 4.3 Implement PGVectorStore/vector retrieval only in a separate approved follow-up, keeping vector results labeled as semantic candidates and resolving quotations through exact retrieval.
- [ ] 4.4 Test vector absence, stale indexes, semantic misses, and exact/semantic mixed queries so semantic retrieval never silently replaces exact retrieval.

## 5. Acceptance, isolation, and rollout

- [ ] 5.1 Run the complete acceptance matrix from the spec against fixtures and a controlled PostgreSQL environment, including verbatim fidelity, page order, boundaries, footnotes, coordinates, provenance, identifiers, and links.
- [ ] 5.2 Verify no existing LangGraph Store/checkpoint table, namespace, key, session semantic, or persistence behavior changes; document the inventory and rollback evidence.
- [ ] 5.3 Review security, access control, retention, source-link availability, OCR disclosure, and embedding data-minimization decisions before production ingestion.
- [ ] 5.4 Roll out in stages: source verification, isolated exact corpus, read-only Librarian retrieval, isolation audit, then (only under a separate approval) optional semantic indexing; document rollback for each stage.
