## Context

See `proposal.md` for motivation and the delta specifications for behavioral requirements. This is a planning document, not an implementation-completion claim.

### Observed repository implementation

The reviewed baseline has top-level `research`, `jasper`, and `record_session` nodes; direct Research enters `record_session`, while a Jasper handoff returns to Jasper. Jasper has a parent-graph `transfer_to_research` command and no hidden compiled Research specialist. Research is built with a read-only virtual filesystem surface, explicit evidence tools, and a final Research-provenance message. Evidence persistence currently bounds content at 50,000 characters and uses Store namespaces for evidence bodies/session source metadata. The UI has a `SessionSources` component with Store-backed listing, display-name edits, source usage, and visual concept-map request composition.

These observations are code-level facts only. They do not establish the approved workflow, complete evidence/report schema, canonical report authority, renderer/service existence, style selection, dashboard requirements, consent/security controls, lifecycle/export policy, or end-to-end/release verification.

### Repository/reference facts

The official LangChain Open Deep Research repository is <https://github.com/langchain-ai/open_deep_research>. It may be reviewed as a candidate for selective workflow/code adaptation **or potential core internal Research architecture**. No license result, pinned version/compatibility, security assessment, governance fit, or integration review has been accepted. This change neither adopts, installs, vendors, nor copies it.

The workflow patterns under consideration are authorized task clarification/refinement, research-brief creation, subquestion planning/decomposition, bounded potentially parallel provider research, evidence-gap reflection, bounded follow-up research, working-context compression, and structured cited-report generation.

### User-approved proposed architecture

Research owns autonomous in-depth research, canonical report authorship/provenance, and an eventual renderer/service boundary. Jasper remains human-facing: it may assign/reopen Research, preserve the session relationship, introduce the transition, receive/synthesize results, present saved Research reports, and create evidence-grounded visual concept maps from saved report/evidence references. Jasper does not reread the web solely to recreate saved support and does not claim a Research report as Jasper work.

The canonical accessible text/structured cited report is authoritative. It contains content, citations, limitations, immutable evidence references/IDs, retrieval status, provenance, and source metadata. Every later rendered representation preserves those fields; style may never change substance.

## Goals / Non-Goals

**Goals:**

- Make Research's visible top-level ownership, Jasper coordination, and session relationship explicit.
- Evaluate Open Deep Research as either selectively adaptable patterns or potential core internal architecture while retaining the existing LangGraph Store/session evidence layer and Jasper access paths.
- Separate short-lived working state from durable evidence/report records: bounded LangGraph checkpoints for working context and resumable state; existing LangGraph Store for immutable/content-versioned evidence, canonical reports, and lightweight session references.
- Establish the canonical report contract before any renderer/service or style-selection design.
- Define an eventual Research-owned renderer/service boundary with safe human-facing style selection for clean, accessible, professional work presentation and separately configurable personal-interest/creative presentation.
- Preserve evidence-grounded Jasper presentation and visual concept-map generation without needless repeat web reads.
- Define an explainable, sanitized future dashboard/visual workspace contract.

**Non-Goals:**

- No runtime, UI, PDF/rendering, dependency, or application-code implementation in this change.
- No adoption, installation, vendoring, wholesale copy, or unreviewed dependency adoption of Open Deep Research.
- No renderer, templates, output-format, printable/exportable PDF, final visual identity, branding, artifact-storage lifecycle, or export/open/download authorization decision.
- No decision that any provider, scholarly/reference-library access, autonomous authority, external disclosure, consent rule, retention policy, or voice/provenance presentation is approved.
- No custom database, migration, custom evidence service/API, vector index, crawler, shell/command tool, Research mutation capability, unrestricted tool surface, host-filesystem access, or OCR. OCR remains separate and pending.

## Decisions

### 1. Research owns autonomous research and canonical report provenance; Jasper coordinates and presents

Research remains visible and independently addressable at the top-level LangGraph boundary. Jasper can assign or reopen it, preserve the session relationship, introduce the transition, receive a final result, synthesize it, present saved canonical Research reports, and create approved grounded visual concept maps from saved artifacts. Direct Research remains direct and does not fabricate a Jasper response.

This prevents specialist attribution from being obscured while preserving a coherent human-facing session narrative. Jasper presentation is not authorship transfer.

Alternatives considered:

- Make Jasper the autonomous researcher: rejected because it obscures specialist ownership and breaks the approved separation.
- Return Research to a hidden compiled subagent: rejected because visible lifecycle, auditability, and session relationship would again become implicit.

### 2. Evaluate Open Deep Research for selective adaptation or core architecture, not presumed adoption

Future review evaluates both selectively adapting particular patterns and using the project as Research’s core internal architecture. Either path must integrate with the existing LangGraph Store/session evidence layer and Jasper access paths. The candidate sequence remains authorized clarification/refinement; brief; decomposition; bounded potentially parallel approved-provider research; reflection; bounded follow-up; compression; and canonical cited report.

This names the real architectural choice without treating a public reference repository as an installed service, a durable evidence store, or authority to expand access. License, selected version/compatibility, security, governance, and integration review are decision gates, not formalities.

Alternatives considered:

- Adopt it wholesale now: rejected because review is incomplete and the architecture/data boundaries have not been reconciled.
- Treat it only as a selective reference: not yet chosen; it remains one review outcome alongside potential core internal architecture.

### 3. Canonical report first; every rendering is a bounded representation

The canonical accessible text/structured cited report is the authoritative artifact. It must preserve content, citations, limitations, immutable evidence references/IDs, retrieval status, provenance, and source metadata. A representation may improve legibility or presentation but cannot omit, rewrite, substitute, embellish, or otherwise alter substantive content or attribution.

This makes accessibility, citation inspection, durable reopening, and provenance resilient to later presentation decisions.

Alternatives considered:

- Make a PDF, styled template, or visual presentation authoritative: rejected because format, styling, and export decisions are open and can obscure accessibility or provenance.
- Render from free-form report prose without evidence references: rejected because it would permit citation/attribution laundering and weaken verification.

### 4. Eventual Research-owned renderer/service has narrow, data-only authority

After the canonical contract and design approval, an eventual Research-owned renderer/service will consume only saved canonical report/evidence references. It provides human-facing style selection with safe defaults: clean, accessible, professional work presentation and separately configurable personal-interest/creative presentation. It retains Research authorship/provenance and must preserve all canonical fields in every representation.

The renderer/service has no web access and no access to secrets, raw authentication material, unsupported local paths, or protected workspace material. It cannot introduce attribution laundering. It may not become a general file reader, retrieval client, or authority to export/open/download artifacts.

Alternatives considered:

- Let Jasper or a UI renderer freely assemble reports from web/workspace material: rejected because it breaks the saved-evidence boundary and weakens Research provenance.
- Couple a renderer directly to credentials, filesystem paths, or retrieval: rejected due to unnecessary authority and secret/protected-material exposure.

### 5. Checkpoints are working state; Store is durable evidence/report record

Short-lived working context and resumable execution state belong in bounded LangGraph checkpoints. The existing Store holds immutable/content-versioned evidence records, authoritative canonical reports, and lightweight session references. Evidence requires source/provider identifier or URL, bounded content, status, timestamp, hash/version, provenance, and required metadata. Canonical reports cite immutable evidence IDs and reopen without repeating web calls.

This avoids checkpoint growth, retains reconstructible provenance, and honors the approved no-custom-database/no-evidence-service boundary.

### 6. Validate saved-artifact grounding for Jasper visuals and presentation

Jasper may present saved reports and create visual concept maps or other approved visual forms using selected saved evidence or evidence references from a canonical report. Validation resolves citations to permitted immutable evidence IDs; it does not reread the web just to recreate prior support. Both Jasper presentation and renderer output preserve Research authorship/provenance.

This preserves provenance and makes saved work reusable while avoiding citation laundering.

### 7. Present a sanitized research record, never internal reasoning

The future dashboard/visual workspace must show status, brief/subquestions, progress, visited/read sources, retrieval failures/limitations, report status, durable artifacts, available presentation/style state, and sanitized execution history. It must omit chain-of-thought, secret material, raw auth data, and unsafe tool details.

This supports human understanding and correction without turning observability into a sensitive execution dump.

## Risks / Trade-offs

- [Open Deep Research selective adaptation or core-architecture adoption introduces license, version, security, governance, or integration incompatibility] → Review both paths before adoption; pin/record reviewed versions; do not install or copy by default.
- [Rendered output changes or omits substance/provenance] → Make canonical report authoritative; validate preservation of every required field in every representation.
- [Renderer expands into a secret, workspace, or web authority] → Use saved-reference-only inputs and deny these authority paths by design and tests.
- [Style selection creates inaccessible or coercive defaults] → Define safe accessible defaults and separately configurable work versus personal-interest/creative presentation. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [Autonomous research exceeds authority, provider, cost, or concurrency boundaries] → Keep these governance decisions open; implement only after explicit policy and bounded enforcement are defined. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
- [Checkpoint context grows or durable artifacts duplicate] → Bound checkpoint state; Store bodies/reports once and retain references/version identity.
- [Dashboard disclosure leaks sensitive content or reasoning] → Define and test a sanitized presentation projection rather than exposing raw state/traces.

## Migration Plan

1. Keep the four authoritative `todos.json` entries in their current truthful statuses; revise their scope only as necessary for this approved plan. Keep OCR separate.
2. Define and validate the canonical accessible report/evidence contract first, including immutable evidence references and report reopening without web calls.
3. Before runtime implementation, review Open Deep Research for selective adaptation and potential core-architecture adoption: license, version/compatibility, security, governance, and integration fit with Store/session evidence and Jasper access paths. Record the outcome rather than assuming approval.
4. After canonical-contract approval, design the renderer/service and safe style-selection boundary; then verify integrity, attribution, security, and accessibility before implementation.
5. Resolve renderer/templates/formats/PDF/branding/lifecycle/export authorization only through later human governance/design review. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
6. Implement only after governance/design decisions establish approved providers/libraries, authority/consent/disclosure scope, secret-manager credential boundary, budgets/concurrency/stop conditions, retention/deletion, and voice/provenance presentation. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
7. If rollout regresses, disable new workflow/presentation entry points while preserving immutable evidence/report artifacts and references; do not delete or rewrite provenance as rollback.

## Open Questions

The following are intentionally unresolved and must be decided through governance/design review before implementation commits to a provider or behavior:

- Which Open Deep Research review outcome is acceptable: selective adaptation, potential core internal architecture, or neither?
- What is the renderer/service implementation boundary, and which templates, output formats, dependencies, printable/exportable PDF approach, and artifact-storage lifecycle are acceptable?
- What final visual identity, branding, and consistent stylization are approved for work and personal-interest/creative presentation?
- What authorization permits report rendering, opening, downloading, or export, and how is it revocable?
- Which web providers and scholarly/reference libraries are approved, and what provider terms apply?
- What explicit authorization scope permits autonomous task clarification, external retrieval, follow-up research, and external disclosure/consent?
- Which secret manager and runtime injection boundary supplies provider credentials, with no credentials in checkpoints, Store records, artifacts, logs, UI, or renderer inputs?
- What cost, rate, parallelism/concurrency, retry, and stop-condition budgets apply per session/run/provider?
- What source/report retention, deletion, export, and fork-inheritance policy applies to immutable/versioned artifacts?
- How should voice and visual provenance communicate Research status, uncertainty, citations, and limitations accessibly?

These are unresolved policy choices, not settled requirements or implementation authorization.