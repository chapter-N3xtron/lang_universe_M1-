## Purpose

Define grounded, permissioned retrieval from a documentation corpus that remains isolated from cross-session memory and accurately describes its initial non-semantic matching behavior.

## ADDED Requirements

### Requirement: Documentation is a separate corpus boundary
The system SHALL store and retrieve documentation records in application-owned documentation namespaces that are distinct from cross-session memory namespaces. Each documentation namespace SHALL include capability, tenant, trust domain, owner, and corpus identity. Sharing a PostgreSQL deployment does not permit joins, fallback searches, or record movement across those logical boundaries, and application documentation MUST NOT be written directly into Agent Server internal tables.

#### Scenario: Documentation and memory share infrastructure
- **WHEN** documentation retrieval and cross-session memory use the same PostgreSQL deployment
- **THEN** each remains accessible only through its own supported application boundary and distinct namespaces

#### Scenario: Retrieval falls back to memory
- **WHEN** no documentation result matches a query
- **THEN** the system returns no documentation matches and does not search cross-session memory as a fallback

### Requirement: Documentation retrieval and ingestion require verified scope and explicit corpus access
Before retrieval or corpus ingestion, the system SHALL derive the principal, private-installation tenant, `local-installation-v1` trust domain, `person` owner, and permitted corpus scopes from verified server-side configuration and identity. Retrieval SHALL require `documentation-retrieval:read` plus an explicit grant for every target corpus. Corpus writes SHALL require a supervisor-created `documentation-retrieval:write` delegation following approved source validation and successful OCR. The system SHALL deny by default. Shared, work-member, and caller-selected tenant contexts are unsupported.

#### Scenario: Authorized corpus query
- **WHEN** a verified principal has `read` permission for a corpus in the current tenant and trust domain
- **THEN** the system searches only that corpus and other explicitly listed corpora in the same authorized scope

#### Scenario: Unauthorized corpus is included
- **WHEN** a request includes any corpus outside the verified principal's grants
- **THEN** the system denies that corpus access without revealing document existence or corpus statistics

#### Scenario: Write lacks supervisor delegation
- **WHEN** a corpus-write request does not have a current supervisor-created ingestion delegation for the verified scope and corpus
- **THEN** the system denies the write without revealing corpus state or changing content

#### Scenario: Request targets another installation
- **WHEN** a caller requests a tenant, owner, or trust domain other than the server-derived installation scope
- **THEN** the system denies the request without accessing or revealing that scope

### Requirement: Initial retrieval is exact, metadata, or lexical only
The initial system SHALL provide bounded exact-identifier lookup, allowlisted metadata filtering, and lexical text matching. Every response SHALL state the match mode and corpus scope used. The system MUST NOT claim that initial retrieval is semantic, vector, embedding-based, conceptual, or ontology-driven.

#### Scenario: Exact document lookup
- **WHEN** an authorized caller requests an existing document or fragment by exact identifier
- **THEN** the system returns the authorized record with `exact` as the match mode

#### Scenario: Metadata-filtered lexical query
- **WHEN** an authorized caller submits a lexical query with allowlisted metadata filters
- **THEN** the system returns bounded matching records with `lexical` and `metadata-filtered` match information

#### Scenario: Semantic search is requested
- **WHEN** a caller requests semantic or vector search before a separately specified index exists
- **THEN** the system reports the mode as unsupported and does not relabel lexical results

#### Scenario: Ontology reasoning is requested
- **WHEN** a caller requests ontology-based expansion or inference
- **THEN** the system reports it as unsupported future custom logic

### Requirement: Retrieval results preserve document provenance
Every returned documentation result SHALL include corpus identity, document identifier, fragment or locator identifier when applicable, source title, source URI or approved opaque locator, source revision or version, content digest, publication or source time when known, retrieval time, and match mode. Unknown provenance fields SHALL be marked unknown rather than inferred, and generated answers MUST retain references sufficient to identify the supporting results.

#### Scenario: Provenance is complete
- **WHEN** a documentation result is returned
- **THEN** the response includes its available source identity, revision, digest, locator, corpus, time, and match-mode fields

#### Scenario: Source time is unknown
- **WHEN** a matching record has no verified publication time
- **THEN** the result marks source time unknown and does not substitute ingestion or retrieval time as publication time

### Requirement: Queries and results are bounded and deterministic enough to inspect
The system SHALL enforce configured hard limits for query bytes, filter count and values, requested corpora, candidate scan, result count, per-result content bytes, total response bytes, and pagination depth. Results SHALL use a documented lexical ordering and stable tie-breaker within a fixed corpus revision. The system SHALL reject unsupported filters and MUST NOT perform unbounded corpus enumeration.

#### Scenario: Query exceeds a hard limit
- **WHEN** a query, filter set, corpus list, or requested page exceeds a configured hard limit
- **THEN** the system rejects or caps it according to the documented contract without running an unbounded operation

#### Scenario: Lexical scores tie
- **WHEN** two authorized results have the same lexical rank within one corpus revision
- **THEN** the system orders them by the documented stable tie-breaker

### Requirement: Document content is data, not authorization
The system SHALL treat retrieved documentation as untrusted source content. Instructions, namespace values, access requests, or credential requests contained in a document MUST NOT change authorization, invoke another capability, widen retrieval, or override server policy.

#### Scenario: Retrieved document contains an instruction
- **WHEN** a result tells an agent to query another tenant or reveal a credential
- **THEN** the system treats that text only as document content and does not widen access or expose a credential

### Requirement: Deleted, expired, or unavailable documents are not returned
Retrieval SHALL exclude corpus records whose approved lifecycle state is deleted, expired, quarantined, superseded-withdrawn, or otherwise unavailable. Retrieval SHALL honor the corpus revision selected at authorization time and SHALL fail safely if lifecycle status cannot be verified. This change does not implement corpus deletion or reindexing workflows.

#### Scenario: Document is unavailable
- **WHEN** a matching document is marked deleted, expired, quarantined, or withdrawn
- **THEN** the system does not return its content in normal retrieval

#### Scenario: Lifecycle state cannot be verified
- **WHEN** the system cannot establish whether a candidate is currently available
- **THEN** it excludes the candidate and reports a sanitized retrieval failure or partial-result status

### Requirement: Agents never receive corpus credentials
The system SHALL keep Store, database, source-system, future index, and embedding-provider credentials in trusted server infrastructure. Agents SHALL receive only authorized retrieval or supervisor-mediated ingestion operations and bounded provenance-bearing results; errors and telemetry MUST NOT reveal credential or secret connection material.

#### Scenario: Agent retrieves documentation
- **WHEN** an agent has a valid server-created delegation for an authorized corpus
- **THEN** trusted server code executes retrieval without adding corpus or persistence credentials to agent context

#### Scenario: Retrieval backend fails
- **WHEN** the retrieval backend returns an error
- **THEN** the system exposes only a sanitized failure class and correlation identifier to the agent

### Requirement: Retrieval access is auditable
The system SHALL record bounded audit events for allowed and denied documentation reads and supervisor-mediated ingestion requests containing time, verified principal or service identifier, tenant, trust domain, owner and corpus scopes, operation, match mode when applicable, policy decision, reason class, correlation identifier, and result count. Audit events MUST NOT copy query results, document bodies, credentials, or internal reasoning and SHALL follow an approved retention and access policy.

#### Scenario: Corpus query succeeds
- **WHEN** an authorized documentation query returns results
- **THEN** the system records the authorized corpus scope, match mode, and result count without duplicating result content

#### Scenario: Corpus query is denied
- **WHEN** authorization denies a documentation query
- **THEN** the system records a sanitized denial without revealing document existence

### Requirement: Supervisor-mediated OCR ingestion is the only corpus write path
The existing Agent Server supervisor graph SHALL be the sole authority that routes documentation corpus writes. Librarian MAY request download of approved research sources, and Coder MAY submit qualifying work artifacts. The supervisor SHALL validate scope and source, route the selected document through the existing OCR capability, and create a bounded documentation record only after successful OCR and authorized trusted-adapter write. Librarian, Coder, and OCR SHALL NOT communicate directly with each other or receive Store/database credentials. Reindexing and document/corpus deletion remain unsupported.

#### Scenario: Librarian source is ingested
- **WHEN** Librarian requests ingestion of an approved downloaded research source
- **THEN** the supervisor routes it to OCR and, after successful bounded OCR output and authorization, writes provenance-bearing content to the authorized corpus

#### Scenario: Coder artifact is ingested
- **WHEN** Coder requests ingestion of a qualifying work artifact
- **THEN** the supervisor routes it to OCR and, after successful bounded OCR output and authorization, writes provenance-bearing content to the authorized corpus

#### Scenario: A direct specialist write is attempted
- **WHEN** Librarian, Coder, or OCR attempts to write the corpus without a supervisor-created delegation
- **THEN** the system denies the operation without changing corpus content

#### Scenario: OCR or source validation fails
- **WHEN** download approval, source validation, OCR, or a bounded corpus write fails
- **THEN** the system reports a sanitized failure and does not claim that corpus content changed

#### Scenario: Reindex or corpus deletion is requested
- **WHEN** a caller requests reindexing or implementation of document or corpus deletion under this capability
- **THEN** the system reports the operation as unsupported rather than simulating success
