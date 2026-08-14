## 1. Contract and data model

- [ ] 1.1 Define source-qualified catalog entities, observations, revisions/tags, lifecycle, freshness, uncertainty, and provenance schemas from the model-catalog spec.
- [ ] 1.2 Define normalized provider/source adapter contract with safe raw-context references, source timestamps, adapter versions, bounded errors, and idempotent refresh identity.
- [ ] 1.3 Define explicit distinctions and cross-record references for catalog discovery, capability evidence, recommendation, authorization, and actual model use.

## 2. Source adapters and ingestion

- [ ] 2.1 Implement Ollama discovery fixtures and adapter handling for `/api/tags` and `/api/show`, preserving preliminary-report limitations for benchmark and license fields.
- [ ] 2.2 Implement Hugging Face Hub ingestion for metadata, model cards, licenses, and evaluation results with separate evidence/provenance classes.
- [ ] 2.3 Define and test ComfyUI-friendly provider/aggregator adapters without assuming a unified third-party aggregator API; report unavailable discovery explicitly.
- [ ] 2.4 Add normalization, source-qualified deduplication, conflict preservation, and retirement handling across adapter outputs.

## 3. Persistence and retrieval

- [ ] 3.1 Add PostgreSQL persistence and indexes for exact filtering of identity, provider/source, modality, context, runtime/quantization, availability, status, licensing, cost, freshness, and provenance.
- [ ] 3.2 Add optional PGVector/semantic indexing for approved descriptive evidence while keeping structured metadata authoritative and usable without vectors.
- [ ] 3.3 Add user-facing catalog filtering and presentation that clearly distinguishes open, commercial, and unknown licensing and exposes stale/conflicting status.

## 4. Refresh and reliability

- [ ] 4.1 Implement scheduled/on-demand synchronization with per-source timestamps, rate-limit backoff, bounded retries, partial failure reporting, and preservation of last-known data.
- [ ] 4.2 Implement freshness policies, stale markers, and bounded just-in-time provider/benchmark refresh with explicit cached-versus-current status.
- [ ] 4.3 Add observability and tests for source failures, unavailable APIs, duplicate/reordered refreshes, conflicting fields, retirement, and semantic-index degradation.

## 5. Privacy and adjacent capability integration

- [ ] 5.1 Enforce owner/workspace scoping and sanitization for local hardware/provider availability, logs, raw context, and semantic indexing; verify no credentials or secret payloads persist.
- [ ] 5.2 Add optional snapshot/version/source references and forward-compatible session/thread correlation fields, retaining `workspace_id` and existing session/thread terminology without defining a canonical session ID.
- [ ] 5.3 Integrate catalog references as inputs to `model-capability-verification` and candidates for `model-selection-and-stewardship` without selecting or authorizing models.
- [ ] 5.4 Integrate available catalog snapshot/source context with `durable-interaction-records` model-use records; keep `research-agent-promotion` evidence provenance separate and apply `visualization-board-alignment`/`session-anatomy` only to relevant presentation/Perspective distinctions.
