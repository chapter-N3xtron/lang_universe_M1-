# Coder Report Visual Artifact

## Why

A Coder result is currently available to Jasper as a strict `TechnicalReport`, but it is not a durable visual-board artifact. A person therefore cannot inspect the technical result, changed-file counts, or code differences from the saved session’s visual board. Jasper's concise spoken explanation is useful for understanding the outcome, but it is not a substitute for the underlying technical evidence.

## What Changes

- Create one versioned `coder_report` visual artifact from Coder's validated `TechnicalReport` whenever Coder returns to Jasper.
- Include a readable technical report view and safe, bounded per-file code-diff data when it is available from the selected repository.
- Add an accessible tabbed report viewer to the existing session visual board: a technical Report tab plus selectable changed-file tabs labelled with repository-relative paths and added/removed line counts.
- Use documented libraries rather than a custom tab, tree, or diff engine: `@radix-ui/react-tabs` for tabs, `@pierre/trees/react` for the changed-file tree and built-in Git status, and `@pierre/diffs/react` for unified or side-by-side code differences.
- Keep Jasper's user-facing response as a complete plain-language, voice-friendly explanation through the existing `JasperResponse.voice_text` path. The board artifact is the inspectable technical evidence; it is never read as raw code by the speech layer.

## Non-Goals

- No new text-to-speech endpoint, audio transport, streaming protocol, graph registration, or Coder transfer topology.
- No interactive code editing, accepting/rejecting patches, committing, pushing, or source-control action from the visual board.
- No custom diff algorithm, custom tab system, new database schema, or separate artifact store.
- No silently truncated, unredacted, or fabricated code differences.
- No change to the existing React Flow concept-map renderer or its meaning.

## Capabilities

### New Capabilities

- `coder-report-visual-artifact`: Defines the durable report artifact, safe diff capture, tabbed visual-board presentation, and separation between technical evidence and Jasper's spoken walkthrough.

### Modified Capabilities

- None.

## Impact

- Backend: Coder terminal-report assembly, Jasper's existing Coder return projection, visual-artifact union, and artifact persistence through the existing session path.
- Frontend: session visual pane, a new report-artifact renderer, and two package dependencies managed with pnpm.
- Trust domain: repository source excerpts may become visible in a saved local session artifact. Capture must remain bounded, repository-relative, and redacted before persistence or browser delivery.
