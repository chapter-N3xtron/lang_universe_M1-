## Purpose

Define grounded, permissioned retrieval from a documentation corpus that remains isolated from cross-session memory and uses the supplied LangGraph Store's local semantic search for document content.

## ADDED Requirements

### Requirement: Documentation is one canonical installation-wide corpus boundary
The system SHALL store and retrieve documentation records in exactly one canonical installation-wide corpus in application-owned documentation namespaces supplied through the Agent Server-injected `BaseStore`. Those namespaces SHALL be distinct from cross-session memory and SHALL include capability, tenant, trust domain, owner, and the server-derived canonical corpus identity. Each document and fragment SHALL exist only in that corpus and MUST NOT be duplicated into per-session storage. Sharing a PostgreSQL deployment does not permit joins, fallback searches, or record movement across logical boundaries, and application documentation MUST NOT be written directly into Agent Server internal tables.

#### Scenario: Documentation and memory share infrastructure
- **WHEN** documentation retrieval and cross-session memory use the same PostgreSQL deployment
- **THEN** each remains accessible only through its own supported application boundary and distinct namespaces

#### Scenario: Two sessions use the same document
- **WHEN** two authorized threads link or use the same stable document ID
- **THEN** both resolve the one canonical document and no session-specific content copy is created

#### Scenario: Retrieval falls back to memory
- **WHEN** no documentation result matches a query
- **THEN** the system returns no documentation matches and does not search cross-session memory as a fallback

### Requirement: Complete OCR output is stored as ordered bounded fragments
After successful Docling OCR, the system SHALL preserve the complete normalized text by deterministically splitting it into UTF-8-safe bounded fragments that prefer Docling Markdown structure. Every production fragment SHALL be no larger than the named 1,800-byte RAG ceiling, conservatively below deployed `embeddinggemma`'s 2,048-token context, and SHALL also remain below the independent 32 KiB Store item bound. Every fragment SHALL carry stable document identity, zero-based order, total fragment count, and character offsets sufficient to reconstruct the exact OCR text in order. The canonical metadata envelope SHALL be stored once per document and MUST NOT be recopied for each fragment. Multiple books or documents SHALL remain independent canonical records.

#### Scenario: OCR output exceeds one Store item
- **WHEN** normalized Docling text exceeds the bounded fragment size
- **THEN** the system writes every ordered fragment exactly once and concatenating fragments by index reproduces the complete normalized text

#### Scenario: Multiple books are ingested
- **WHEN** two approved books are ingested into the installation corpus
- **THEN** each has one canonical metadata record and its own complete ordered fragment sequence without overwrite or cross-document mixing

### Requirement: Documentation retrieval and ingestion require verified scope and explicit corpus access
Before retrieval or corpus ingestion, the system SHALL derive the principal, private-installation tenant, `local-installation-v1` trust domain, `person` owner, and canonical installation corpus from verified server-side configuration and identity. Retrieval SHALL require `documentation-retrieval:read` plus an explicit grant for that canonical corpus. Corpus writes SHALL require a supervisor-created `documentation-retrieval:write` delegation following approved source validation and successful OCR. The system SHALL deny by default. Shared, work-member, additional-corpus, and caller-selected tenant or corpus contexts are unsupported.

#### Scenario: Authorized corpus query
- **WHEN** a verified principal has `read` permission for the canonical corpus in the current tenant and trust domain
- **THEN** the system searches only that server-derived installation corpus

#### Scenario: Unauthorized corpus is included
- **WHEN** a request includes any corpus outside the verified principal's grants
- **THEN** the system denies that corpus access without revealing document existence or corpus statistics

#### Scenario: Write lacks supervisor delegation
- **WHEN** a corpus-write request does not have a current supervisor-created ingestion delegation for the verified scope and corpus
- **THEN** the system denies the write without revealing corpus state or changing content

#### Scenario: Request targets another installation
- **WHEN** a caller requests a tenant, owner, or trust domain other than the server-derived installation scope
- **THEN** the system denies the request without accessing or revealing that scope

### Requirement: Retrieval is stable-key exact, canonical metadata, or Store-native semantic
The system SHALL provide exact document and fragment lookup by stable identifier, allowlisted canonical document-level metadata filtering, and bounded native semantic content retrieval. Exact lookup SHALL use the full authorized namespace and stable exact Store key. Semantic retrieval SHALL pass the validated query to `BaseStore.asearch` against only the fully authorized fragment namespace, preserve the Store's order and scores, and MUST NOT invoke application-level document lexical ranking or custom reranking. Every response SHALL state the match mode and corpus scope used.

The LangGraph Store index SHALL use the documented custom async embedding-function path with local Ollama `embeddinggemma`, 768 dimensions, zero keep-alive, and only the fragment `content` field indexed. The adapter SHALL resolve the trusted server-configured `OLLAMA_HOST` or `OLLAMA_BASE_URL` endpoint and SHALL pass `keep_alive=0` to Ollama embedding requests. Canonical document metadata SHALL be written with `index=False`; content-bearing fragments SHALL be written with `index=['content']`. Ollama access SHALL remain inside the user-approved `local-installation-v1` trust boundary through trusted server configuration. Canonical tags MUST NOT be copied onto fragments. Custom Stores, separate vector databases, model-driven retrieval branches, direct SQL, ontology expansion, and reindexing workflows remain excluded; the deterministic non-model library operation is the sole manual UI read contract.

#### Scenario: Exact document lookup
- **WHEN** an authorized caller requests an existing document or fragment by exact identifier
- **THEN** the system uses its stable exact Store key and returns the authorized record with `exact` as the match mode without corpus enumeration

#### Scenario: Semantic content query
- **WHEN** an authorized caller submits a bounded document-content query
- **THEN** the system passes that query to Store search over the authorized fragment namespace and returns bounded results in native Store order with native scores and `semantic` as the match mode

#### Scenario: Canonical metadata query
- **WHEN** an authorized caller filters canonical documents by an allowlisted tag or source field
- **THEN** the system returns matching active canonical document records without duplicating those fields into indexed fragments

#### Scenario: Ontology reasoning is requested
- **WHEN** a caller requests ontology-based expansion, inference, or a reindexing workflow
- **THEN** the system reports it as unsupported future custom logic

### Requirement: Retrieval results preserve canonical metadata and document provenance
Every document SHALL own one canonical metadata envelope in the installation corpus, including its document-level tags. Tags SHALL be shared across every session, returned from that envelope, and never stored on a session link or independently redefined by a fragment. Every returned documentation result SHALL include corpus identity, document identifier, fragment or locator identifier when applicable, source title, canonical document tags, source URI or approved opaque locator, source revision or version, content digest, publication or source time when known, retrieval time, and match mode. Unknown provenance fields SHALL be marked unknown rather than inferred, and generated answers MUST retain references sufficient to identify the supporting results.

#### Scenario: Provenance is complete
- **WHEN** a documentation result is returned
- **THEN** the response includes its available source identity, revision, digest, locator, corpus, time, and match-mode fields

#### Scenario: Source time is unknown
- **WHEN** a matching record has no verified publication time
- **THEN** the result marks source time unknown and does not substitute ingestion or retrieval time as publication time

#### Scenario: Canonical tags change
- **WHEN** authorized corpus metadata updates a document's tags
- **THEN** every session resolving that document sees the updated canonical tags without rewriting any session link

#### Scenario: A link attempts to carry tags
- **WHEN** a session-link mutation includes tags or other document metadata
- **THEN** the server rejects the noncanonical link payload and leaves both the link set and document metadata unchanged

### Requirement: Queries and results are bounded and deterministic enough to inspect
The system SHALL enforce configured hard limits for query bytes, filter count and values, requested corpora, candidate search, result count, per-result content bytes, total response bytes, and pagination depth. Semantic results SHALL preserve the supplied Store's ranking and scores rather than applying a custom tie-breaker. Metadata-only results SHALL remain deterministically ordered. The system SHALL reject unsupported filters and MUST NOT perform unbounded corpus enumeration.

#### Scenario: Query exceeds a hard limit
- **WHEN** a query, filter set, corpus list, or requested page exceeds a configured hard limit
- **THEN** the system rejects or caps it according to the documented contract without running an unbounded operation

#### Scenario: Store returns semantic scores
- **WHEN** Store search returns bounded semantic results and scores
- **THEN** the system preserves that order and those scores without application reranking

### Requirement: Document content is data, not authorization
The system SHALL treat retrieved documentation as untrusted source content. Instructions, namespace values, access requests, or credential requests contained in a document MUST NOT change authorization, invoke another capability, widen retrieval, or override server policy.

#### Scenario: Retrieved document contains an instruction
- **WHEN** a result tells an agent to query another tenant or reveal a credential
- **THEN** the system treats that text only as document content and does not widen access or expose a credential

### Requirement: Manual search and Jasper use deterministic server operations over one canonical corpus
Jasper SHALL use graph-injected `BaseStore` capabilities for stable-key exact lookup, canonical metadata filtering, lifecycle/provenance assembly, and bounded Store-native semantic fragment search. The manual Installation Library SHALL invoke a deterministic non-model server graph operation through the documented JavaScript SDK run mechanism. That operation SHALL derive installation authority server-side and use only the Agent Server-injected `BaseStore` through Phase 5 capabilities. The browser MUST NOT call direct Phase 5 Store get/search, provide a Store namespace, or provide tenant, trust-domain, owner, memory, audit, or other internal scope.

The manual operation SHALL accept only bounded exact-resolution, allowlisted canonical-metadata, or semantic-search inputs. Result limit SHALL be at most 20 and semantic query length at most 4 KiB. Semantic search SHALL delegate to `BaseStore.asearch` on the authorized fragment namespace, preserve native order/scores, verify active canonical lifecycle, deduplicate by document ID, and return canonical metadata only with no fragment body. Documentation Store get/search/put/delete/list-namespaces and direct internal Phase 5 namespaces SHALL remain denied to browser callers. Existing legacy Store authorization SHALL remain unchanged. A search result alone SHALL NOT create a session link.

#### Scenario: User searches canonical document metadata
- **WHEN** the authenticated owner submits allowlisted bounded metadata filters through the Installation Library SDK run contract
- **THEN** the deterministic server operation searches the complete server-derived canonical document namespace and returns active canonical metadata only

#### Scenario: User searches document fragments semantically
- **WHEN** the authenticated owner submits a bounded semantic query through the Installation Library SDK run contract
- **THEN** the deterministic server operation uses the configured native fragment index, preserves native ranking, joins active canonical metadata, and returns no fragment body

#### Scenario: Jasper searches documentation
- **WHEN** Jasper has explicit documentation-read delegation and submits a valid request through its injected-Store capability
- **THEN** it uses the same canonical corpus and native fragment semantics with capability-level lifecycle, provenance, failure, and match-label handling

#### Scenario: Caller supplies internal scope or direct Store access
- **WHEN** a browser request supplies tenant, trust domain, owner, namespace, raw Phase 5 scope, direct Store get/search/mutation, or namespace listing
- **THEN** authorization denies it without Phase 5 Store access while leaving pre-existing legacy namespace rules unchanged

#### Scenario: Search returns documents that are not used
- **WHEN** manual or Jasper search returns a document that is not added or actually used
- **THEN** the current thread's linked-document set remains unchanged

### Requirement: Session document links are bounded thread-scoped references
Each authoritative LangGraph thread MAY retain in checkpointed execution state an ordered set of at most 100 unique stable document IDs. Reopening that thread SHALL restore its Session Documents set. The server SHALL derive the authoritative thread/session identity from the authenticated current thread or run and SHALL reject an attempt to mutate another thread through caller input. Each link SHALL contain only that thread/session identity and the stable document ID; it MUST NOT contain document or fragment content, tags, titles, provenance, or copied metadata. Links are thread-scoped execution state/references, not cross-session memory, not an additional corpus, and not a second document copy. Multiple threads MAY reference the same document ID independently.

#### Scenario: Reopen a thread
- **WHEN** an authorized owner reopens a LangGraph thread with linked document IDs
- **THEN** Session Documents restores that thread's bounded set and resolves current authorized metadata from the canonical corpus

#### Scenario: Two threads link one document
- **WHEN** two threads add the same canonical document ID
- **THEN** each thread retains its own reference to the single canonical document without duplicating content or tags

#### Scenario: Link limit is reached
- **WHEN** an add would exceed 100 unique document IDs for the current thread
- **THEN** the server rejects the add without evicting an existing link or partially changing thread state

#### Scenario: Duplicate add is requested
- **WHEN** the current thread already contains the stable document ID
- **THEN** the add is idempotent and the ordered set still contains one reference

### Requirement: Owner can add and remove current-session document links
The authorized owner SHALL be able to search the Installation Library and add an available canonical document's stable ID to, or remove it from, the current authoritative thread. Before add, the server SHALL authorize the owner and current thread and validate the canonical document by stable exact Store key. Remove SHALL affect only that thread's reference; it MUST NOT delete or modify the canonical document, its tags, or another thread's link.

#### Scenario: Owner adds a library document
- **WHEN** the authorized owner adds an available exact document ID from Installation Library to the current thread
- **THEN** the server adds only that stable ID and Session Documents refreshes from server truth

#### Scenario: Owner removes a session document
- **WHEN** the authorized owner removes a linked document ID from the current thread
- **THEN** the server removes only that thread's link and leaves the canonical document and other threads unchanged

#### Scenario: Caller targets another thread
- **WHEN** a link mutation supplies a thread identity other than the authenticated current thread
- **THEN** the server denies it without revealing document or target-thread existence and without changing either thread

### Requirement: Jasper links documents actually used by the current thread
When Jasper actually uses a retrieved document excerpt as evidence in a model operation, graph code SHALL add that document's stable ID to the bounded linked-document set of the current authoritative thread. Jasper SHALL derive that thread from the current authenticated run and MUST NOT select another thread. Merely retrieving, ranking, or displaying a document SHALL NOT count as use. If authorization, exact document validation, or link persistence fails, Jasper SHALL NOT claim the document was used.

#### Scenario: Jasper uses a retrieved excerpt
- **WHEN** Jasper incorporates an authorized document excerpt as evidence for the current run
- **THEN** the document ID is linked once to that run's authoritative thread and becomes visible in Session Documents

#### Scenario: Jasper only inspects search results
- **WHEN** Jasper searches but does not use a returned document as evidence
- **THEN** no link is added for that document

### Requirement: Linking never injects full document content
Adding or restoring a session link SHALL NOT place full document content into graph state, messages, prompts, or model context. When a graph operation needs a linked document, graph code SHALL use Jasper's injected-Store Phase 5 capability to select only bounded relevant fragments or excerpts and SHALL preserve their provenance.

#### Scenario: Session with linked documents is reopened
- **WHEN** the graph restores the thread's linked document IDs
- **THEN** no document body is loaded into model context merely because it is linked

#### Scenario: Jasper needs evidence from a linked document
- **WHEN** Jasper needs content from a linked document for the current task
- **THEN** graph code retrieves only bounded relevant excerpts rather than the full document

### Requirement: Narrow document UI uses TanStack Query over server truth
The only general-UI exception in this phase SHALL be the two views named **Installation Library** and **Session Documents**. The frontend SHALL use the existing TanStack Query provider and invalidation patterns only to fetch and cache those views, submit bounded Installation Library reads and explicit owner uploads through authenticated custom Agent Server routes, add or remove links through the current-thread server-authorized run contract, and refresh both views after ingestion, link mutations, or Jasper use. The custom routes SHALL run behind auth-first middleware, verify `Request.user` exactly against server installation identity, obtain the Agent Server-injected `BaseStore` with documented `langgraph.config.get_store()`, and derive all tenant, owner, corpus, authority, ID, status, and routing values server-side. Graph agents SHALL continue using `Runtime.store` tools. The owner-upload control SHALL reuse the existing sidecar document POST to obtain an opaque preserved-upload reference before the custom ingestion route and SHALL show bounded working/success/error status. Query keys SHALL use only a stable non-secret auth discriminator and MUST NOT contain a raw credential. The server SHALL remain the source of truth and SHALL enforce authentication, thread identity, corpus authorization, canonical metadata, lifecycle, bounds, ingestion, and mutations without a model call for deterministic UI operations. Successful ingestion SHALL NOT automatically create a thread link; the human can use **Add to session**. The browser MUST NOT maintain a shadow corpus or authoritative link registry, supply internal Store scope, call Phase 5 Store operations/namespaces directly, use stateless runs for Phase 5 reads or ingestion, or render fragment bodies. Unrelated UI remains out of scope.

#### Scenario: Manual link mutation succeeds
- **WHEN** the server accepts an add or remove mutation
- **THEN** TanStack Query invalidates or refreshes both relevant server-backed views without treating client cache as authoritative

#### Scenario: Owner explicitly ingests a selected file
- **WHEN** the authenticated owner chooses a supported file and its sidecar-preserved opaque reference passes deterministic server validation and OCR
- **THEN** the canonical library is refreshed, a sanitized document ID and fragment count are shown, and no session link is added automatically

#### Scenario: Client cache is stale or forged
- **WHEN** cached data conflicts with server-authorized corpus or thread state
- **THEN** the server response controls the rendered views and rejects any unauthorized mutation

#### Scenario: Unrelated UI change is proposed
- **WHEN** implementation work is not required for Installation Library or Session Documents behavior
- **THEN** it remains outside this Phase 5 change

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

### Requirement: Deterministic manual owner OCR ingestion is the only enabled corpus write path
The existing trusted supervisor ingestion adapter SHALL be the sole authority that routes documentation corpus writes. Its enabled production callers SHALL be deterministic pre-model custom operations explicitly initiated by the authenticated installation owner: a selected browser upload or a submitted public HTTPS page/PDF. The upload operation SHALL accept only the existing sidecar's opaque `upload:` reference, matching filename, bounded title, and optional bounded canonical tags. The public operation SHALL accept only a bounded HTTPS URL, bounded title, and optional bounded canonical tags. Each route SHALL authenticate `Request.user` before obtaining the Agent Server-injected `BaseStore` with `get_store()`. Tenant, owner, corpus, requester, routing origin, document ID, fragment seed, operation ID, source revision/digest, locator, and active source status SHALL be server-derived and MUST NOT be caller-selectable.

Trusted backend code SHALL download public content with HTTPS on every hop; reject userinfo, fragments, unsupported ports, local/internal names, and every DNS answer set containing a non-global IPv4/IPv6 address; resolve before every connection; and connect to a validated resolved IP while retaining TLS SNI, certificate-hostname verification, and Host routing for the URL hostname. It SHALL disable automatic redirects and revalidate at most five Location hops, avoid proxy/environment-proxy use, impose bounded connect/read timeouts, response headers, accepted PDF/HTML/plain-text media types, and the existing 25 MiB response ceiling, and return fixed sanitized failures. URL query values and downloaded bodies MUST NOT be logged. Safe filename/extension values SHALL be server-derived, and exact downloaded bytes SHALL cross the existing opaque approved-upload boundary before OCR. These narrow controls MUST NOT be represented as general arbitrary-network safety.

Both operations SHALL invoke existing `run_ocr` and `supervisor_ingest_document`, create complete ordered documentation fragments no larger than 1,800 UTF-8 bytes only after successful OCR and authorized trusted-adapter writes, verify that source bytes remain unchanged, return only a sanitized document ID and fragment count, and SHALL NOT auto-link. Public document identity SHALL be stable from the downloaded source-byte digest; only the server-only owner public-route origin may approve `public-https` or `public-pdf`. Hard validation SHALL complete before corpus mutation. The adapter uses ordinary Store operations and MUST NOT claim multi-key transaction or conflicting-write safety.

Librarian public/private/network ingestion and Coder artifact ingestion SHALL remain fail-closed until genuine trusted specialist handoffs are implemented. Candidate validators, mocked policy tests, and the manual owner public route are not specialist handoffs. Librarian, Coder, and OCR SHALL NOT communicate directly with each other or receive Store/database credentials. Reindexing and document/corpus deletion remain unsupported.

#### Scenario: Authenticated owner upload is ingested
- **WHEN** the installation owner explicitly selects a supported file, the sidecar preserves it, and the opaque reference passes owner, Store, upload-boundary, and OCR validation
- **THEN** server-derived identities route complete normalized Docling output through the trusted adapter and return only the canonical document ID and fragment count without linking it

#### Scenario: Librarian source lacks a trusted production handoff
- **WHEN** Librarian requests ingestion of a public, private, or network research source
- **THEN** ingestion remains unavailable and no corpus write occurs

#### Scenario: Authenticated owner submits a public document
- **WHEN** the installation owner explicitly submits a bounded public HTTPS page or PDF and the trusted downloader validates every connection/redirect and preserves the bounded accepted response through the upload boundary
- **THEN** server-derived identity routes complete normalized Docling output through the trusted adapter and returns only document ID/count without linking it

#### Scenario: Public download validation fails
- **WHEN** any URL, DNS, connection, redirect, header, media-type, timeout, or response-size validation fails
- **THEN** the route returns a fixed sanitized failure and performs no OCR or corpus mutation

#### Scenario: Coder artifact lacks a trusted production handoff
- **WHEN** Coder requests ingestion of a qualifying work artifact
- **THEN** ingestion remains unavailable and no corpus write occurs

#### Scenario: A direct specialist write is attempted
- **WHEN** Librarian, Coder, or OCR attempts to write the corpus without a supervisor-created delegation
- **THEN** the system denies the operation without changing corpus content

#### Scenario: OCR or source validation fails
- **WHEN** download approval, source validation, OCR, or a bounded corpus write fails
- **THEN** the system reports a sanitized failure and does not claim that corpus content changed

#### Scenario: Reindex or corpus deletion is requested
- **WHEN** a caller requests reindexing or implementation of document or corpus deletion under this capability
- **THEN** the system reports the operation as unsupported rather than simulating success
