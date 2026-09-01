## 1. Technical Report Contract

- [x] 1.1 Add the strict shared `TechnicalReport` version `1.0` model and exact nested record enums, required fields, array bounds, text bounds, and extra-field rejection defined by the capability spec.
- [x] 1.2 Add model-level validation for unique and resolved supporting-reference IDs, repository-relative changed-file paths, and completion-status consistency with blockers and remaining authorization needs.
- [x] 1.3 Add focused contract tests for valid empty arrays, every completion and evidence type, missing or extra fields, unknown versions, field bounds, unresolved references, unsafe paths, and inconsistent completed reports.

## 2. Coder Report Production

- [x] 2.1 Add the typed report field to the existing Coder/shared return state without changing graph registration, transfer topology, or progress streaming.
- [x] 2.2 Implement deterministic report assembly from Coder task results, changed-file data, typed validation evidence, blockers, remaining authorization needs, material risks, canonical run provenance, and bounded safe references.
- [x] 2.3 Produce and validate a report on completed, partial, blocked, failed, missing-final-result, and cancelled terminal paths while keeping legacy text non-authoritative. A caught `asyncio.CancelledError` returns a normal Coder state/output with a validated cancelled report, compatible `coding_status="cancelled"`, and safe legacy cancellation diagnostic so the existing bridge delivers it to Jasper; do not re-raise it. Keep `GraphBubbleUp` propagation unchanged.
- [x] 2.4 Add Coder tests that verify truthful status mapping, explicit empty collections, retained changes on validation failure, bounded evidence references, provenance, and safe failure reports.

## 3. Jasper Consumption and Summarization

- [x] 3.1 Detect the existing post-Coder return, validate the typed report, and make it Jasper's authoritative input instead of directly relaying the current plain-text completion message.
- [x] 3.2 Implement the bounded report projection and concise plain-English summary rules for outcome, material work, typed validation, blockers, authorization needs, and material risks.
- [x] 3.3 Enforce evidence-aware wording so source tests, static analysis, and builds never become deployment-success claims, and disclose failed or inconclusive deployment checks.
- [x] 3.4 Add the fail-closed user response for absent, malformed, over-bound, unresolved-reference, or unsupported-version reports without dumping raw report or legacy text.
- [x] 3.5 Add Jasper tests with conflicting legacy text and report data, non-completed outcomes, material risks, malformed reports, and source-test-versus-deployment evidence.
- [x] 3.6 Correct the task digest so every task note's status and explanatory note is voiced when it fits; add focused coverage for multiple task notes covering every status, explicit 24,000-character voice-size overflow disclosure with retained report state, and conflicting deployment checks. Derive compatibility `coding_status` from the final assembled report status and verify the shared `JasperResponse` schema and fallback enforce the same 24,000-character limit.

## 4. Focused Integration Verification

- [x] 4.1 Add an existing-graph-path orchestration test proving Coder returns a typed report and Jasper actually consumes it to produce no more than two short voice-friendly paragraphs.
- [x] 4.2 Add regression coverage proving summaries still use the existing `JasperResponse.voice_text` browser-sidecar path and introduce no text-to-speech endpoint, server audio stream, or transport change.
- [x] 4.3 Run the focused Coder model, Coder node, Jasper handoff, Jasper response, and orchestration test suites and record source-level evidence without treating it as deployed acceptance.
