# LangChain Visual Workspace Architecture

Status: accepted for implementation (2026-07-30)

## Product invariant

Chat and visual content are equal, first-class surfaces. The user controls which
surface is foregrounded. An agent may return a layout suggestion, but it may not
change focus, panel order, panel size, or the saved layout.

Voice is independent of layout. TTS receives only `voice_text`; it never reads
serialized diagrams, chart data, tool traces, or visual formatting.

## Framework boundaries

- LangGraph remains the outer supervisor, durable thread, checkpoint, interrupt,
  and streaming runtime.
- LangChain `create_agent` owns Jasper's model/tool loop, middleware, structured
  response validation, retry behavior, and provider strategy.
- Pydantic is the backend source of truth for response and artifact schemas.
- Pydantic JSON Schema is committed and generates frontend TypeScript. Generated
  files are never edited by hand; drift is a test failure.
- LangGraph state and the existing `useStream` connection transport artifacts.
  No second WebSocket, SSE endpoint, or custom artifact event bus is permitted.
- React owns layout. Resizing and persistence use a maintained panel library.
- Renderers consume validated payloads. React Flow renders concept and code maps;
  later renderers may add Plotly charts and trusted architecture images.

LangChain's structured-output and generative-UI patterns are reused rather than
reimplemented. Renderer-specific interaction state (zoom, selection, viewport)
stays in the browser and is not model-generated.

## Canonical response

Every structured Jasper completion has:

- `version`: schema version (`1` for this release).
- `voice_text`: concise natural language suitable for speech and ordinary chat.
- `artifacts`: zero or more discriminated visual artifacts.
- `layout_suggestion`: optional, advisory metadata shown as a user action.
- `diagnostic`: optional typed, non-secret fallback information.

The first renderer is `react_flow`. Its payload contains bounded nodes and edges,
stable IDs, accessible labels, and no executable content. The artifact envelope
contains an opaque ID, title, plain-text alternative, and optional source message
ID. Presentation state is deliberately absent.

## Provider strategy

The response path is selected deterministically:

1. Provider-native structured output, only when the LangChain model profile or a
   verified local override says native structured output and tools can coexist.
2. LangChain `ToolStrategy`, only when combined tool calling is verified.
3. Two pass: a normal tool-capable agent gathers evidence, then a tool-free model
   call formats the result with `with_structured_output`.
4. Safe text only: preserve a useful assistant message, return no artifacts, and
   attach a typed diagnostic if structured validation still fails.

There is no heuristic parsing of malformed JSON and no silent strategy change.
Model profile data is preferred. A small explicit override table may correct
missing or stale capability data for models that have passed the repository test
matrix. Overrides never contain credentials.

## Safety and resource limits

- Strict Pydantic models reject unknown fields.
- Concept maps are limited to 100 nodes, 200 edges, 120 characters per label,
  2,000 characters per node detail, and 256 KiB serialized per artifact.
- Node IDs must be unique; every edge endpoint must exist.
- URLs, HTML, JavaScript, event handlers, CSS, and arbitrary component names are
  not accepted in concept-map payloads.
- Backend tools retain the existing workspace confinement and secret-file rules.
- Renderers never use `dangerouslySetInnerHTML` for model output.
- Diagnostics expose categories and recovery guidance, not prompts, credentials,
  raw provider exceptions, tool arguments, or tool output.

## Workspace behavior

Supported layouts are `chat`, `visual`, `split`, and `compact_chat`. The user can
focus either surface, swap sides, resize panels, and restore defaults. Layout is
stored per LangGraph thread in local browser storage; malformed persisted state is
discarded. An agent suggestion appears as an explicit action and never auto-runs.

On narrow screens, surfaces become tabs rather than unusably small columns.
Changing layout must preserve renderer viewport, selection, chat scroll position,
and in-progress voice playback.

## Accessibility

- All layout operations are keyboard reachable and have visible focus states.
- Resize separators expose correct semantics and practical pointer targets.
- Every artifact has a title and plain-text alternative.
- Concept-map nodes are available in a navigable textual outline in addition to
  the canvas.
- Reduced-motion preferences disable layout animation.
- Layout suggestions are announced without stealing focus.

## Release gate

The first release is one production vertical slice: Jasper can choose or directly
produce a concept map, LangChain validates the response, LangGraph persists and
streams it, React Flow renders it, the user controls the workspace, and TTS speaks
only `voice_text`.

It must pass schema round-trip and drift tests, provider-strategy unit tests,
malformed-output recovery, outer-graph persistence/reconnect tests, workspace UI
and keyboard tests, payload-limit tests, TypeScript, an optimized build, and the
existing long-thread performance budgets. Plotly, Tree-sitter, issue-list, and
architecture renderers are out of scope until this gate passes.
