## Context

See `proposal.md` for motivation and preliminary research context. The catalog is a proposed supporting data plane beneath `model-capability-verification` and `model-selection-and-stewardship`; it is not an execution registry or policy authority. Existing terminology distinguishes repository binding `workspace_id` from visual workspace concepts, and existing interaction materials use session/thread/branch/turn/attempt terminology. No canonical future session-ID contract is established.

## Goals / Non-Goals

**Goals:**

- Establish a source-qualified, revision-aware catalog model that can preserve provider observations, research evidence, and uncertainty.
- Make API-first discovery, refresh state, freshness, retirement, conflicts, and provenance observable.
- Support structured PostgreSQL queries and optional semantic retrieval without making vectors the metadata authority.
- Provide a privacy-bounded bridge from catalog snapshots to future durable model-use records.
- Keep catalog discovery, capability evidence, recommendation, authorization, and actual use as separately inspectable concepts.

**Non-Goals:**

- Selecting, routing, authorizing, downloading, loading, or executing models.
- Treating provider claims or public benchmarks as task-specific capability verification.
- Guaranteeing a unified ComfyUI aggregator API where the preliminary research did not establish one.
- Persisting credentials, auth headers, payloads, protected paths, or a detailed hardware fingerprint.
- Defining a canonical session/thread identifier or changing `workspace_id` semantics.
- Replacing adjacent capabilities or duplicating their full requirements.

## Decisions

### 1. Use source-qualified observations, not one flattened model row

A catalog entity identifies the model as observed by a source, while source observations retain provider, endpoint, revision/tag, retrieved payload digest or safe reference, timestamps, and adapter context. Normalized projections can be queried, but source observations remain available for audit and conflict explanation. This prevents an Ollama tag, a Hub revision, and a ComfyUI asset reference from being treated as interchangeable identities.

**Alternative considered:** one canonical row with last-write-wins fields. Rejected because it loses conflicts, historical freshness, and evidence class.

### 2. Use adapter contracts with explicit source classes

Adapters should expose discovery, normalization, refresh status, and bounded error information through a common contract while allowing source-specific fields. Initial adapters cover Ollama `/api/tags` and `/api/show`, Hugging Face Hub metadata/model cards/evaluations/licenses, and ComfyUI-friendly providers or aggregators. Ollama output is intentionally incomplete for standardized benchmarks/licenses; ComfyUI aggregator availability remains an open source-by-source question.

**Alternative considered:** scrape arbitrary web pages as the primary source. Rejected because it is brittle, difficult to rate-limit safely, and weakens provenance. Research citations can still be ingested as explicitly non-provider evidence.

### 3. Separate cached catalog state from bounded just-in-time refresh

PostgreSQL stores normalized metadata, source observations, synchronization state, lifecycle, and freshness. Queries may use cached state and, under explicit policy, request a bounded provider or benchmark refresh. A refresh returns status and preserves the previous snapshot when the source fails or is rate limited. The catalog never implies that a just-in-time lookup has become a durable current snapshot until it is successfully recorded.

**Alternative considered:** query every source on every catalog view. Rejected for latency, availability, rate limits, and reproducibility. **Alternative considered:** cache indefinitely. Rejected because availability, licenses, benchmarks, and retirement change.

### 4. Keep structured metadata authoritative; make semantic indexing optional

Structured columns/relations support exact filters for provider, modality, context, runtime, availability, status, licensing, freshness, and cost. Optional PGVector indexes selected descriptions, cards, or evidence for semantic retrieval and are linked back to source/version records. Vector absence or staleness degrades semantic search only; it does not remove structured catalog behavior.

**Alternative considered:** embed the entire record and use vector similarity for all queries. Rejected because exact lifecycle, license, provenance, and policy filters require structured semantics.

### 5. Preserve evidence boundaries and downstream authority

Catalog records can be referenced by capability verification as inputs, but evidence class and limitations remain visible. Recommendations remain governed by `model-selection-and-stewardship`; authorization remains human or approved-profile authority; actual use is recorded by durable interaction/model-use records. Where available, a model-use record references a catalog snapshot/version and source context without making the catalog a competing ledger.

This is compatible with `durable-interaction-records` model-use correlation. `research-agent-promotion` may refresh or cite catalog evidence, but research provenance remains separate from provider metadata. `visualization-board-alignment` and `session-anatomy` are relevant only to presenting catalog status and maintaining the distinction between a user-facing Perspective and the underlying catalog/session data; they do not define catalog identity.

### 6. Use forward-compatible correlation references only

Catalog snapshots MAY carry optional, opaque references for future session/thread correlation and existing `workspace_id` where applicable. The schema and APIs must tolerate absent or unknown future fields. No canonical ID, generation rule, or settled session contract is introduced here.

### 7. Apply privacy and ownership at ingestion and query boundaries

Local availability and hardware observations are minimized to approved capability/resource summaries. Provider availability is represented as status and safe source context, not as credentials or secret configuration. Access is scoped to the authorized local owner/repository binding context, with sanitization before persistence, logging, vectorization, or user presentation.

## Risks / Trade-offs

- **[Risk] Provider APIs change or omit important fields** → Version adapters, preserve raw-safe source context and unknown values, and expose source timestamps and adapter errors.
- **[Risk] Conflicting model identities produce misleading deduplication** → Use source-qualified identity, retain all observations, and surface conflict status rather than silent overwrite.
- **[Risk] Stale cached data is mistaken for current availability or licensing** → Apply explicit freshness policies, visible stale markers, and bounded just-in-time refresh.
- **[Risk] Semantic indexing leaks sensitive metadata or obscures exact filters** → Sanitize before indexing, index only approved fields, and keep PostgreSQL structured records authoritative.
- **[Risk] Local hardware/provider details become a fingerprint or credential leak** → Minimize observations, enforce owner scope, redact secrets/protected paths, and test safe diagnostics.
- **[Risk] Users mistake catalog data for verification or authorization** → Label discovery/evidence classes and keep downstream recommendation, authorization, and model-use transitions separate.
- **[Risk] ComfyUI ecosystem lacks a stable unified aggregator** → Support source-specific adapters and explicitly report the research limitation; do not claim an aggregator contract.
- **[Risk] Future session correlation is over-specified prematurely** → Store optional forward-compatible references only and preserve existing `workspace_id` and session/thread terminology.

## Migration Plan

This change is proposed and has no runtime migration. If approved for implementation, introduce schema and adapter fixtures first, backfill only from explicitly authorized sources, mark imported records with initial snapshot/version and uncertainty, and run read-only validation before enabling refresh. Rollback disables adapters and semantic indexes while retaining or tombstoning catalog snapshots according to the separately approved retention policy; it must not alter interaction records or provider credentials.

## Open Questions

- Which source-specific freshness and retirement policies are acceptable for each initial adapter?
- Which exact safe fields should be exposed for local hardware and provider availability in each deployment?
- Which benchmark sources and evaluation-result formats are approved for ingestion beyond the preliminary research context?
- When the repository settles its session/thread-ID contract, which opaque correlation fields should become required for new model-use links?
