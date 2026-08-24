## 1. Contract and fixtures

- [ ] 1.1 Confirm the installed Docling version and document the supported page-image, picture-image, element-iteration, caption, and provenance APIs.
- [ ] 1.2 Decide the bounded harvest policy, qualifying Docling labels, page/image limits, retention rules, and automatic-versus-explicit trigger.
- [ ] 1.3 Add representative fixtures for scanned pages, scientific multi-column pages, charts, diagrams, tables, captions, and pages without visual elements.

## 2. Docling-directed harvest

- [ ] 2.1 Configure page-image retention through documented `PdfPipelineOptions` without introducing document-specific layout rules.
- [ ] 2.2 Produce a lossless manifest linking each harvested page image to the source PDF hash, page number, Docling element IDs/labels, captions, bounding boxes, reading order, converter version, dimensions, media type, and image hash.
- [ ] 2.3 Preserve a full-page fallback whenever an eligible visual element cannot be cropped safely; defer element-only cropping until separately validated.
- [ ] 2.4 Reference workspace images from OCR Markdown without allowing OCR or vision models to alter Docling's structural relationships.

## 3. Bounded workspace assets

- [ ] 3.1 Define and implement a typed Custodian action that writes harvested images and their manifest into `<pdf-stem>.ocr-assets/` beside a repository-bound PDF.
- [ ] 3.2 Enforce repository confinement, source-PDF immutability, atomic writes, collision/revision handling, binary and aggregate size limits, and refusal of protected paths.
- [ ] 3.3 Keep browser-only upload assets inside bounded Agent Server artifact storage when no repository binding exists.

## 4. Future document-image visual artifact

- [ ] 4.1 Resolve the visual response schema/version decision and add a validated `document_image` artifact containing bounded metadata and an opaque asset ID only.
- [ ] 4.2 Add owner/session-authorized binary asset storage and an authenticated streaming route; reject every `data:` URI and native host path, allowlist safe raster media types, enforce response content types with `nosniff`, and never embed image bytes in artifact JSON.
- [ ] 4.3 Extend generated client types, validators, session artifact handling, and renderer dispatch without changing existing `react_flow` behavior.
- [ ] 4.4 Add an accessible page-image renderer with alt text, source page metadata, loading/error states, and bounded display behavior.

## 5. Focused validation

- [ ] 5.1 Verify Docling alone determines visual/page relationships and that downstream models cannot reorder, merge, or invent harvested elements.
- [ ] 5.2 Verify repository images and manifests are written beside the source PDF while the PDF remains byte-for-byte unchanged.
- [ ] 5.3 Verify authentication, owner/session isolation, opaque references, size/count limits, retention, deletion, and missing/stale asset behavior.
- [ ] 5.4 Verify old `react_flow` session artifacts remain valid and render unchanged across the schema/version transition.

## 6. Deferred text-plus-image composition

- [ ] 6.1 Specify, in a later compatibility-reviewed change, how Docling-ordered OCR text and document images coexist in Visboard without re-running OCR or weakening provenance.
