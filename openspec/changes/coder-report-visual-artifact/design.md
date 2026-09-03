## Context

Phase 6 established `TechnicalReport` as the strict, authoritative Coder-to-Jasper handoff. The existing session persistence path already stores `visual_artifacts` generically in LangGraph Store and the application-owned PostgreSQL session projection. The present visual schema and UI only recognize `react_flow` concept-map artifacts, so Coder reports are neither persisted as board artifacts nor rendered there.

The product boundary is deliberate: Coder produces the technical evidence; the visual board lets the person inspect it; Jasper explains the complete result in plain language suitable for the existing speech path.

## Decisions

### 1. Create one deterministic report artifact from the validated Coder report

After Coder has assembled and validated a terminal `TechnicalReport`, the existing post-Coder Jasper return creates a `coder_report` artifact without asking a model to restate, summarize, or invent report data. The artifact retains the validated report fields required for technical review and has its own literal artifact version.

The existing `TechnicalReport` remains the Coder-to-Jasper authority. The artifact is a durable presentation record derived from it, not a replacement report protocol.

### 2. Capture diffs as safe bounded evidence, not as model prose

A real code diff requires source content from before and after the run. The capture adapter obtains it only from the explicitly selected repository and only after Coder's terminal result. It records repository-relative paths, change type, and added/removed line counts. When safe before/after content or a patch is available, it is attached as a per-file diff record for the visual artifact.

The adapter must redact secret-like values using the existing sensitive-output boundary before the artifact is persisted. It must not fabricate unavailable source. A file that is binary, unavailable, redacted, or excluded by the artifact size budget remains listed with an explicit availability reason instead of a fake or silently incomplete diff.

The existing 256 KiB serialized visual-artifact ceiling remains authoritative. Capture must select bounded material diffs before persistence, report any omitted diff in the technical report artifact, and preserve changed-file metadata even when full patch content cannot be included.

### 3. Reuse Radix Tabs and Pierre Diffs

Install `@radix-ui/react-tabs` through pnpm for the report artifact's tab system. It supplies accessible `Root`, `List`, `Trigger`, and `Content` primitives with documented keyboard support. The UI uses it for a Report tab and changed-file tabs; it does not create a tab widget from scratch.

Install `@pierre/diffs` through pnpm and import its React components from `@pierre/diffs/react`. Its documented `Virtualizer` and diff/file components render the selected bounded diff with line numbers, syntax highlighting, folding, wrapping, and unified or split presentation. It performs the presentation; the backend remains responsible for truthful diff data and limits.

A changed-file trigger displays the repository-relative path and `−removed +added` counts. It activates that file's diff tab. The Report tab displays Coder's technical result: outcome, task notes, changed-file list, typed validation evidence, blockers, remaining authorization needs, and material risks. Jasper's prose does not replace this content.

Install `@pierre/trees` through pnpm and use its documented React `FileTree` and `useFileTree` APIs on the initial Report tab. Supply the artifact's canonical changed-file paths and built-in `gitStatus` records. Selecting a tree path activates the same file's existing diff tab. The tree remains read-only: no renaming, drag-and-drop, context menu, or repository mutation capability is enabled.

### 4. Extend the visual-artifact union and dispatch, leaving React Flow intact

Add a discriminated `coder_report` artifact type alongside the existing `react_flow` concept map. The session visual pane validates artifacts through the same `JasperResponse` contract, includes both renderer types in its timeline, and dispatches each selected artifact to its own renderer.

React Flow continues rendering concept maps. The Coder report uses the existing visual-pane surface as a normal React component, not as a React Flow node or a new graph engine.

### 5. Preserve a clear review and speech boundary

The report artifact is technical and may contain code excerpts. Jasper's `voice_text` remains a maximum-two-paragraph plain-language walkthrough of the report outcome, work, evidence, blockers, authorization needs, and risks. Raw patches, code blocks, tab labels, and detailed file lists do not enter speech output.

## Risks and mitigations

- [Sensitive source text is persisted in an artifact] → Collect only selected-repository diffs, redact before storage, keep the existing artifact ceiling, and mark unavailable files rather than bypassing safety limits.
- [Large reports make the board unresponsive] → Use `@pierre/diffs/react` virtualization, render only the active diff tab, and retain bounded artifact data.
- [A later UI change breaks old saved reports] → Include a literal artifact version and keep compatible renderers for supported versions; reject unsupported versions visibly without treating data as a diff.
- [A source-test result is mistaken for deployed behavior] → Reuse typed validation evidence and clearly label source, runtime, and deployment checks separately in both report and Jasper output.
- [The browser becomes an execution or review-approval surface] → Keep the board read-only; no patch acceptance, workspace mutation, Git operation, or authority change is included.

## Documentation basis

- Radix Tabs: https://www.radix-ui.com/primitives/docs/components/tabs
- Pierre Diffs: https://diffs.com/docs
- React Flow custom-node and component model: https://reactflow.dev/learn/customization/custom-nodes
- LangChain structured output: https://docs.langchain.com/oss/python/langchain/structured-output
