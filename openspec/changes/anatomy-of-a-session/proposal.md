## Why

The project needs a shared, human-centered definition of a session so accumulated inquiry materials remain understandable as one body of work rather than an undifferentiated chat history. A durable, user-authored Perspective is needed to preserve and revisit the user's evolving understanding without treating model synthesis or political recommendations as the user's stance.

## What Changes

- Define a session as an Inquiry-oriented body of work that groups its inquiry materials and durable records.
- Define the session artifact categories: visualizations/charts, PDFs, research outputs (links, saved pages, reports, and research-pass reports), polls, and a durable user-authored Perspective.
- Specify Perspective as the user's current understanding, conclusion, decision, or stance based on assembled materials; it can be revisited and updated as the inquiry develops.
- Establish provenance, user-authorship, and non-prescription boundaries so the system does not misattribute generated content to the user or prescribe political conclusions.
- Describe learning, dense-text/scientific inquiry, social or political perspective formation, voting considerations, and decision-tool outputs as illustrative uses rather than mandated outcomes or workflows.
- Define revisitation of a saved session/thread as initially showing the latest hydrated content once, with the viewport behavior kept distinct from new-arrival top anchoring and without inventing durable viewport-position storage.

## Capabilities

### New Capabilities

- `session-anatomy`: Defines the Inquiry-oriented session, its recognized artifact categories, and the durable user-authored Perspective record and boundaries.

### Modified Capabilities

- None. The repository has no existing main OpenSpec capability specifications.

## Impact

- Adds planning artifacts only under `openspec/changes/anatomy-of-a-session/`; no implementation code, API, dependency, persistence migration, or UI behavior is authorized by this change.
- Future session, artifact, research, visualization, polling, and decision-support work must preserve human authorship, provenance, revisability, and user control. Governance reference: `GOVERNANCE_FRAMEWORK.md`.

## Terminology boundary

A session is valid even when it has no repository-path binding. When a binding exists,
existing `workspace_id` values identify the durable repository binding and are not
visual UI workspace IDs. Artifacts belong to their producing thread/session rather
than to that binding. Visual workspace means only Chat/Split/Visual presentation and
browser-local layout state. See `openspec/TERMINOLOGY.md`.
