# Document Image Harvest

## Why

Docling can identify pages, pictures, tables, charts, diagrams, captions, and their positions, but the OCR path does not yet preserve those visual regions as durable workspace or visual-session artifacts. Adding this directly tonight would combine document conversion, binary artifact storage, authenticated delivery, schema evolution, and a new visual renderer in one debugging session. The work needs a bounded specification so it can be implemented later without weakening Docling's layout authority or derailing the current text-layout correction.

## What Changes

- Define Docling as the authority for deciding which source page and document elements contain pictures, charts, diagrams, tables, or other visual material.
- Preserve a full rendered source page as the initial reliable harvest unit. Element crops may be added later when Docling supplies a trustworthy bounding box, but a crop must not replace the contextual page artifact.
- Write workspace copies through a typed Custodian action into a sibling `<pdf-stem>.ocr-assets/` directory while leaving the source PDF unchanged.
- Record source page number, Docling element identifiers and labels, bounding boxes when available, captions, content hashes, media type, and derivation metadata in the OCR manifest.
- Reference harvested images using paths resolved relative to the sibling OCR Markdown file, with the path base recorded in the manifest.
- Define a future validated `document_image` visual artifact that uses an opaque authenticated asset reference rather than a host path or embedded base64 payload.
- Preserve the distinction between repository outputs and session-owned visual artifacts described in `openspec/TERMINOLOGY.md`.
- Defer text-plus-image Visboard composition, chart interpretation, and visual-language-model descriptions until the image artifact boundary is implemented and tested.

## Capabilities

### New Capabilities

- `document-image-harvest`: Docling-directed preservation, workspace delivery, provenance, and future visual-session presentation of document page images.

### Related Existing Changes

- `visualization-board-alignment`: Defines the current `react_flow` concept-map surface and explicitly does not change its response schema. This change is separate because document images require a new validated artifact contract, authenticated binary delivery, and renderer. It must preserve that change's session, provenance, accessibility, and human-control boundaries.

## Impact

Later implementation will affect the Docling conversion configuration, OCR manifest and Markdown output, typed Custodian actions, bounded binary artifact storage, authenticated Agent Server routes, the authoritative visual response schema and generated TypeScript types, session artifact validation, and the visual workspace renderer. It will require focused backend and frontend tests and a compatibility decision for the visual response schema version.

## Non-goals

- Do not interpret, summarize, or reconstruct chart data automatically.
- Do not use OCR or vision-model prompts to decide document layout or image ownership.
- Do not expose host filesystem paths to the browser.
- Do not embed large image payloads in LangGraph state, chat messages, checkpoints, or visual-artifact JSON.
- Do not implement text-plus-image Visboard composition as part of the current Docling-authoritative text-layout correction.
