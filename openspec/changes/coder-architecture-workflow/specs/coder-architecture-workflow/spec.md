## Purpose

Defines an explicit, reviewable contract for delegating coding work to Coder while preserving role boundaries, authorization, efficient execution, and context-aware reporting to the active conversation.

## Observed Current Behavior

The current repository contains a Jasper-led agent-chat UI and existing subagent-oriented planning work, but no ratified Coder architecture or workflow contract was found in the main OpenSpec specifications. The questions below are therefore unresolved design questions, not descriptions of already-implemented behavior: Coder architecture; subagent roles and boundaries; tool access; synchronous versus asynchronous operation; approval and authorization flow; reducing approval noise; smaller-model routing for routine formatting, lint, and type checks; and the required post-Coder reporting workflow.

## ADDED Requirements

### Requirement: Coder architecture and role boundaries are explicit

The workflow SHALL define Coder’s responsibility as implementation-focused work and SHALL distinguish Coder’s responsibilities from Jasper’s orchestration, conversation, authorization, and user-facing synthesis responsibilities. The workflow SHALL identify boundaries for any other subagents so delegation does not imply authority outside the assigned task.

#### Scenario: Delegated implementation has a bounded role
- **WHEN** Jasper delegates an implementation task to Coder
- **THEN** the delegation identifies the task scope, Coder’s allowed responsibilities, and decisions that remain with Jasper or require human authorization

### Requirement: Tool access is least-privilege and task-scoped

Coder SHALL receive only the tools and repository areas needed for the assigned task, with access constraints visible to the delegating workflow. Coder MUST NOT infer permission to inspect secrets, credentials, private keys, auth headers, or unrelated working-tree changes from a general coding assignment.

#### Scenario: A task requests unrelated sensitive material
- **WHEN** Coder encounters a need to inspect a secret, credential, private key, auth header, or unrelated change
- **THEN** Coder declines that access and reports the blocker without exposing the sensitive material

### Requirement: Synchronous and asynchronous operation are distinguishable

The workflow SHALL define when Coder runs synchronously within the active turn and when it runs asynchronously, including completion, timeout, cancellation, and status semantics for each mode. A caller MUST be able to distinguish a completed report from an in-progress, cancelled, timed-out, or failed execution.

#### Scenario: An asynchronous Coder task is still running
- **WHEN** Coder has not completed an asynchronously delegated task
- **THEN** Jasper reports the task as in progress rather than presenting an incomplete report as final

### Requirement: Approval and authorization are explicit

The workflow SHALL distinguish user authorization, Jasper’s delegation decision, and Coder’s execution. Actions with material side effects or scope beyond the approved task MUST require the applicable authorization before execution. Routine, read-only, or already-authorized steps MUST NOT be represented as newly authorized merely because Coder is running.

#### Scenario: Coder encounters an out-of-scope side effect
- **WHEN** completing the task would require an action outside the authorized scope
- **THEN** Coder pauses or declines that action and returns a clear authorization-needed status to Jasper

### Requirement: Approval noise is minimized without weakening control

The workflow SHALL group predictable, low-risk steps into a clearly described approval unit and SHALL avoid repeated prompts for the same authorized scope. It MUST preserve a distinct approval boundary for new, higher-risk, destructive, external, or materially broader actions.

#### Scenario: Routine checks follow an approved coding task
- **WHEN** formatting, lint, or type checks are predictable parts of the authorized task
- **THEN** they execute under the approved unit without repeated equivalent prompts, while any materially broader action still requests separate authorization

### Requirement: Routine verification may use smaller models under explicit routing rules

The workflow SHALL define criteria for routing routine formatting, lint, and type-check work to a smaller model, including the allowed task class, required inputs, expected outputs, escalation conditions, and verification responsibility. A smaller model MUST NOT be used for architectural decisions, ambiguous changes, authorization decisions, or user-facing synthesis unless explicitly assigned and authorized.

#### Scenario: A routine check is safely routable
- **WHEN** a formatting, lint, or type-check task is deterministic, bounded, and has a machine-verifiable result
- **THEN** the workflow may route it to a smaller model and records the check result and model role

#### Scenario: A routine check reveals ambiguity or broader impact
- **WHEN** the smaller-model check cannot complete deterministically or indicates an architectural, security, or scope issue
- **THEN** the workflow escalates to Coder or Jasper rather than allowing the smaller model to decide the broader change

### Requirement: Jasper summarizes Coder reports in conversation context

After Coder completes, Jasper MUST read and validate Coder’s report, then summarize its material results, changed files, validation status, blockers, and unresolved authorization needs in the context of the active conversation. Jasper MUST NOT dump the raw Coder report into chat as the user-facing response; raw details MAY remain available through an explicitly requested or separately accessible record.

#### Scenario: Coder completes successfully
- **WHEN** Coder returns a completed report for the active task
- **THEN** Jasper provides a concise contextual summary that connects the result to the user’s request and does not paste the raw report

#### Scenario: Coder completes with blockers
- **WHEN** Coder reports a blocker, failed check, or authorization need
- **THEN** Jasper summarizes the blocker and its impact in the active conversation without hiding the failure or dumping the raw report

### Requirement: Workflow state and provenance are preserved

The workflow SHALL preserve the relationship between the user request, Jasper’s delegation, Coder’s execution, verification results, approvals, and Jasper’s contextual summary. Summaries MUST distinguish observed current behavior, proposed requirements, completed work, and unresolved questions.

#### Scenario: A report contains a proposal rather than completed work
- **WHEN** Coder’s output describes a possible design or recommendation without implementation evidence
- **THEN** Jasper labels it as proposed or unresolved rather than reporting it as completed behavior
