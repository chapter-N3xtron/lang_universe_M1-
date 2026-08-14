## 1. Contract and governance decisions

- [ ] 1.1 Review and ratify the Coder role, subagent boundaries, tool-access limits, and separation of Jasper orchestration from implementation.
- [ ] 1.2 Define authorization classes, approval-unit grouping, escalation boundaries, and cancellation/timeout semantics for synchronous and asynchronous execution.
- [ ] 1.3 Define retention and access rules for raw Coder reports and Jasper’s contextual summaries.

## 2. Delegation and execution

- [ ] 2.1 Define and implement a task-scoped delegation contract carrying scope, tools, execution mode, authorization state, expected outputs, and completion state.
- [ ] 2.2 Implement bounded synchronous and asynchronous Coder execution with explicit in-progress, completed, failed, timed-out, and cancelled states.
- [ ] 2.3 Enforce least-privilege tool and repository-area access, including refusal to inspect secrets, credentials, private keys, auth headers, or unrelated working-tree changes.
- [ ] 2.4 Implement approval grouping for predictable low-risk steps and separate authorization for destructive, external, or materially broader actions.

## 3. Verification and reporting

- [ ] 3.1 Implement explicit smaller-model routing for deterministic formatting, lint, and type-check tasks with required inputs, recorded results, and escalation criteria.
- [ ] 3.2 Normalize Coder output into a report containing changed files, validation, completion state, blockers, authorization needs, and provenance.
- [ ] 3.3 Implement Jasper’s post-Coder workflow so it summarizes the report in the active conversation context rather than dumping raw report text into chat.
- [ ] 3.4 Ensure summaries distinguish observed current behavior, proposed requirements, completed work, and unresolved questions.

## 4. Validation and rollout

- [ ] 4.1 Add focused tests for role boundaries, tool restrictions, approval grouping, execution states, smaller-model escalation, and report provenance.
- [ ] 4.2 Add tests proving successful and blocked Coder reports are summarized contextually without raw-report dumping.
- [ ] 4.3 Run focused integration, authorization, and regression checks; document rollback by disabling the new delegation path if validation fails.
- [ ] 4.4 Validate smaller-model routing against the selection authority, capability evidence, no-silent-switch, selected-versus-actual, and escalation contracts.
