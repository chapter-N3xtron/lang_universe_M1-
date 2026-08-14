## Context

This proposed capability supplies evidence to `../model-selection-and-stewardship/` and must remain distinct from selection authority. It also supplies verification references to `../durable-interaction-records/` without becoming a model-use ledger.

## Evidence model

Evidence is normalized but not flattened: provider/documentation, benchmark, local-hardware, and task-verification records retain separate semantics. Metrics remain multidimensional, with uncertainty, freshness, version/configuration, environment, and task provenance attached.

## Recommendation boundary

A recommendation is an explanation constrained by authorized task requirements and available evidence. It is not authorization to switch models, providers, locations, or hardware. Selection authority and fallback behavior are defined by `../model-selection-and-stewardship/`; this change only establishes whether a candidate is evidenced as suitable.

## Open Questions

Thresholds, freshness windows, confidence methodology, benchmark comparability, and the owner of verification datasets require approval. Until resolved, unknown evidence must remain visible and cannot justify silent escalation.
