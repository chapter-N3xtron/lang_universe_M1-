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
| `updated_by` | string | What agent last modified the file. Use `"opencode-desktop"`. |
| `sections` | array[Section] | Ordered list of plan sections. |

### Section

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique kebab-case identifier for the section. |
| `title` | string | Human-readable section title. |
| `created_at` | string (ISO-8601) | When this section was created. Set once, never changed. |
| `planned_by_model` | string | Full model ID that authored this plan section (e.g. `"ollama-cloud/glm-5.2"`, `"ollama/qwen3:32b"`, `"anthropic/claude-sonnet-4.5"`). Set once, never modified. |
| `planned_by_agent` | string | Agent that created the section. Always `"opencode-desktop"`. |
| `todos` | array[Todo] | The individual todo items in this section. |

### Todo

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique kebab-case identifier. |
| `content` | string | What needs to be done. |
| `status` | string | One of `"pending"`, `"in_progress"`, `"completed"`. |
| `agent` | string or null | Responsible agent: `"coding"`, `"jasper"`, `"research"`, `"magic-coder"`, or `null`. Historical completed entries may retain legacy values for audit integrity. |
| `completed_by_model` | string or null | Full model ID that completed this todo. Set when status changes to `"completed"`. Never set for pending items. |
| `completed_at` | string (ISO-8601) or null | When the todo was completed. Set with `completed_by_model`. |
| `notes` | string | Brief summary of what was done or relevant context. |

## Rules

### Adding a new plan section

When you create a new set of related todos:

1. Append a new object to `sections[]`.
2. Set `planned_by_model` to your current full model ID (e.g. `"ollama-cloud/glm-5.2"`).
3. Set `planned_by_agent` to `"opencode-desktop"`.
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

### Never

- Delete a completed todo (preserve the audit trail).
- Modify `planned_by_model` after section creation.
- Reorder completed todos above pending ones.
- Edit `todos.json` for any purpose other than task tracking.

## Worked example

### Adding a section

Initial state of a new section:

```json
{
  "version": 1,
  "updated_at": "2026-07-27T22:05:00Z",
  "updated_by": "opencode-desktop",
  "sections": [
    {
      "id": "my-new-plan",
      "title": "My New Plan",
      "created_at": "2026-07-27T22:05:00Z",
      "planned_by_model": "ollama-cloud/glm-5.2",
      "planned_by_agent": "opencode-desktop",
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
  "updated_by": "opencode-desktop",
  "sections": [
    {
      "id": "my-new-plan",
      "title": "My New Plan",
      "created_at": "2026-07-27T22:05:00Z",
      "planned_by_model": "ollama-cloud/glm-5.2",
      "planned_by_agent": "opencode-desktop",
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
