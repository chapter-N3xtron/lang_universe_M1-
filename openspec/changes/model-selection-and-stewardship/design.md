## Context

This is a proposed contract coordinated with `../model-capability-verification/` and `../durable-interaction-records/`. It does not authorize runtime implementation.

## Decisions

- Human intent is the authority; profiles and defaults are bounded delegated authority.
- Selection is resolved from narrowest authorized scope outward and never by hidden provider heuristics.
- Local-first is a stewardship preference constrained by verified capability and explicit user/provider policy, not an assumption that local hardware exists.
- Every attempt retains selected versus actual identity and an explicit outcome; diagnostics remain sanitized.

## Boundaries

Capability evidence belongs to `../model-capability-verification/`; durable records belong to `../durable-interaction-records/`. UI selector presentation may reference this change, but selector behavior is defined here rather than in visualization-board-alignment. No provider installation, credential change, cloud call, or hardware purchase is part of this proposal.

## Open Questions

Approval owners for profile publication, exact scope names, policy values for cloud data/cost/region/retention, and whether an already authorized fallback may proceed automatically remain unresolved. Until decided, fallback must fail closed or request explicit authorization.
