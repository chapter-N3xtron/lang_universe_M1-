## Why

Research is already partially present as a top-level specialist, but its autonomous in-depth workflow, durable evidence/report boundary, report-presentation boundary, and human-understandable progress contract need an explicit, reviewable architecture. The approved direction permits review of LangChain's Open Deep Research reference implementation for either selective adaptation or possible core internal architecture use without claiming adoption, installation, code copying, or implementation completion.

## What Changes

- Establish Research—not Jasper—as the owner of autonomous in-depth research. Research remains a visible, independently addressable top-level LangGraph specialist; Jasper assigns or reopens its work, retains the session relationship, introduces the transition, receives its result, and may synthesize it.
- Record the canonical accessible text/structured cited report artifact as authoritative. It must durably preserve content, citations, limitations, immutable evidence references/IDs, retrieval status, provenance, and source metadata.
- Specify an eventual Research-owned report renderer/service boundary that consumes only saved canonical report/evidence references and offers human-facing style selection with safe defaults. It can support configurable clean, accessible, professional work presentation and separately configurable personal-interest/creative presentation. Style must never alter substance.
- State that consistent branded/stylized report output, potentially including printable/exportable PDF, is intended; renderer, templates, output formats, dependencies, final visual identity, branding, artifact-storage lifecycle, and export/open/download authorization remain explicit open decisions.
- Document Open Deep Research (<https://github.com/langchain-ai/open_deep_research>) as a candidate for selective adaptation **or potential Research core internal architecture**, integrated with the existing LangGraph Store/session evidence layer and Jasper access paths, only after license, version/compatibility, security, governance, and integration review. It is neither installed nor adopted by this change.
- Preserve that Jasper may present saved Research reports and create evidence-grounded visual concept maps from saved report/evidence references without rereading the web or claiming Research authorship.
- Retain durable evidence semantics, Store/checkpoint separation, offline report reopening, visual citation validation, dashboard sanitization, all existing security boundaries, autonomous Research direction, persistence/dashboard requirements, and OCR exclusion.

## Capabilities

### New Capabilities

- `top-level-research-handoff`: Visible Research ownership, bounded Jasper–Research handoff/reopen lifecycle, authorized autonomous research workflow, Research provenance, and Jasper presentation of saved reports/visual concept maps.
- `durable-session-evidence`: Bounded immutable/versioned evidence, authoritative canonical cited reports, renderer input integrity, checkpoint/Store separation, offline reopening, and evidence-grounded visual generation.
- `session-sources-view`: Human-understandable research status, progress, sources, limitations, durable-artifact review, sanitized-history presentation, accessible saved-report presentation, and evidence-restricted visual concept-map composition.

### Modified Capabilities

- None. The repository has no existing main OpenSpec capability specifications.

## Impact

### Observed repository baseline

- `backend/src/chat_ui.py` already defines top-level `research`, `jasper`, and `record_session` nodes, routes direct Research to recording, and returns Jasper-delegated Research to Jasper.
- `backend/src/jasper_agent.py` already exposes a parent-graph `transfer_to_research` tool and no hidden compiled Research specialist.
- `backend/src/research_agent.py` already creates a read-only Deep Agents Research graph with selected-workspace discovery/reads and Research-provenance final output.
- `backend/src/research_evidence.py` already bounds stored content to 50,000 characters and uses Store namespaces for evidence bodies and session-source metadata.
- `agent-chat-ui/src/components/workspace/session-sources.tsx` already shows session sources, permits session display-name edits, and composes a visual concept map request.
- These are observed implementation facts, not conformance, renderer availability, security, accessibility, lifecycle, retention, export, or release-completion claims.

### Repository/reference facts

- The official Open Deep Research repository is <https://github.com/langchain-ai/open_deep_research>. Its license, version/compatibility, security posture, governance fit, and integration fit have not been accepted by this change.

### User-approved proposed architecture

- Research is the in-depth research engine and a visible top-level specialist. Jasper coordinates the human-facing relationship and can present saved Research reports or create grounded visual concept maps from saved Research artifacts/evidence without a new web read.
- LangGraph checkpoints hold bounded working context and resumable run state. The existing LangGraph Store is the durable session boundary for evidence/report artifacts and lightweight references.
- The canonical accessible text/structured report artifact is authoritative. An eventual Research-owned renderer/service consumes saved canonical report/evidence references, preserves every substantive and provenance field in every representation, and exposes safe human-facing style selection.

### Open decisions

- Renderer/service implementation, templates, output formats, PDF/print support, dependencies, final visual identity, branding, stylization, storage lifecycle, and export/open/download authorization.
- Whether Open Deep Research is selectively adapted or becomes Research’s core internal architecture after the required review.
- Provider/library approval, autonomous authority, external disclosure/consent, provider terms, secret-manager-only credentials, budgets, stop conditions, retention/deletion, and voice/provenance presentation. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

### Affected areas and constraints

- Future implementation may affect the top-level graph, Research workflow/tool contracts, checkpoint state, Store schemas, canonical report/evidence validation, renderer boundary, style selection, session recording, visual workspace/dashboard presentation, accessibility, provenance, and voice presentation.
- Existing implementation authority remains in the four current `todos.json` items: `implement-visible-jasper-research-handoff`, `persist-bounded-session-research-evidence`, `add-session-sources-view-and-renaming`, and `verify-top-level-research-and-session-sources`. OpenSpec tasks sequence and clarify those items without replacing their truthful statuses.
- The renderer/service has no authority to access secrets, raw authentication material, unsupported local paths, protected workspace material, or the web; it cannot introduce attribution laundering. Research retains report authorship and provenance.
- No runtime, UI, PDF/rendering, dependency, or application-code implementation is authorized by this planning revision. OCR remains pending and separate.

## Terminology boundary

In this change, selected-workspace research means a safe read within the selected
repository path/root. It does not imply a visual workspace or repository ownership
of evidence. Existing `workspace_id` fields remain durable repository binding IDs;
a session may have none, and artifacts remain owned by their producing
thread/session. Visual workspace is reserved for presentation/layout state. See
`openspec/TERMINOLOGY.md`.

## Model provenance boundary

Handoff, durable evidence, and session-source presentation reference the model-selection, capability-verification, and durable-interaction changes for selected-model authority, verification, selected-versus-actual identity, and continuity across resume/retry/reopen. Research/source evidence provenance remains distinct from model provenance; hidden escalation is not authorized.