## Context

The OCR specialist currently converts a PDF with Docling and renders page images for downstream OCR. It does not preserve selected page or picture images beside a workspace PDF, and the visual workspace accepts only validated `react_flow` concept-map artifacts. The browser cannot safely render a native host path, and the existing visual-artifact contract has a 256 KiB serialized limit that rules out embedded page images.

Docling's documented PDF pipeline can retain page and picture images with `PdfPipelineOptions.generate_page_images`, `generate_picture_images`, and `images_scale`. Its `DoclingDocument` also retains ordered document elements and provenance such as source pages and bounding boxes. That structure, not an OCR-model prompt, is the authority for harvest decisions and relationships.

## Goals

- Preserve useful source visuals without changing or degrading the source PDF.
- Keep Docling authoritative for page, element, caption, and layout relationships.
- Make each harvested image auditable against its source page and Docling metadata.
- Keep repository writes inside the typed Custodian boundary.
- Permit a later visual workspace renderer without exposing host paths or placing binary data in model context.
- Prefer the simplest reliable artifact—a full source-page image—before adding cropping or chart interpretation.

## Decisions

### 1. Docling controls selection and provenance

Harvest eligibility comes from the converted `DoclingDocument`: page membership, element type, caption association, bounding box, and reading order. OCR and vision models may not create, reorder, merge, or relocate visual elements. A model-derived description, if added in a later change, is annotation only and cannot become layout authority.

The lossless Docling representation and extraction manifest remain available for auditing. If Docling identifies a visual element but a safe crop cannot be produced, the system preserves the complete source page rather than guessing a crop.

### 2. Full pages are the first supported image unit

The first implementation preserves one rendered PNG for each source page selected by Docling as containing relevant visual material. This keeps captions, axes, legends, and nearby explanatory text in context and avoids crop-boundary mistakes. Duplicate requests for the same source page reuse one content-addressed image.

Element crops are a later optimization. A crop must retain a link to its full-page artifact and source bounding box; it must not be the only preserved evidence.

### 3. Workspace output stays within Custodian

For a repository-bound source PDF, Custodian creates or updates a sibling directory named `<pdf-stem>.ocr-assets/`. Suggested names are `page-0001.png` and a machine-readable manifest. Paths are derived from the source PDF and validated inside the selected repository. Writes are bounded and atomic. The original PDF is never a mutation target.

OCR Markdown uses image references resolved from the Markdown file's parent directory, and the manifest records that path base, so the text and sibling asset directory remain portable together. Browser-only uploads have no repository destination; their harvested assets remain in bounded Agent Server artifact storage.

### 4. Visual delivery uses an opaque asset reference

A future visual artifact uses a new validated renderer discriminator such as `document_image`. Its JSON contains only bounded metadata: artifact ID, title, alt text, source page, media type, dimensions, content hash, and an opaque asset ID. An authenticated Agent Server route resolves that asset ID and streams the image after session/owner authorization.

The artifact must not contain a host path, `file://` URL, any `data:` URI, credential, authorization header, or embedded image bytes. The asset route serves only an explicit safe raster-media allowlist with content-type enforcement and `X-Content-Type-Options: nosniff`. Repository copies and session visual artifacts have separate lifecycle and ownership even when they derive from the same page.

### 5. Accessibility does not depend on speculative interpretation

Every image artifact has useful alt text. Initially that text may identify the source document, page number, and Docling element/caption metadata. It must not present an unverified model description as observed fact. Chart or diagram interpretation requires a later explicit enrichment contract with provenance and uncertainty.

### 6. Text-plus-image composition is deferred

The first visual renderer displays one page image with source metadata and an accessible caption. Combining OCR text regions, selectable overlays, synchronized highlights, or multiple images into a composed Visboard document is a later phase. The data contract should retain page and element identifiers so that phase does not require re-OCR.

## Relationship to visualization-board-alignment

`visualization-board-alignment` documents today's concept-map renderer and future board editing while intentionally retaining response version 2 and avoiding schema changes. Document images must not be inserted into that contract as if already supported. Before implementation, this change must coordinate a schema/version decision, generated client types, session validation, renderer selection, and lifecycle behavior with that existing change.

## Risks and controls

- **Large documents:** enforce configurable page-count, pixel, encoded-byte, per-run, and retained-storage bounds before durable writes.
- **Private document exposure:** require owner/session authorization for every visual asset response and use opaque identifiers.
- **Docling detection errors:** preserve the full page and metadata; do not use a model prompt to invent crop or layout decisions.
- **Artifact drift:** record source PDF hash, Docling metadata, converter/model versions, and image hash.
- **Lifecycle confusion:** clearly report whether an image exists in the repository, session artifact storage, or both.

## Open decisions before implementation

1. The visual response schema/version migration and backward-compatible renderer union.
2. The authenticated asset store, opaque identifier format, retention policy, and deletion behavior.
3. Exact limits for pages, dimensions, encoded bytes, per-run assets, and retained storage.
4. Whether harvest is automatic for Docling picture/table labels, explicitly requested, or both.
5. The initial set of Docling labels that qualify a page for harvest.
6. Custodian collision/revision behavior for an existing `.ocr-assets` directory.
7. When element crops become eligible and how crop quality is validated.
8. The later text-plus-image composition and whether OCR text is rendered as an overlay, adjacent panel, or linked artifact.
