## Why

Model discovery is currently scattered across provider-specific knowledge, local runtime assumptions, benchmark sources, and research notes, making candidate identity, freshness, licensing, and provenance difficult to inspect. A supporting model catalog is needed now so capability verification and model selection can consume bounded, normalized evidence without conflating discovery with verification, recommendation, authorization, or execution.

## What Changes

- Add the proposed `model-catalog` supporting data-plane capability beneath `model-capability-verification` and `model-selection-and-stewardship`.
- Define API-first provider/source adapters, including preliminary Ollama discovery context, Hugging Face Hub metadata/model-card/evaluation context, and ComfyUI-friendly provider/aggregator boundaries.
- Normalize model identity, source/provenance, revisions/tags, modalities/capabilities, context limits, quantization/runtime metadata, availability, lifecycle, licensing, cost indicators, benchmark references, freshness, and uncertainty.
- Define refresh, synchronization, rate-limit, failure, stale-data, deduplication/conflict, and retirement behavior.
- Specify PostgreSQL persistence with optional PGVector/semantic indexing, hybrid cached metadata and just-in-time refresh, and user-facing filters.
- Preserve privacy boundaries for local hardware and provider availability, never persist credentials, and reserve forward-compatible correlation fields for future thread/session identifiers while retaining `workspace_id` compatibility.

## Capabilities

### New Capabilities
- `model-catalog`: Normalized, provenance-aware discovery and lifecycle catalog for locally and remotely available models and their metadata.

### Modified Capabilities
- None. The catalog supplies candidates and evidence to adjacent proposed capabilities without changing their requirements in this change.

## Impact

Future provider/source adapter interfaces, catalog ingestion and refresh jobs, PostgreSQL schema and optional PGVector indexes, catalog query/filter views, diagnostics, and durable model-use correlation. This is a proposed capability only: it changes no runtime code, dependencies, credentials, environment files, provider configuration, or external services.

## Research context

The following is preliminary research/context from the **Librarian report in the governing conversation**, not authoritative provider documentation and not a substitute for source-specific verification:

- Ollama API discovery, including `/api/tags` and `/api/show`, does not provide standardized benchmark or license fields; those endpoints are useful preliminary report context rather than complete catalog evidence.
- Hugging Face Hub exposes richer model-card, evaluation-result, and license metadata than the basic Ollama discovery surface.
- ComfyUI core/asset APIs appeared limited for unified catalog discovery, and unified third-party aggregator APIs were not established in the earlier research.
- PostgreSQL with optional PGVector supports structured metadata filtering and semantic retrieval; metadata need not all be placed into vectors.
- Hybrid local storage with just-in-time provider or benchmark querying is an architectural option for freshness and cost control.
- No complete end-to-end model catalog implementation was found.

These findings constrain the proposal's uncertainty and provenance language; they do not assert provider guarantees or fabricate citations/URLs.
