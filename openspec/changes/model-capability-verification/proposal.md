## Why

A model’s provider description, benchmark result, local availability, and task performance are different kinds of evidence, but are easy to conflate. This proposal defines a normalized, uncertainty-aware verification contract so recommendations use the least adequate resource without hidden escalation or hardware assumptions.

## What Changes

- Define normalized capability evidence and distinct evidence sources.
- Define multidimensional metrics, uncertainty, freshness, and provenance.
- Define version/configuration/task verification requirements and least-resource recommendations.
- Prohibit hidden escalation, unsupported claims, and implied hardware purchases.

## Capabilities

### New Capabilities
- `model-capability-verification`: Normalized, provenance-aware verification of model capabilities and resource suitability.

### Modified Capabilities
- None.

## Impact

Future model catalogs, verification fixtures, recommendation logic, selection UI, and durable provenance. This is specification-only; it adds no benchmark runs, provider calls, dependencies, hardware, credentials, or runtime behavior.
