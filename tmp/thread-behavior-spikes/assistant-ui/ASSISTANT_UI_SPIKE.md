# Spike C — assistant-ui Thread/ThreadPrimitive

Candidate: `@assistant-ui/react@0.15.14` (real package; installed independently). This is an isolated API adapter only; current Agent Chat remains unchanged.

Native coverage: Thread primitives provide provider/composer/message rendering conventions and runtime-driven scroll behavior, but not this app's LangGraph SDK history hydration, messages-tuple accumulation, stable assistant replacement semantics, duplicate-ID reconciliation, or geometry contract. Dynamic content and user scrolling can be composed, not inferred from arbitrary external stream state.

Files created: `src/spikes/assistant-ui-thread-adapter.tsx`, this document, package metadata/lockfile.

Integration cost: substantial message-model bridge from `Message`/SDK stream metadata into assistant-ui runtime/thread state, plus preserving existing message controls and checkpoint editing. No schema migration is required if kept behind an adapter.

Rollback: `rm -rf /tmp/thread-behavior-spikes/assistant-ui`.
