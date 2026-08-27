# Phase_6_Coder_report_handoff

## Why

Coder currently returns completion information as plain assistant text, so Jasper can only relay or reinterpret an unvalidated message. A versioned, typed handoff is needed so Jasper can reliably disclose completion, failures, evidence limits, blockers, authorization needs, and risks in a concise spoken summary.

## What Changes

- Introduce a strict, versioned `TechnicalReport` contract produced whenever Coder returns to Jasper, with required fields for completion status, task notes, changed files, typed validation evidence, blockers, remaining authorization needs, material risks, provenance, and bounded supporting references.
- Require Jasper to consume the validated report after Coder returns and generate a concise, voice-friendly plain-English user summary rather than dumping the raw report.
- Require summaries to disclose failure or incomplete work and to distinguish source-level test evidence from deployment evidence; source tests alone cannot support a deployment-success claim.
- Replace the current bypass/plain-text completion handoff as the authoritative Coder-to-Jasper result while retaining a safe, explicit invalid-report failure path.
- Preserve the existing browser-sidecar speech architecture and its `JasperResponse.voice_text` output; do not add or change text-to-speech transport.
- Exclude graph registration, MCP, streaming or reconnect behavior, dashboards, and deployed acceptance.

## Capabilities

### New Capabilities

- `coder-report-handoff`: Defines Coder's typed technical report and Jasper's truthful, voice-friendly consumption and summarization behavior.

### Modified Capabilities

None.

## Impact

- Affects the backend Coder result model/state, Coder return assembly, Jasper post-Coder handling, prompts/formatting boundaries, and focused contract and orchestration tests.
- Introduces an internal versioned handoff contract between existing Coder and Jasper execution paths; malformed or unsupported reports fail closed into an explicit user-visible limitation.
- Does not alter browser speech synthesis, sidecar ownership, frontend text-to-speech transport, graph registration, MCP surfaces, streaming/reconnection, dashboards, or deployment acceptance criteria.
