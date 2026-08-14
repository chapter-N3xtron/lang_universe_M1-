## Purpose

Defines a source-faithful, page-aware corpus contract for Librarian research so exact quotations and future conceptual retrieval remain separately attributable, testable, and independent of LangGraph execution persistence.

## ADDED Requirements

### Requirement: Preserve extraction lineage and page-aware source artifacts

The corpus process SHALL identify `Late_victorian_holocost` as the established source repository/path from the prior repository context and SHALL document its role as the producer or holder of page-aware `pages.jsonl` extraction artifacts. Each imported book SHALL retain links or resolvable references to the originating PDF and the source JSONL record set. The contract SHALL distinguish repository observations from assumptions about files that have not been inspected in the selected repository.

#### Scenario: Source lineage is inspectable
- **WHEN** an imported book is presented to a downstream consumer
- **THEN** the record identifies `Late_victorian_holocost`, the PDF reference, the JSONL reference, and the extraction/OCR provenance without claiming an unverified current filesystem location

#### Scenario: Page boundaries survive import
- **WHEN** a `pages.jsonl` record is imported
- **THEN** its page ordinal and page boundary remain independently addressable, including empty, image-only, or OCR-failed pages where the source artifact records them

### Requirement: Preserve a verbatim PostgreSQL corpus separate from LangGraph Store

The first PostgreSQL corpus layer SHALL preserve source text verbatim, including whitespace or line-boundary policy as explicitly recorded, footnotes, page order, page boundaries, and coordinates when available. It SHALL carry stable book, page, and chunk identifiers, extraction/OCR method and version, source digest or equivalent provenance, and links to the PDF and JSONL. Corpus tables, migrations, and access paths SHALL be separate from LangGraph Store/checkpoint tables and SHALL NOT change existing LangStore semantics, namespaces, keys, or retention behavior.

#### Scenario: Verbatim text is returned
- **WHEN** an exact corpus query selects a page or chunk
- **THEN** the returned text is byte-for-byte or code-point-for-code-point identical to the stored source representation under the declared encoding/normalization policy, and no summary or cleanup is applied

#### Scenario: Missing metadata is explicit
- **WHEN** coordinates, OCR confidence, footnote structure, or another source field is absent
- **THEN** the corpus records absence/unknown explicitly and does not synthesize a value

#### Scenario: LangStore isolation is verified
- **WHEN** the corpus layer is deployed or tested
- **THEN** verification can demonstrate that existing LangGraph Store/checkpoint tables and semantics were not altered, and the corpus can be disabled without making LangGraph persistence unavailable

### Requirement: Define bounded Librarian exact-retrieval tooling

The planning contract SHALL define Librarian-facing exact retrieval as a proposed tool boundary, not an existing API. An exact retrieval request SHALL accept a stable book identifier plus one bounded selector: page ordinal/range, stable page identifier, or a coordinate/region selector when coordinates exist; optional chunk bounds and a maximum result size SHALL be explicit. A response SHALL contain source text, stable identifiers, page ordinals, citation-ready PDF/page provenance, extraction/OCR provenance, source links, and truncation or no-result status. Retrieval SHALL support contiguous page or region results and SHALL preserve source ordering.

#### Scenario: Contiguous page retrieval
- **WHEN** Librarian requests pages 12 through 14 for a known book
- **THEN** the result contains only those pages in ascending source order, preserves page boundaries and footnotes, and cites each page and the originating PDF/JSONL

#### Scenario: Region retrieval without coordinates
- **WHEN** Librarian requests a coordinate region for a page whose source has no coordinates
- **THEN** the tool returns an explicit unsupported/unavailable result rather than guessing, OCRing silently, or substituting a different region

#### Scenario: Bounded response
- **WHEN** a request exceeds configured page, region, or byte limits
- **THEN** the tool returns a deterministic bounded result with an explicit truncation/error status and a continuation selector, if supported by the later implementation

### Requirement: Guard exact retrieval against source transformation

Exact retrieval SHALL not silently alter, summarize, translate, normalize, reorder, deduplicate, merge, or infer source text. Any display-only transformation SHALL be separately labeled and SHALL retain an unmodified exact field. Tool errors, ambiguous selectors, unavailable provenance, and conflicting source versions SHALL be visible to Librarian and downstream citation handling.

#### Scenario: No silent reordering
- **WHEN** stored chunks are returned for multiple pages
- **THEN** their source page/chunk order is retained, and any database ordering needed to achieve it is explicit in the contract

#### Scenario: OCR and extraction versions conflict
- **WHEN** more than one extraction/OCR version exists for a requested source
- **THEN** the response identifies the selected version and provenance, or reports ambiguity requiring an explicit choice; it does not silently mix versions

### Requirement: Reserve semantic retrieval as a distinct future layer

The design SHALL document a future, non-implemented vector-database layer using LangChain's documented PostgreSQL/PGVectorStore integration boundary, including an embedding adapter and retriever boundary. The vector layer SHALL index approved derived representations with links to exact corpus identifiers and provenance; it SHALL never become the authority for verbatim text, page order, citations, or source boundaries. No vector database, embeddings, PGVectorStore integration, retriever, migration, dependency, or runtime behavior is created by this change.

Documented facts SHALL be checked against current official references, including LangChain PGVectorStore documentation (https://docs.langchain.com/oss/python/integrations/vectorstores/pgvector), LangChain retriever concepts (https://python.langchain.com/docs/concepts/retrievers/), LangGraph persistence/store concepts (https://langchain-ai.github.io/langgraph/concepts/persistence/), and PostgreSQL documentation (https://www.postgresql.org/docs/current/). The design SHALL label facts, repository observations, explicit inferences, proposals, and unresolved items rather than presenting proposals as existing APIs.

#### Scenario: Exact and semantic results are distinguishable
- **WHEN** Librarian later queries exact and semantic retrieval in one research turn
- **THEN** each result declares its retrieval mode, exact corpus identifiers/provenance, and whether text is source text or an embedding-derived candidate; semantic results link back to exact retrieval before quotation or citation

#### Scenario: Vector layer is absent
- **WHEN** the future vector layer has not been implemented or is unavailable
- **THEN** exact corpus retrieval remains usable and the system reports semantic retrieval as unavailable rather than falling back silently or fabricating relevance

### Requirement: Apply source-of-truth and staged acceptance rules

The specification SHALL establish that the original PDF and page-aware `pages.jsonl` are the primary source artifacts; PostgreSQL is a provenance-preserving query projection; exact retrieval is authoritative for quotations and page citations; and future vectors are discovery aids only. Acceptance SHALL cover lineage, fidelity, ordering, boundaries, footnotes, optional coordinates, provenance, stable identifiers, source links, isolation from LangStore, bounded tool behavior, and explicit non-implementation of vectors.

#### Scenario: Corpus validation succeeds
- **WHEN** a fixture includes reordered pages, footnotes, coordinates, OCR metadata, and a missing coordinate field
- **THEN** validation detects or preserves each condition, exact round-trip text passes, stable identifiers and links resolve to the declared source records, and page-order assertions pass

#### Scenario: Planning-only boundary is audited
- **WHEN** this change is reviewed before implementation
- **THEN** only OpenSpec planning artifacts are added for this change; no runtime code, database migration, LangGraph Store modification, or vector integration is claimed or present as part of the change
