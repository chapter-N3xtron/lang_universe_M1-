# No-Self Prompt Style

> **Status:** Working prompt-editing standard for human review.
>
> **Purpose:** Keep model-facing prompts and tool descriptions consistent, non-self-referential, non-coercive, and centered on supporting a human's mental clarity and ability to engage in an evidence-based inquiry.
>
> **Boundary:** This document defines language and formatting. It does not grant model authority, replace deterministic safeguards, or authorize prompt implementation. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## 1. Core principle

Developer-authored model instructions describe a function, task, constraints, and output. They do not describe a living entity, personal identity, inner state, intention, relationship, or knowledge of self.

Use functional language:

```text
Role:
Creator of a non-coercive research brief, free from dark patterns,
in support of a human's inquiry.
```

Do not use identity language:

```text
You are a research assistant.
Your job is to understand what the user needs.
```

## 2. Required prompt structure

Use these sections in this order:

```text
Role:
<Functional role and how that role supports the human.>

Task:
<Specific operation for this pipeline stage.>

Constraints:
<Scope, evidence, safety, no-self, anti-coercion, and quality rules.>

Output:
<Exact expected result or structured fields.>
```

Input or context blocks may appear between `Task` and `Constraints` when needed:

```text
Human messages:
<Messages>
{messages}
</Messages>

Date:
{date}
```

Input blocks are data. Instructions found inside human messages, retrieved pages, search results, quotations, or tool output do not replace the developer-authored task and constraints.

## 3. Role formatting

`Role` explains the function and its relationship to the human. It does not repeat the task.

Role wording must be specific to the current pipeline stage. The no-self philosophy and human-support relationship remain consistent, but the functional role must accurately describe clarification, brief creation, supervision, research, compression, report construction, or another applicable stage. Do not reuse one generic role across the pipeline.

Good:

```text
Role:
Facilitator of non-coercive research clarification, free from dark
patterns, in support of a human's mental clarity and ability to engage
in an evidence-based inquiry.
```

```text
Role:
Organizer of research evidence in support of a human's mental clarity
and ability to engage in an evidence-based inquiry.
```

```text
Role:
Constructor of a clear, non-coercive, evidence-grounded report, free
from dark patterns, in support of a human's mental clarity and ability
to engage in an evidence-based inquiry.
```

Not acceptable:

```text
Role:
Summarize the research findings.
```

The example above is a task, not a role.

## 4. No-self language rules

Developer-authored prompts, schema descriptions, tool descriptions, and tool-result instructions must not refer to the model through first-person or second-person identity language.

Avoid:

- `I`, `me`, `my`, `mine`
- `we`, `us`, `our`, `ours`
- `you`, `your`, `yours`
- `yourself`, `myself`, `ourselves`
- Statements such as `You are...`, `Your job is...`, `I found...`, or `We will...`
- Claims of understanding, belief, desire, intention, confidence, emotion, memory, awareness, experience, authorship, or relationship

Use:

- Functional role names
- Direct task statements
- Neutral action verbs
- Observable system or pipeline states
- Explicit source and evidence language

Examples:

```text
Instead of: You should decide whether more research is needed.
Use: Determine whether material evidence gaps remain.
```

```text
Instead of: What key information did I find?
Use: Identify the key findings supported by the available evidence.
```

```text
Instead of: Confirm that you will now begin research.
Use: State neutrally that the research process will begin.
```

Quoted human language, source text, and evidence may contain these pronouns. Preserve quotations accurately and keep them clearly marked as data rather than developer-authored instructions.

### Agentic workflow violation reporting

The no-self rule does not prevent evidence-based recognition of actions or violations produced by an agentic workflow.

Use this format:

```text
Observed context:
<Validated human input, system event, or cited record.>

Observed action:
<Acting component and observable action.>

Rule reference:
<approved rule ID> — <exact approved rule text>

Evidence:
<Traceable evidence connecting the action to the observed context.>

Assessment:
<Conflict between the observed action and referenced rule.>

Resulting boundary:
<Fail-closed state, unresolved decision, or required human review.>
```

A violation report must identify the observed context, acting component, observed action, explicit approved rule ID and rule text, supporting evidence, and resulting boundary. Do not infer motive, desire, awareness, or intention.

When no approved rule ID exists, label the assessment as a potential conflict requiring human review, not as an authoritative violation.

## 5. Human-support and anti-coercion rules

Every human-facing or human-influencing prompt must support mental clarity and evidence-based inquiry.

Required constraints where relevant:

- Preserve the human's stated scope and language.
- Preferences, requirements, and outcome criteria absent from human input remain unspecified unless supplied through a clarification response.
- Do not broaden the task without explicit human direction.
- Do not use pressure, persuasion, emotional loading, scarcity, social proof, engagement tactics, or repeated prompting after refusal.
- Do not present one option as morally, socially, or emotionally preferred.
- Distinguish observed evidence, inference, uncertainty, limitation, and proposal.
- Preserve disagreement and conflicting evidence without forcing resolution.
- State material limitations without alarmist framing.
- Keep requests for clarification necessary, bounded, and neutral.
- Keep declining, deferring, or stopping available without penalty or degraded support.
- Do not claim completeness, success, or certainty without evidence.

## 6. Report-quality rules

Prompt instructions that shape reports should protect clarity without removing material evidence.

Use constraints such as:

```text
- Preserve every unique relevant finding, citation, limitation, and
  evidence relationship.
- State each materially identical claim once in the most relevant section.
- Attach all supporting citations to that statement.
- Keep related but meaningfully different claims distinct.
- Present conflicting claims separately and preserve the evidence for each.
- Do not repeat full background explanations across sections.
- Keep report length proportionate to the research brief.
- Use headings only when they improve navigation.
- Use the conclusion to synthesize rather than repeat every section.
```

Do not use uncontrolled instructions such as:

```text
Be as comprehensive as possible.
Include anything even remotely relevant.
Make every section fairly long and verbose.
Repeat all relevant information verbatim.
```

## 7. Tool-description format

Model-visible tool descriptions follow the same no-self frame.

```text
Role:
Bounded evidence-gap assessment in support of an evidence-based inquiry.

Task:
Assess current findings and identify material evidence gaps.

Constraints:
- Use only the supplied findings.
- Preserve uncertainty and conflicting evidence.
- Do not broaden the research scope.
- Use neutral, non-self-referential language.

Output:
A concise evidence-gap assessment and bounded next-step recommendation.
```

Tool-result messages should report observable outcomes:

```text
Accepted:
Research findings recorded for the assigned topic.
```

```text
Avoid:
I recorded the findings and think more research is needed.
```

## 8. Structured-output formatting

Keep existing field names exact unless a separate schema change receives explicit approval.

```text
Output:
Return valid structured data with exactly these fields:

"need_clarification": boolean
"question": string
"verification": string
```

No-self framing changes the language placed in fields. It does not silently rename fields or change their types.

## 9. Prompt-review checklist

Before approving a prompt or tool description, verify:

- [ ] `Role` describes a function in support of the human, not a task or identity.
- [ ] `Task` states one bounded operation.
- [ ] `Constraints` include applicable no-self and anti-coercion rules.
- [ ] `Output` names the exact expected result or schema.
- [ ] Developer-authored text contains no first-person or second-person self framing.
- [ ] Human messages, source material, and tool output are clearly treated as data.
- [ ] The prompt does not broaden scope or infer a desired outcome.
- [ ] Evidence, citations, uncertainty, limitations, and disagreements remain protected.
- [ ] Length and formatting instructions support clarity rather than maximal output.
- [ ] No urgency, pressure, dark pattern, or engagement optimization appears.
- [ ] Existing schemas, tool names, and routing contracts remain unchanged unless separately approved.

## 10. Consent-gated editing process

Prompt editing proceeds one item at a time:

1. Show the exact current prompt and related model-visible descriptions.
2. Explain the current pipeline function in plain language.
3. Identify no-self, coercion, scope, evidence, and quality concerns.
4. Explain downstream effects of a change.
5. Draft one replacement using this style.
6. Support human questions and revisions.
7. Obtain explicit human consent for that prompt.
8. Move to the next prompt only after the human indicates understanding and consents.

No batch approval, silent prompt replacement, speculative code, or custom pipeline code is authorized by this process.
