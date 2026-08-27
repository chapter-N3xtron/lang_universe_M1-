## 1. Technical Report Contract

- [ ] 1.1 Add the strict shared `TechnicalReport` version `1.0` model and exact nested record enums, required fields, array bounds, text bounds, and extra-field rejection defined by the capability spec.
- [ ] 1.2 Add model-level validation for unique and resolved supporting-reference IDs, repository-relative changed-file paths, and completion-status consistency with blockers and remaining authorization needs.
- [ ] 1.3 Add focused contract tests for valid empty arrays, every completion and evidence type, missing or extra fields, unknown versions, field bounds, unresolved references, unsafe paths, and inconsistent completed reports.

## 2. Coder Report Production

- [ ] 2.1 Add the typed report field to the existing Coder/shared return state without changing graph registration, transfer topology, or progress streaming.
- [ ] 2.2 Implement deterministic report assembly from Coder task results, changed-file data, typed validation evidence, blockers, remaining authorization needs, material risks, canonical run provenance, and bounded safe references.
- [ ] 2.3 Produce and validate a report on completed, partial, blocked, failed, missing-final-result, and cancelled terminal paths while keeping legacy text non-authoritative.
- [ ] 2.4 Add Coder tests that verify truthful status mapping, explicit empty collections, retained changes on validation failure, bounded evidence references, provenance, and safe failure reports.

## 3. Jasper Consumption and Summarization

- [ ] 3.1 Detect the existing post-Coder return, validate the typed report, and make it Jasper's authoritative input instead of directly relaying the current plain-text completion message.
- [ ] 3.2 Implement the bounded report projection and concise plain-English summary rules for outcome, material work, typed validation, blockers, authorization needs, and material risks.
- [ ] 3.3 Enforce evidence-aware wording so source tests, static analysis, and builds never become deployment-success claims, and disclose failed or inconclusive deployment checks.
- [ ] 3.4 Add the fail-closed user response for absent, malformed, over-bound, unresolved-reference, or unsupported-version reports without dumping raw report or legacy text.
- [ ] 3.5 Add Jasper tests with conflicting legacy text and report data, non-completed outcomes, material risks, large reports, malformed reports, and source-test-versus-deployment evidence.

## 4. Focused Integration Verification

- [ ] 4.1 Add an existing-graph-path orchestration test proving Coder returns a typed report and Jasper actually consumes it to produce no more than two short voice-friendly paragraphs.
- [ ] 4.2 Add regression coverage proving summaries still use the existing `JasperResponse.voice_text` browser-sidecar path and introduce no text-to-speech endpoint, server audio stream, or transport change.
- [ ] 4.3 Run the focused Coder model, Coder node, Jasper handoff, Jasper response, and orchestration test suites and record source-level evidence without treating it as deployed acceptance.
