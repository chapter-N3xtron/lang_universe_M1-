## Context

See `proposal.md` for motivation and `specs/coder-architecture-workflow/spec.md` for the behavior contract. The repository currently has no main OpenSpec capability defining Coder’s architecture or reporting workflow. The design must therefore preserve the distinction between observed behavior and requirements proposed for later implementation.

## Goals / Non-Goals

**Goals:**

- Provide a reviewable architecture boundary between Jasper, Coder, smaller verification models, and any future subagents.
- Make task-scoped tools, authorization, execution mode, approval grouping, escalation, and report provenance explicit.
- Make Jasper’s contextual summary the user-facing post-Coder interface.

**Non-Goals:**

- No runtime orchestration, permission system, prompt change, model deployment, queue, persistence schema, or UI implementation.
- No selection of a specific vendor, framework, transport, or model.
- No automatic authorization, secret access, or inference of user intent.

## Decisions

### 1. Use a delegation contract as the architecture seam

Each future delegation should carry scope, role, tools, execution mode, authorization state, expected outputs, and completion state. This is preferred over implicit conventions because it makes boundaries testable and supports both synchronous and asynchronous execution.

Alternative considered:

- Rely on free-form prompts alone: rejected because scope, authorization, and report state become difficult to audit or distinguish.

### 2. Separate orchestration from implementation and verification

Jasper remains responsible for interpreting the active conversation, deciding whether to delegate, preserving authorization boundaries, and synthesizing the result. Coder performs bounded implementation work. Smaller models are limited to deterministic routine checks and escalate ambiguity. This separation avoids granting a verification worker architectural or authorization authority.

Alternative considered:

- Give one agent responsibility for delegation, implementation, checks, and user response: rejected because it obscures role boundaries and increases approval and reporting ambiguity.

### 3. Treat approval as scoped state, not repeated prompts

Future implementation should represent an approved unit of low-risk, predictable steps and retain a separate boundary for broader or higher-risk actions. This reduces approval noise while keeping control meaningful.

Alternative considered:

- Ask for approval before every command: rejected as noisy and likely to train users to approve mechanically.
- Allow unrestricted execution after the first approval: rejected because later side effects can exceed the original authorization.

### 4. Normalize completion into a report before user-facing synthesis

Coder’s output should be treated as an evidence-bearing report with completion state, changed files, validation, blockers, and authorization needs. Jasper should consume that report and produce a context-aware summary rather than forwarding raw output. This preserves useful detail while avoiding transcript dumping and clearly separates observed results from proposals.

Alternative considered:

- Stream or paste the raw Coder report into chat: rejected because it shifts interpretation to the user and can misstate proposals, failures, or unfinished work as conclusions.

### 5. Route routine checks by task class and escalation criteria

Formatting, lint, and type checks can be routed to a smaller model only when bounded and machine-verifiable. Any ambiguity, architectural impact, security concern, or authorization question escalates to Coder or Jasper. This keeps routine work efficient without allowing a smaller model to make consequential decisions.

Alternative considered:

- Route all Coder work to the smallest available model: rejected because implementation reasoning and scope decisions are not equivalent to routine verification.

## Risks / Trade-offs

- [Approval grouping hides a new side effect] → Encode action class and scope; retain a new approval boundary for destructive, external, or materially broader work.
- [Jasper’s summary omits a Coder failure] → Require completion state, validation, blockers, and authorization needs in the normalized report and summary.
- [Smaller-model routing misses an architectural issue] → Restrict routing to deterministic checks and require escalation on ambiguity or broader impact.
- [Synchronous execution blocks the active conversation] → Define explicit asynchronous status, timeout, cancellation, and completion semantics before implementation.
- [Observed behavior is confused with the proposed contract] → Label observations, requirements, completed work, and unresolved questions separately in records and summaries.

## Migration Plan

1. Review and ratify the proposed role, authorization, execution-mode, routing, and reporting requirements.
2. Define the delegation and report schemas without changing current runtime behavior.
3. Implement one bounded workflow behind explicit authorization and focused validation.
4. Roll back by disabling the new delegation path and retaining the existing behavior; no data migration is authorized by this planning change.

## Open Questions

- Which concrete execution boundary and transport should carry synchronous and asynchronous delegation?
- Which action classes qualify as one approval unit under the final governance decision?
- What retention and user-access rules apply to raw Coder reports versus Jasper summaries?
- Which approved profile and capability-verification evidence may authorize routine smaller-model routing, and which fallback/escalation decisions must remain human-facing?

Model selection is not inferred from Coder role: the authority, profile/version, capability evidence, selected-versus-actual identity, and failure/escalation path must be carried as provenance.
