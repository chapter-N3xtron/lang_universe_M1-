# Planning Statement: Agent Outputs in the Visualization Board

## 1. User-facing requirement

The user always interacts with **Jasper through chat**.

Jasper may:

- answer directly;
- call the Coder node;
- call the Librarian node;
- call the OCR node;
- use visualization tools to create a flowchart, timeline, concept map, or other visual artifact.

Specialist nodes must not become separate conversational interfaces.

When a specialist produces substantial material:

- Jasper’s chat response must contain only a concise summary, status, and useful next step.
- The complete material must be available in the visualization board.
- The user must be able to open, read, inspect, search, and later listen to that material from the board.
- The full material must not be duplicated into the chat thread merely because it was returned by a node.

Initial scope:

1. OCR output.
2. Librarian reports and research material.
3. Coder results, including code diffs and test reports.

Future scope:

- interactive React Flow boards;
- Miro-like node and edge editing;
- flowcharts;
- timelines;
- relationship maps;
- shared visual artifacts containing both written material and visual relationships.

## 2. Specific OCR requirement

The OCR pipeline now successfully processes the RUBTTI PDF, with minor recognition errors.

Current undesired behavior:

- OCR returns the full extracted PDF text directly into the Jasper chat thread.

Required behavior:

- Jasper says that OCR completed.
- Jasper reports only a bounded summary, such as the number of pages and detected disagreements.
- The complete OCR text appears in the visualization board.
- The board may also expose:
  - page boundaries;
  - rendered page images;
  - normalized OCR output;
  - Surya output;
  - GLM-OCR output;
  - disagreement details;
  - source-document metadata.

The original PDF must remain unchanged.

## 3. Current canonical repository

Repository:

```text
/Volumes/Storage/LangGraph_AgentChat_ui_Opencode_CLI-bottom-locking-runtime
```

Branch:

```text
runtime-compose
```

The runtime is deployed through the Compose stack with:

- LangGraph API;
- Agent Chat UI frontend;
- PostgreSQL;
- Redis;
- native sidecar services;
- host Ollama models for Surya and GLM-OCR.

The recent Docling dependency fix is committed as:

```text
918d080 Add GLib runtime for Docling
```

The running LangGraph image has been rebuilt and verified with:

- `libglib2.0-0`;
- `libgthread-2.0.so.0`;
- `libgl1`;
- `libxcb1`.

The actual running container imports OpenCV and Docling successfully.

## 4. Current backend architecture

### Jasper and graph orchestration

Relevant files:

```text
backend/src/chat_ui.py
backend/src/jasper_agent.py
backend/src/coding_agent.py
backend/src/librarian_agent.py
backend/src/ocr_agent.py
```

Jasper is the conversational supervisor and routes work to specialist nodes.

The outer graph state currently contains:

```text
messages
ui
visual_artifacts
jasper_structured_response
coding_status
coding_session_id
session_evidence
```

`backend/src/chat_ui.py` already uses LangGraph UI state:

```python
ui: Annotated[list[AnyUIMessage], ui_message_reducer]
```

The outer graph already has nodes for:

- Jasper;
- Coder;
- Librarian;
- OCR;
- visualization-related output;
- session recording.

### OCR

`backend/src/ocr_agent.py` currently:

1. validates the uploaded or approved document;
2. uses Docling for layout parsing and page rendering;
3. calls Surya through Ollama;
4. calls GLM-OCR through Ollama;
5. compares the two outputs;
6. writes result and manifest files;
7. returns a result dictionary.

The current leak occurs in `specialist_message()` at approximately `backend/src/ocr_agent.py:117-122`, where the message includes:

```text
Normalized result:
[full OCR text]
```

The same function also returns artifact paths, but those paths are currently filesystem paths rather than a board-native visual artifact.

### Coder

`backend/src/coding_agent.py` already uses LangGraph’s `push_ui_message()` for periodic coder progress reports.

This proves that the repository already has a supported UI-message path for specialist activity. However, current coder progress is not the same as a durable final board artifact containing:

- changed files;
- diffs;
- tests;
- generated files;
- deployment information.

### Librarian

The Librarian is the repository’s distinct research specialist. It must remain the research handoff for web and document research.

Its complete research output currently needs to be separated into:

- a concise Jasper-facing result;
- a board-facing report or evidence artifact.

No assumption should be made that the Librarian’s current output already satisfies that separation.

## 5. Current visual workspace

Relevant files:

```text
backend/src/visual_models.py
backend/src/jasper_tools.py
backend/src/session_catalog.py
backend/src/session_catalog_routes.py

agent-chat-ui/src/components/workspace/session-visual-pane.tsx
agent-chat-ui/src/components/workspace/visual-surface.tsx
agent-chat-ui/src/components/workspace/concept-map-renderer.tsx
agent-chat-ui/src/providers/Stream.tsx
agent-chat-ui/src/components/thread/artifact.tsx
```

### Existing React Flow board

React Flow/XYFlow is already present and used by:

```text
agent-chat-ui/src/components/workspace/concept-map-renderer.tsx
```

The current renderer supports a grounded concept-map artifact with:

- nodes;
- edges;
- evidence references;
- claim status;
- narration content;
- an accessible outline;
- voice narration through bounded `voice_text`.

The current visual artifact contract is defined in:

```text
backend/src/visual_models.py
```

The current envelope is `ConceptMapArtifact`, and its renderer is restricted to:

```text
renderer: "react_flow"
```

The current contract deliberately limits concept-map artifacts to bounded serialized payloads.

### Durable session artifacts

The current session catalog already includes artifact persistence and session links:

```text
backend/src/session_catalog.py
backend/src/session_catalog_routes.py
```

It supports:

- artifact identifiers;
- session association;
- artifact payloads;
- artifact listing;
- title changes;
- deletion;
- inherited session artifact references.

The frontend already loads saved artifacts through:

```text
agent-chat-ui/src/components/workspace/session-visual-pane.tsx
```

At present, that pane filters saved artifacts to `renderer === "react_flow"`.

Therefore, the repository already has a durable visual-artifact path, but it currently understands only React Flow concept maps.

## 6. Current Agent Chat UI capabilities

The upstream Agent Chat UI project provides documented artifact and generative-UI primitives:

```text
useArtifact()
ArtifactProvider
ArtifactContent
ArtifactTitle
LoadExternalComponent
uiMessageReducer
push_ui_message()
```

The upstream artifact pattern is:

```text
chat message → artifact card → side-panel content
```

The upstream artifact side panel can host arbitrary React content, including an existing React Flow component.

The upstream generative-UI path also supports:

- serializable component properties;
- custom UI components;
- UI messages associated with an assistant message;
- streaming UI updates;
- client-side component maps;
- hiding messages from the chat display.

Agent Chat UI’s documented hidden-message convention uses a message ID beginning with:

```text
do-not-render-
```

This is relevant to preventing internal or large intermediate outputs from appearing in the chat.

### Important limitation

The upstream artifact hook is primarily a presentation mechanism:

- panel state is client-side;
- mounted React component state is not automatically durable;
- the artifact hook is not itself a session artifact database;
- React Flow viewport, selection, drag state, and unsaved edits are not automatically persisted.

The repository’s existing session catalog is therefore important if board artifacts must survive reloads and session reopening.

## 7. Existing external precedents

### LangChain Open Canvas

Repository:

```text
https://github.com/langchain-ai/open-canvas
```

It demonstrates:

- chat plus a workspace;
- Markdown artifacts;
- code artifacts;
- artifact versioning;
- chat-driven updates;
- LangGraph integration.

It is useful precedent for document and code artifact behavior.

However:

- GitHub marks it archived and read-only;
- it is not a React Flow board;
- it is not a drop-in component for the current runtime;
- it does not provide the complete required OCR/research/code/session-artifact solution.

It should be studied, not adopted blindly.

### LangGraph generative UI

Official documentation:

```text
https://docs.langchain.com/langsmith/generative-ui-react
```

It documents:

- server-emitted UI components;
- `ui` state;
- `push_ui_message()`;
- streaming updates;
- `LoadExternalComponent`;
- client-provided component maps;
- updating UI components by stable ID.

This is a documented way to stream or render specialist output without creating a second transport protocol.

### LangGraph Store

Official documentation:

```text
https://docs.langchain.com/oss/python/langgraph/stores
```

LangGraph distinguishes:

- checkpointer: thread state and conversation continuity;
- Store: application-defined durable data.

The Store concept is relevant to large reports, OCR text, code results, and artifact revisions, but the repository’s existing session-catalog persistence must be compared with it before selecting a boundary.

### CopilotKit and AG-UI examples

These demonstrate agents synchronized with interactive canvases and shared frontend state.

They are relevant research references for:

- state synchronization;
- interactive cards;
- agent-driven canvas updates;
- human-in-the-loop canvas actions.

They introduce a different UI/runtime integration model and should not be selected merely because they have a canvas example.

### Other workflow builders

Projects such as Firecrawl’s Open Agent Builder demonstrate React Flow-style workflow authoring and execution status.

They are relevant for the future Miro-like workflow board, but they are not simple additions to the current LangGraph/Agent Chat UI runtime.

## 8. Known solution paths

### Path A: Upstream Agent Chat UI artifact mechanism

Use the documented Agent Chat UI artifact side panel and custom components.

```text
Jasper summary → normal chat
full specialist result → artifact component in side panel
```

Advantages:

- documented;
- already designed for chat-plus-artifact interaction;
- can host React Flow;
- supports custom components;
- avoids a new websocket or event bus.

Limitations:

- not durable by itself;
- artifact state is primarily client-side;
- not a complete session-wide board;
- large artifact storage must be handled elsewhere.

### Path B: Existing runtime visual-artifact path

Extend the current repository-native visual artifact path so that the existing board can display more than `react_flow`.

Possible existing artifact categories:

```text
react_flow
document
code_diff
research_report
ocr_report
```

This would reuse:

- current Pydantic validation;
- generated frontend schema;
- `visual_artifacts` graph state;
- session catalog;
- session artifact routes;
- existing visual pane;
- existing React Flow renderer.

This path is not a new architecture, but it does require extending the current artifact contract and adding renderers.

### Path C: Open Canvas-style artifact editor

Study and selectively reproduce Open Canvas behavior:

- Markdown/code artifact;
- versioning;
- chat-driven updates;
- artifact side panel.

This is the strongest precedent for code and document editing, but the repository is archived and cannot be treated as a maintained foundation.

### Path D: Adopt a separate canvas protocol or framework

Examples include CopilotKit/AG-UI or a dedicated collaborative canvas.

This may become relevant for full Miro-style editing, but it would be a larger architectural change and is not justified for the immediate OCR/Coder/Librarian requirement without further evidence.

## 9. Format question

The current evidence supports a pragmatic separation:

```text
Board artifact metadata → structured and validated
Report body             → Markdown or code/diff content
React Flow view         → existing nodes/edges payload
Voice layer             → explicit bounded voice text
```

Markdown is supported by the Open Canvas precedent and is suitable for:

- OCR reports;
- research reports;
- code-review reports;
- headings;
- lists;
- tables;
- citations;
- code fences.

Code diffs should preserve diff semantics rather than being flattened into ordinary Markdown. The display can still use standard diff text or a known diff-rendering component.

No conclusion has yet been established that a new custom universal JSON document AST is necessary. Further searches should specifically test whether an existing content-block, artifact, document-editor, or AG-UI format already covers the required structure.

## 10. Voice-layer requirement

Future voice playback should not scrape arbitrary HTML or read raw JSON.

The board format should preserve enough semantics for voice to:

- read headings and paragraphs in order;
- announce page boundaries;
- summarize or skip code;
- read selected diff hunks;
- identify citations;
- describe OCR disagreements;
- describe React Flow nodes and edges;
- let the user select a block or section to hear.

The current repository already establishes an important boundary:

```text
TTS receives voice_text.
TTS does not read serialized diagrams, tool traces, or visual formatting.
```

Any future board solution must preserve that boundary.

## 11. Required acceptance behavior

A successful implementation should demonstrate:

### OCR

- PDF processing completes.
- Chat contains no full extracted PDF body.
- Board contains the complete OCR result.
- Page/source/disagreement metadata remains available.
- Board content survives thread reload.

### Librarian

- Chat contains only a concise research completion summary.
- Full report appears in the board.
- Sources, citations, limitations, and provenance remain inspectable.
- Research output is not confused with user-authored conclusions.

### Coder

- Chat contains only a concise completion summary.
- Board contains changed files, diffs, tests, and relevant generated-file references.
- Added, removed, and unchanged lines remain distinguishable.
- Large code output does not flood the chat.

### Existing React Flow

- Current concept maps continue to render.
- Existing saved artifacts remain readable.
- Future board editing can extend the same artifact identity and revision model.
- Board selection and layout remain user-controlled.
- No agent silently changes focus or board layout merely because an artifact was generated.

### Persistence and safety

- Full bodies are not stored in unbounded chat messages or checkpoints.
- Artifact IDs, revisions, source references, digests, and producer identity are retained.
- Secrets, credentials, unsafe tool traces, and chain-of-thought are excluded.
- Existing session deletion and rename behavior remains truthful.
- No second custom transport is introduced unless documented framework capabilities are proven insufficient.

## 12. Questions for further searches

Further research should focus on finding an existing implementation for:

1. Agent Chat UI artifact cards that open durable document/code workspaces.
2. LangGraph `ui` messages carrying large or streamed document artifacts.
3. Open Canvas’s exact artifact and version data model.
4. Existing React Flow document/code/report canvas projects that already support artifact persistence.
5. AG-UI or other established protocols for agent-to-canvas updates.
6. Existing voice/accessibility patterns for Markdown, code diffs, and node graphs.
7. Whether the current Agent Chat UI artifact mechanism can be connected to the existing session catalog without replacing either.
8. Whether a maintained document editor or diff viewer can be embedded directly into the current visual pane.

## Current non-conclusion

The evidence currently supports reusing:

- LangGraph state and UI-message streaming;
- Agent Chat UI artifact components;
- the runtime’s existing session catalog;
- the existing React Flow renderer;
- Markdown/code artifact patterns from Open Canvas.

It does **not** yet justify designing a new universal board protocol, a new persistence layer, a new event bus, or a new Miro-like canvas framework. Further investigation should identify the smallest combination of existing implementations that can be composed without replacing the current runtime.
