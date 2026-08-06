## Context

See `proposal.md` for motivation and `specs/session-anatomy/spec.md` for the behavior contract. The existing governance draft already identifies sessions as durable, linked records of a person’s work, decisions, explanations, and visual artifacts, while distinguishing human intent and authorization from model inference. The repository has no archived main OpenSpec capabilities, and the related `research-agent-promotion` change defines durable Research evidence and reports without defining the broader session anatomy or a user-authored Perspective.

## Goals / Non-Goals

**Goals:**

- Establish the conceptual boundary needed for future session work to associate inquiry materials coherently.
- Make the user-authored Perspective an explicit durable session record distinct from generated, sourced, or computational materials.
- Preserve the user’s ability to revisit and change their view as materials and understanding develop.
- Keep learning, scientific inquiry, social or political deliberation, voting considerations, and decision-tool use descriptive rather than outcome-prescriptive. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

**Non-Goals:**

- No implementation, persistence schema, database migration, UI, API, polling mechanism, visualization renderer, PDF generator, or decision tool is selected or authorized.
- No categorization scheme is made exhaustive, and no requirement obliges a session to contain a particular material type.
- No political conclusion, voting recommendation, political profile, or inference about a user’s beliefs is authorized.
- No rule is established for automatic Perspective generation, model authorship, automated overwrites, retention/deletion, sharing, or access control; these require later human governance and product decisions. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## Decisions

### 1. Define the session around inquiry, not chat chronology

A session is specified as an Inquiry-oriented body of work. This accommodates conversation while making the durable unit understandable through its assembled materials and user’s evolving view.

Alternative considered:

- Define a session as a transcript or thread only: rejected because it does not describe how charts, documents, research outputs, polls, and user understanding relate as one inquiry.

### 2. Make Perspective explicitly user-authored and separate from materials

Perspective is a durable user-authored record of a current understanding, conclusion, decision, or stance. Generated summaries, reports, polls, visualizations, and decision-tool outputs remain materials; they never silently become the user’s statement.

Alternative considered:

- Treat the latest model synthesis as the current Perspective: rejected because it would collapse model output into human authorship and obscure the user’s actual view.

### 3. Treat Perspective as revisable rather than final

The contract permits revisiting and updating Perspective without framing revision as error, endorsement, authorization, or finality. This supports inquiry that develops over time and avoids converting a draft view into an irreversible profile.

Alternative considered:

- Freeze Perspective after it is recorded: rejected because it conflicts with learning and evidence-based reconsideration.

### 4. Keep political and voting examples non-prescriptive

Political perspective formation and voting considerations are valid illustrative inquiries, but the specification requires the system to preserve the user’s deliberation and not assign a political stance, candidate preference, or vote.

Alternative considered:

- Exclude political inquiry entirely: rejected because it would unnecessarily exclude a legitimate user-directed inquiry use while not addressing attribution or coercion risks.

## Risks / Trade-offs

- [Artifact categories are mistaken for a required implementation schema] → Treat them as behavioral categories and defer storage and representation design.
- [Generated output is presented as the user’s belief] → Require explicit user authorship for Perspective and separate it from every generated or sourced material type.
- [A saved Perspective is interpreted as permanent or decisive] → Require revisability and prohibit inference of finality, agreement, or authorization from an unchanged record.
- [Political or voting support becomes prescriptive] → Limit the contract to user-directed deliberation and prohibit inferred or prescribed political conclusions. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## Migration Plan

1. Add this planning specification without changing current implementation behavior or stored data.
2. Before any implementation, obtain human governance and product decisions for authorship confirmation, revision/history semantics, retention/deletion, sharing/access control, and presentation accessibility. Governance reference: `GOVERNANCE_FRAMEWORK.md`.
3. Design future session data and UI contracts to meet the specification while preserving the existing durable evidence and report provenance boundaries.
4. If a future implementation cannot distinguish user authorship from generated output, withhold Perspective labeling rather than attributing a Perspective to the user.

## Open Questions

- What explicit interaction confirms authorship when the system assists a user in drafting Perspective text?
- Should prior Perspective versions be retained, and if so, what user-visible revision, retention, and deletion controls apply?
- Which access, sharing, export, and cross-device controls apply to a Perspective and its related materials?
- How should accessibility and localization support review and revision without misrepresenting authorship or certainty?
