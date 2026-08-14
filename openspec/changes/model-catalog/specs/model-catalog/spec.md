## Purpose

Provide a normalized, provenance-aware model discovery catalog that supplies inspectable candidates and evidence to capability verification and model stewardship without becoming an execution or authorization authority.

## ADDED Requirements

### Requirement: API-first source adapters and discovery
The catalog SHALL represent provider/source adapters as explicit sources with source identity, adapter version, retrieval method, endpoint or documentation reference where safe, and source timestamp. Adapters SHALL prefer supported APIs or documented export surfaces, preserve raw source context separately from normalized fields, and report unsupported or unavailable discovery rather than inventing records.

#### Scenario: Source discovery succeeds
- **WHEN** an adapter retrieves provider metadata through a supported API
- **THEN** the catalog stores normalized fields, source identity, retrieval timestamp, adapter context, and a reference to the source response or safe digest

#### Scenario: Source has no supported discovery surface
- **WHEN** no supported API or documented export is available for a source
- **THEN** the catalog reports discovery as unavailable or research-only and does not present an inferred record as authoritative provider metadata

### Requirement: Initial source coverage and research limits
The catalog SHALL support Ollama sources, including `/api/tags` and `/api/show` as preliminary report context, Hugging Face Hub metadata/model cards/licenses/evaluation results, and ComfyUI-friendly model providers and aggregators. It SHALL preserve unknown benchmark/license fields for Ollama and SHALL label the earlier finding that unified ComfyUI aggregator APIs were not established as a research limitation rather than treating it as an API guarantee.

#### Scenario: Ollama record is imported
- **WHEN** `/api/tags` or `/api/show` supplies model information
- **THEN** the record identifies Ollama as the source, retains endpoint context and timestamp, and leaves standardized benchmark and license values unknown unless separately sourced

#### Scenario: Hugging Face evidence is imported
- **WHEN** Hub metadata, a model card, a license, or an evaluation result is retrieved
- **THEN** each item retains its source/provenance and is distinguishable as metadata, documentation, license information, or evaluation evidence

#### Scenario: ComfyUI discovery is requested
- **WHEN** a ComfyUI-friendly provider or aggregator is queried
- **THEN** available source-specific results may be cataloged, while absence of an established unified aggregator API is reported as uncertainty or limitation

### Requirement: Normalized model identity and lifecycle
Each catalog record SHALL normalize a stable source-qualified model identity, provider, source, revision or tag, modalities/capabilities, context limits, quantization and runtime metadata, local/cloud availability, active/retired status, licensing status, pricing or cost indicators where available, benchmark references, freshness, provenance, and uncertainty. Unknown, conflicting, estimated, and stale values SHALL remain explicitly labeled rather than silently resolved.

#### Scenario: Same model has multiple tags
- **WHEN** one source reports multiple tags or revisions for a model
- **THEN** the catalog preserves the source-qualified identity and records each relevant revision/tag without collapsing materially different versions

#### Scenario: License is unavailable
- **WHEN** a source supplies no reliable license status
- **THEN** user-facing catalog output labels licensing as unknown rather than open or commercial

#### Scenario: Model is retired
- **WHEN** a source reports retirement or refresh policy marks a model retired
- **THEN** the record remains historically addressable, is marked retired with reason/timestamp where available, and is excluded from active results by default

### Requirement: Refresh, synchronization, and stale data
The catalog SHALL support scheduled and on-demand refresh with per-source timestamps, freshness policy, rate-limit handling, bounded retries, partial failure reporting, and stale-data markers. Refresh SHALL be idempotent and SHALL not erase the last known record merely because a source is temporarily unavailable. Just-in-time provider or benchmark refresh MAY supplement cached metadata when freshness, authorization, rate limits, and privacy boundaries permit.

#### Scenario: Source is rate limited
- **WHEN** a refresh receives a rate-limit response
- **THEN** it records the source status and retry/backoff information, preserves prior data, and does not spin indefinitely or claim current freshness

#### Scenario: Cached metadata is stale
- **WHEN** a query uses metadata beyond its freshness policy
- **THEN** the result visibly indicates staleness and may request bounded just-in-time refresh without hiding the cached snapshot

#### Scenario: Refresh partially fails
- **WHEN** some source records refresh successfully and others fail
- **THEN** successful records advance independently, failed records retain prior provenance and error state, and the synchronization result reports partial completion

### Requirement: Deduplication and conflict handling
The catalog SHALL deduplicate records only using evidence-preserving identity rules and SHALL retain links to all contributing sources. Conflicting provider, revision, capability, license, availability, cost, or benchmark values SHALL remain source-qualified with conflict status and timestamps; the catalog SHALL not select an authoritative value solely by silent overwrite.

#### Scenario: Two sources describe one model differently
- **WHEN** normalized identity links records from multiple sources with conflicting fields
- **THEN** the query exposes the conflicting values, source provenance, and uncertainty, while preserving each source observation

### Requirement: PostgreSQL persistence and optional semantic indexing
Catalog metadata SHALL be persistable in PostgreSQL with structured fields suitable for filtering, provenance, lifecycle, freshness, and synchronization queries. Optional PGVector or equivalent semantic indexing MAY index selected descriptions, cards, or evidence, but structured metadata SHALL remain queryable without vectors and no requirement SHALL force all catalog metadata into embeddings.

#### Scenario: Semantic index is unavailable
- **WHEN** optional semantic indexing is disabled, unavailable, or stale
- **THEN** structured catalog filtering and provenance queries remain available, with semantic retrieval reported as unavailable or degraded

### Requirement: Discovery, evidence, recommendation, authorization, and use remain distinct
Catalog discovery and catalog evidence SHALL be distinguishable from task-specific capability verification, recommendation, human or approved-profile authorization, and actual model use. Catalog results MAY supply candidates and references to adjacent capabilities, but SHALL NOT select, authorize, silently switch to, or execute a model.

#### Scenario: Catalog candidate is shown for selection
- **WHEN** a user or steward views catalog candidates
- **THEN** the system identifies them as discovered/catalog evidence and leaves recommendation, authorization, and actual use as separate subsequent states

#### Scenario: Catalog evidence lacks task verification
- **WHEN** a model has provider documentation or benchmark references but no task verification
- **THEN** the catalog exposes that distinction and does not label the model as verified for the task

### Requirement: User-facing filtering and licensing clarity
User-facing catalog queries SHALL support filtering or sorting by provider/source, modality/capability, context limit, runtime/quantization, local/cloud availability, lifecycle, freshness, cost indicators, benchmark references, and licensing status where known. Licensing SHALL visibly distinguish open, commercial, and unknown, without implying that open licensing means unrestricted use or that unknown means open.

#### Scenario: User filters for local open models
- **WHEN** a user requests active, locally available models with open licensing
- **THEN** results include only records meeting the explicit known filters and clearly disclose stale, conflicting, or unknown fields excluded from the result

### Requirement: Privacy, credentials, and forward-compatible correlation
The catalog SHALL minimize and sanitize local hardware and provider-availability details, scope access to the authorized local owner/workspace context, and SHALL NOT persist credentials, tokens, auth headers, or secret payloads. Records MAY carry optional future correlation/reference fields for thread/session identifiers and catalog snapshot/version/source context, while preserving compatibility with `workspace_id` and existing session/thread terminology; this requirement SHALL NOT invent or imply a canonical session-ID contract.

#### Scenario: Provider availability is recorded
- **WHEN** a local or cloud availability observation is cataloged
- **THEN** it exposes only the approved availability/resource summary and provenance, not credentials, protected paths, or unnecessary hardware fingerprint detail

#### Scenario: Catalog is linked to model use
- **WHEN** a durable model-use record is available
- **THEN** it may reference the catalog snapshot/version and source context plus future-compatible session/thread correlation fields, while retaining the selected-versus-actual distinction and not changing existing identifiers
