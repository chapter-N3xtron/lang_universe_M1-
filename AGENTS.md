# Agent Protocol — Todo List

## Location

- Master file: `todos.json` (in the same directory as this file — repo root).
- This is the single source of truth for project task tracking.

## Schema

The file is a JSON object with this structure:

| Field | Type | Description |
|-------|------|-------------|
| `version` | integer | Schema version (currently 1). Always `1`. |
| `updated_at` | string (ISO-8601) | Last modification timestamp. Bump on every write. |
| `updated_by` | string | What agent last modified the file. Use `"deep-agent"`. |
| `sections` | array[Section] | Ordered list of plan sections. |

### Section

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique kebab-case identifier for the section. |
| `title` | string | Human-readable section title. |
| `created_at` | string (ISO-8601) | When this section was created. Set once, never changed. |
| `planned_by_model` | string | Full model ID that authored this plan section (e.g. `"ollama-cloud/glm-5.2"`, `"ollama/qwen3:32b"`, `"anthropic/claude-sonnet-4.5"`). Set once, never modified. |
| `planned_by_agent` | string | Agent that created the section. Always `"deep-agent"`. |
| `todos` | array[Todo] | The individual todo items in this section. |

### Todo

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique kebab-case identifier. |
| `content` | string | What needs to be done. |
| `status` | string | One of `"pending"`, `"in_progress"`, `"completed"`, `"superseded"`. |
| `agent` | string or null | Responsible agent: `"coding"` (Deep Agent), `"jasper"`, `"research"`, `"magic-coder"`, or `null`. Historical completed entries may retain legacy values for audit integrity. |
| `completed_by_model` | string or null | Full model ID that completed this todo. Set only when status changes to `"completed"`. Keep `null` for pending and superseded items. |
| `completed_at` | string (ISO-8601) or null | When the todo was completed. Set with `completed_by_model`; keep `null` when superseded. |
| `notes` | string | Brief summary of what was done or relevant context. |

## Rules

### Adding a new plan section

When you create a new set of related todos:

1. Append a new object to `sections[]`.
2. Set `planned_by_model` to your current full model ID (e.g. `"ollama-cloud/glm-5.2"`).
3. Set `planned_by_agent` to `"deep-agent"`.
4. Generate a unique kebab-case `id` and an ISO-8601 `created_at` timestamp.
5. Every todo starts as `status: "pending"`, `completed_by_model: null`, `completed_at: null`.

### Completing a todo

When you finish work on a todo:

1. Set `status` to `"completed"`.
2. Set `completed_by_model` to your current full model ID.
3. Set `completed_at` to the current ISO-8601 timestamp.
4. Update `notes` with a brief summary of what was done.
5. Bump top-level `updated_at` and `updated_by`.

### Marking a todo in_progress

1. Set `status` to `"in_progress"`.
2. Bump top-level `updated_at`.

### Superseding a todo

Use `superseded` only when a pending or in-progress task has been replaced by a newer task or architecture and should not be implemented as written.

1. Set `status` to `"superseded"`.
2. Set `agent`, `completed_by_model`, and `completed_at` to `null`.
3. Update `notes` with the reason, date, and IDs of the replacement tasks or sections.
4. Bump top-level `updated_at` and `updated_by`.

### Never

- Delete a completed todo (preserve the audit trail).
- Mark completed work as superseded; supersession applies only to unfinished work.
- Modify `planned_by_model` after section creation.
- Reorder completed todos above pending ones.
- Edit `todos.json` for any purpose other than task tracking.

### Governance linkage

`GOVERNANCE_FRAMEWORK.md` is the working governance draft. Any pending or
in-progress todo involving human intent, attention, consent, authorization, memory,
session focus, interrupts, communication behavior, engagement, accessibility,
voice/visual attention, curated reasoning sources, care boundaries, or governance
auditing must include `Governance reference: GOVERNANCE_FRAMEWORK.md.` in its
`content` or `notes`.

When stable governance rule IDs exist, include the applicable IDs alongside the
document reference. The working draft is not the ratified constitution; referencing
it creates an editorial and implementation review obligation but does not grant the
model authority to adopt unresolved proposals.

## Worked example

### Adding a section

Initial state of a new section:

```json
{
  "version": 1,
  "updated_at": "2026-07-27T22:05:00Z",
  "updated_by": "deep-agent",
  "sections": [
    {
      "id": "my-new-plan",
      "title": "My New Plan",
      "created_at": "2026-07-27T22:05:00Z",
      "planned_by_model": "ollama-cloud/glm-5.2",
      "planned_by_agent": "deep-agent",
      "todos": [
        {
          "id": "do-something",
          "content": "Do something important",
          "status": "pending",
          "agent": "coding",
          "completed_by_model": null,
          "completed_at": null,
          "notes": ""
        },
        {
          "id": "do-something-else",
          "content": "Do something else",
          "status": "pending",
          "agent": "jasper",
          "completed_by_model": null,
          "completed_at": null,
          "notes": ""
        }
      ]
    }
  ]
}
```

### Completing a todo

After completing "do-something":

```json
{
  "version": 1,
  "updated_at": "2026-07-27T23:00:00Z",
  "updated_by": "deep-agent",
  "sections": [
    {
      "id": "my-new-plan",
      "title": "My New Plan",
      "created_at": "2026-07-27T22:05:00Z",
      "planned_by_model": "ollama-cloud/glm-5.2",
      "planned_by_agent": "deep-agent",
      "todos": [
        {
          "id": "do-something",
          "content": "Do something important",
          "status": "completed",
          "agent": "coding",
          "completed_by_model": "ollama-cloud/glm-5.2",
          "completed_at": "2026-07-27T23:00:00Z",
          "notes": "Implemented the feature"
        },
        {
          "id": "do-something-else",
          "content": "Do something else",
          "status": "pending",
          "agent": "jasper",
          "completed_by_model": null,
          "completed_at": null,
          "notes": ""
        }
      ]
    }
  ]
}
```
