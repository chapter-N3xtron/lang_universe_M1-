# Spike A — TanStack Virtual

Candidate: `@tanstack/react-virtual@3.14.9` (real package; installed independently).
This sandbox intentionally leaves the production message list unchanged: the adapter is an isolated feasibility artifact, not a replacement.

Native coverage: item measurement/virtual range, keyed item identity, scrollToIndex; no native knowledge of hydration, LangGraph message tuples, semantic completion, duplicate reconciliation, or human-cancel policy. Dynamic height is possible through `measureElement`, but anchoring after delayed growth requires application policy.

Files created: `src/spikes/tanstack-virtual-anchor.ts`, this document, and candidate package metadata/lockfile.

Integration note: the current UI renders a bounded window and owns one-shot placement phases. Replacing it requires mapping message IDs to stable virtual keys, preserving DOM measurement during markdown growth, and coordinating scroll cancellation with virtualizer corrections.

Rollback: `rm -rf /tmp/thread-behavior-spikes/tanstack`.
