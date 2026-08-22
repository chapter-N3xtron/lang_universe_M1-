# Coder Architecture Delivery Board

## Why

Coder needs one truthful, human-controlled contract for both implementation delivery and read-only architecture comprehension. The existing Coder workflow describes delegation and reporting, while the Visualization Board requirements describe where substantial specialist output belongs; neither fully specifies architecture explanation, semantic playback, layered board artifacts, or the boundaries needed to keep delivery safe and attributable.

## What Changes

- Define two explicit user-controlled Coder modes: deadline-oriented implementation/delivery and read-only architectural comprehension.
- Define source-grounded architecture explainers for modules, functions, variables, control flow, data flow, regular loops, asynchronous loops/`await`/event flows, and source-linked paths, symbols, blocks, and line ranges.
- Define layered artifacts for the shared Visualization Board while preserving React Flow interactive diagrams and the existing artifact/persistence authority.
- Require concise Jasper chat summaries and complete, inspectable board artifacts.
- Define semantic per-chunk playback tied to artifact revisions and highlight targets.
- Define session, provenance, repository-revision, memory, and storage boundaries; scope, authorization, safety, and partial/blocked/at-risk/deadline states.
- State explicit relationships and non-duplication with `coder-architecture-workflow`, `visualization-board-alignment`, `durable-interaction-records`, `anatomy-of-a-session`, and `isolate-coder-librarian-workers`.
- Record Linux/Docker execution constraints without inventing a transport or storage authority.
- Place both Coder comprehension and delivery modes under the system governance layer, with an explicit non-replacement-of-human-resonance and bounded-support boundary.

This is a documentation/specification change only. It does not implement runtime code, change schemas, alter application behavior, or claim any capability is implemented.

## Capabilities

### New Capabilities

- `coder-architecture-delivery-board`: User-controlled Coder modes, source-grounded architecture explanations, layered board delivery, semantic playback, and safety/provenance boundaries.

### Modified Capabilities

- None. Existing contracts remain authoritative unless a later implementation proposes a compatible extension through its own reviewed change.

## Impact

Planning artifacts only under this change directory. Future implementation may affect Coder orchestration, board rendering, playback metadata, and durable record writers/readers, but this change authorizes none of those modifications.

## Non-goals

- No runtime code, schema, migration, prompt, model, transport, storage authority, or user-interface implementation.
- No autonomous mode selection, deadline invention, repository mutation in comprehension mode, or authorization inferred from board selection.
- No replacement for React Flow/XYFlow, LangGraph checkpoints/Store, the session catalog, Docker Compose, or the isolated worker boundary.
- No exposure of secrets, credentials, private files, Git internals, or hidden chain-of-thought.

## Dependencies

This change depends on the definitions and boundaries in the five named OpenSpec changes, the shared board requirements document, and the repository's existing Linux/Docker deployment constraints. It proposes no schema or protocol dependency.
