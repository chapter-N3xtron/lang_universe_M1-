## Why

Model choice currently lacks a single human-controlled contract for authority, provider identity, local-first stewardship, and failure behavior. This proposal makes selection inspectable and predictable without claiming runtime implementation.

## What Changes

- Define human-facing selection authority and approved agent-profile authority.
- Define selection scope, precedence, local-first/cloud-stewardship behavior, and explicit no-switch guarantees.
- Define failure, retry, fallback, escalation, and safe diagnostics semantics.
- Require user-visible provider/model identity and bounded provenance for each selection.

## Capabilities

### New Capabilities
- `model-selection-and-stewardship`: Human-authorized, provenance-preserving model/provider selection and execution behavior.

### Modified Capabilities
- None.

## Impact

Future selector UI, agent profiles, routing/orchestration, provider adapters, durable model-use records, diagnostics, and session presentation. This is a proposed capability only; it changes no runtime code, provider configuration, credentials, or dependencies.
