## Context

See `proposal.md` for motivation. Today the Coder node returns `coding_status` plus assistant messages; completion formatting and the execution manifest are appended to plain text. The outer Jasper flow can route Coder back to Jasper, but its documented baseline only asks Jasper to relay the returned assistant message. This permits a plain-text bypass with no strict Coder result contract.

Jasper already produces a structured response whose `voice_text` is consumed by the browser-sidecar speech architecture. That ownership and transport boundary must remain intact. Existing execution-manifest data remains the authority for execution identity, while this change only structures Coder's report about work and evidence.

## Goals / Non-Goals

**Goals:**

- Establish one strict `TechnicalReport` version `1.0` model shared at the Coder/Jasper handoff boundary.
- Make report production deterministic for success, partial, blocked, failed, and cancelled returns.
- Make Jasper's post-Coder response provably report-driven, concise, voice-friendly, and honest about evidence limits.
- Reject malformed reports without reviving the current plain-text relay path.

**Non-Goals:**

- Registering or rewiring graphs, adding MCP tools, or changing specialist transfer topology.
- Changing streaming, progress events, reconnect behavior, dashboards, or deployed acceptance.
- Changing `JasperResponse`, browser speech synthesis, sidecar ownership, or any text-to-speech transport.
- Persisting a new reporting dashboard or exposing full reports directly to users.

## Decisions

### 1. Use one strict report envelope and strict nested records

Add a shared backend model with `extra="forbid"`, strict validation, and a literal `version="1.0"`. Every top-level field required by `specs/coder-report-handoff/spec.md` is always serialized, including empty arrays. Nested records use the exact enums and bounds in the spec:

```text
TechnicalReport
  version: "1.0"
  completion_status: completed | partial | blocked | failed | cancelled
  task_notes: TaskNote[0..64]
  changed_files: ChangedFile[0..256]
  validation_evidence: ValidationEvidence[0..64]
  blockers: str[0..32]
  remaining_authorization_needs: AuthorizationNeed[0..32]
  material_risks: MaterialRisk[0..32]
  provenance: ReportProvenance
  supporting_references: SupportingReference[0..16]
```

A model-level validator enforces unique supporting-reference IDs, reference resolution, repository-relative file paths, and consistency between `completion_status` and unresolved blockers or authorization needs. The report uses concise evidence descriptions and locators, not unrestricted command logs.

Alternative considered: keep a free-form final message and prompt Coder to use headings. Rejected because headings do not provide version negotiation, bounds, enum validation, referential integrity, or reliable failure handling.

### 2. Build the report at the Coder boundary on every terminal path

Coder's terminal adapter converts session output, todos, execution state, and safe evidence metadata into a report. Normal completion, missing final result, caught failure, and cancellation handling each have an explicit status mapping. Existing `coding_status` may remain temporarily for compatibility, but it is derived from or checked against the report and is not Jasper's authoritative result.

Provenance is populated from run state and the canonical workspace: fixed producer `Coder`, coding session ID, thread identity, canonical workspace, nullable selected model, and an ISO-8601 generation time. Existing execution-manifest identity can be represented by a bounded `execution_manifest` supporting reference; the report does not redefine deployment truth.

Alternative considered: ask the language model to emit the final report directly. Rejected as the sole path because deterministic boundary assembly and validation are required even when the model fails, omits fields, or returns malformed content.

### 3. Carry the typed object in existing state rather than serialized assistant content

Add a typed report field to the existing shared state/result passed on the already-established Coder return path. Keep human-readable internal messages only for compatibility and diagnostics; Jasper's post-Coder branch reads and validates the object. No graph registration or transfer-tool change is part of this work.

Alternative considered: serialize JSON into an assistant message. Rejected because it preserves the plain-text bypass, invites truncation or accidental speech, and weakens type guarantees.

### 4. Use a dedicated deterministic Jasper handoff summarization boundary

When the latest return is from Coder, Jasper validates the typed report and passes a bounded report projection to its existing response-generation path with explicit summary rules. The projection retains completion status, material notes, evidence types/results, blockers, authorization needs, and risks while limiting file/reference detail. Tests must prove that available legacy assistant text cannot become the response when a report exists.

The output remains normal `JasperResponse.voice_text`. It is at most two short paragraphs, starts with outcome, and avoids JSON, tables, report labels, raw output, and exhaustive lists. Failure and non-completion language is mandatory when indicated by the report.

Alternative considered: expose the report verbatim and rely on the browser to summarize or speak selected fields. Rejected because it leaks an internal contract into the user experience and would change the browser-sidecar/TTS boundary.

### 5. Gate deployment wording on typed evidence

Summary logic preserves validation `type` and `result`. Source tests, static analysis, and builds can support only claims about those activities. Positive deployment wording is enabled only by relevant passed `deployment_check` evidence and must not be inferred from source-level evidence. This does not add deployed acceptance; it only governs claims about evidence already present.

Alternative considered: reduce validation to passed/failed text. Rejected because Jasper could no longer distinguish source verification from runtime or deployment verification.

### 6. Fail closed on absent or invalid reports

An absent, unsupported, or invalid report produces a short verification-limitation response and no completion assertion. Invalid raw data is logged only through safe diagnostics and is never dumped into `voice_text`. The legacy plain-text return cannot serve as factual fallback.

Alternative considered: relay plain text when validation fails. Rejected because it recreates the exact untyped bypass this change removes and can conceal failure.

## Risks / Trade-offs

- [Report assembly cannot recover evidence that Coder never captured] → Record `not_run` or `inconclusive` evidence and require truthful non-completion/material-risk handling rather than inference.
- [Strict versioning can turn producer/consumer drift into visible failures] → Define one shared model, contract tests, and an explicit unsupported-version response.
- [Concise speech can omit useful detail] → Preserve material blockers, authorization needs, risks, and failed evidence first; keep bounded supporting references in the internal report for follow-up.
- [Legacy messages may accidentally remain authoritative] → Add orchestration tests with conflicting legacy text and report data, asserting that the report wins.
- [A report could include sensitive command output or paths] → Bound references, store summaries/locators rather than raw logs, apply existing secret restrictions, and prefer repository-relative paths.
- [Status and field consistency may be ambiguous] → Centralize deterministic status mapping and validate that `completed` cannot coexist with outcome-preventing blockers or authorization needs.

## Migration Plan

1. Introduce the strict report and nested-record models with schema, bound, referential-integrity, and status-consistency tests.
2. Add report construction to every terminal Coder return while retaining existing messages and `coding_status` only as temporary compatibility data.
3. Add the typed report to the existing shared state handoff and make Jasper's post-Coder handling validate and consume it.
4. Replace direct relay behavior with report-driven concise summarization and a fail-closed invalid-report response.
5. Add focused tests for completed, partial, blocked, failed, malformed, bounded-reference, conflicting-legacy-text, evidence-type, and browser-sidecar-preservation cases.
6. Remove authority from the plain-text bypass once all focused tests pass. Roll back by reverting report consumption and construction together; no data migration or speech-transport rollback is required.
