## 1. Contract review

- [ ] 1.1 Review and ratify the two user-controlled Coder modes, including read-only enforcement and user-supplied deadline semantics.
- [ ] 1.2 Review source-locator, provenance, repository-revision, and observed-versus-inferred explanation rules.
- [ ] 1.3 Confirm compatibility with `coder-architecture-workflow`, `visualization-board-alignment`, `durable-interaction-records`, `anatomy-of-a-session`, and `isolate-coder-librarian-workers` without duplicating authority.

## 2. Architecture explainer design

- [ ] 2.1 Define compatible representations for module, symbol, variable, control-flow, data-flow, regular-loop, and async/event explanation layers.
- [ ] 2.2 Define source-linked path, symbol, block, and line-range resolution, stale-target behavior, and protected-source handling.
- [ ] 2.3 Define acceptance fixtures for ordinary loops, `await`/resume flows, event handlers, cancellation, errors, and statically unknowable behavior.

## 3. Visualization Board and playback design

- [ ] 3.1 Map explanation layers to existing board cards, outline, and React Flow/XYFlow diagrams without creating a competing renderer or identity.
- [ ] 3.2 Define a compatible extension for semantic playback chunks, artifact revisions, source targets, and highlight targets only in a separately approved implementation change.
- [ ] 3.3 Define concise Jasper summaries and complete board artifact retrieval, search, inspection, and bounded voice behavior.

## 4. Safety and lifecycle review

- [ ] 4.1 Define implementation-mode scope, authorization, deadline, partial, blocked, at-risk, cancellation, timeout, and failure handling.
- [ ] 4.2 Verify comprehension mode remains read-only and that secrets, credentials, unrelated paths, Git internals, host operations, and publication are excluded.
- [ ] 4.3 Verify Linux/Docker constraints consume the isolated worker boundary and do not invent a transport, broker, or storage authority.

## 5. Validation and implementation gate

- [ ] 5.1 Run the repository's documented OpenSpec validation/check command and record the result.
- [ ] 5.2 Obtain explicit review of unresolved decisions and risks before any runtime implementation is proposed.
- [ ] 5.3 If approved later, implement through a separate change with compatibility tests; this change itself must remain documentation-only.
