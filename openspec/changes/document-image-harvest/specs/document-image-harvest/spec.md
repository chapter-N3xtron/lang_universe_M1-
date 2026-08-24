## Purpose

Define Docling-directed preservation of document page images, bounded repository delivery through Custodian, and the future secure presentation of those images as visual-session artifacts without weakening layout authority or exposing host paths.

## ADDED Requirements

### Requirement: Docling is authoritative for visual harvest relationships

The system SHALL derive source page membership, visual element type, captions, bounding boxes when available, and reading-order relationships from the converted `DoclingDocument`. OCR and vision models SHALL NOT create, reorder, merge, relocate, or suppress those structural relationships. Model output MAY be retained as separately identified annotation but SHALL NOT become layout authority.

#### Scenario: Docling identifies visual material on a page

- **WHEN** Docling identifies a picture, chart, diagram, table, or other configured visual element on a source page
- **THEN** the harvest record SHALL cite that source page and the available Docling identifiers, labels, captions, bounding boxes, and ordering metadata without asking an OCR or vision-model prompt to decide the layout

#### Scenario: A downstream model disagrees with structure

- **WHEN** a downstream model emits text or a description in an order or grouping inconsistent with Docling
- **THEN** the system SHALL retain Docling's structure, SHALL NOT apply the model's structural change, and MAY record the disagreement as bounded diagnostic metadata

### Requirement: Full-page preservation is the reliable initial artifact

The first supported harvest implementation SHALL preserve a complete rendered image of each eligible source page. A later element crop MAY supplement the full page only when it is derived from Docling provenance and remains linked to the complete page. Failure to produce a trustworthy crop SHALL fall back to the full page without a guessed boundary.

#### Scenario: Eligible page contains a diagram and caption

- **WHEN** a source page contains configured visual material
- **THEN** one bounded full-page image SHALL preserve the diagram, caption, and surrounding context and SHALL be linked to that source page in the manifest

#### Scenario: Element crop is unavailable or uncertain

- **WHEN** Docling lacks a usable bounding box or crop generation fails validation
- **THEN** the complete page image SHALL remain the harvested evidence and no model-generated crop boundary SHALL be substituted

### Requirement: Repository outputs use the Custodian boundary

For a repository-bound source PDF, harvested page images and their manifest SHALL be written through a typed Custodian action to a sibling `<pdf-stem>.ocr-assets/` directory. The action SHALL derive and validate its destination from the source PDF, remain inside the selected repository, apply bounded atomic writes and collision policy, refuse protected paths, and leave the source PDF unchanged.

#### Scenario: Repository PDF produces a page image

- **WHEN** OCR harvests an eligible page from a repository-bound PDF
- **THEN** Custodian SHALL write the image and manifest beside the PDF under `<pdf-stem>.ocr-assets/`, return references resolved relative to the sibling OCR output, and preserve the PDF byte-for-byte

#### Scenario: Source has no repository binding

- **WHEN** the source is a browser-only upload with no repository destination
- **THEN** the system SHALL keep harvested images in bounded Agent Server artifact storage and SHALL NOT infer or invent a host output directory

### Requirement: OCR output references preserved page images

OCR Markdown and its manifest SHALL reference harvested workspace page images by a portable path resolved from the OCR Markdown file's parent directory when such images exist, and the manifest SHALL declare that path base. The manifest SHALL include source PDF hash, source page number, Docling provenance, converter version, image dimensions, media type, content hash, and whether the artifact is a complete page or supplemental crop.

#### Scenario: Text and image outputs are reopened together

- **WHEN** a person opens the OCR Markdown beside its `.ocr-assets` directory
- **THEN** each image reference SHALL resolve relative to the OCR output and its manifest SHALL identify the exact source page and derivation metadata without requiring a new OCR run

### Requirement: Document-image visual artifacts use authenticated opaque references

A future document-image visual artifact SHALL contain bounded metadata and an opaque asset identifier rather than image bytes or a native filesystem path. The browser SHALL retrieve the image only through an authenticated Agent Server route that verifies the applicable owner and session boundary. The artifact contract SHALL provide title, alt text, source page, media type, dimensions, and content hash.

#### Scenario: Visual workspace displays a harvested page

- **WHEN** a valid session-owned `document_image` artifact is selected
- **THEN** the visual workspace SHALL retrieve its image through the authenticated opaque reference and render it with useful alt text and source-page context

#### Scenario: Artifact contains an unsafe reference

- **WHEN** a proposed document-image artifact contains a host path, `file://` URL, any `data:` URI, credential, authorization header, or embedded image bytes
- **THEN** validation SHALL reject the artifact and the protected value SHALL not be shown, persisted, logged, or sent to the browser; authenticated delivery SHALL allowlist safe raster media types, enforce the matching response content type, and send `X-Content-Type-Options: nosniff`

### Requirement: Repository and visual-session lifecycles remain distinct

A harvested repository image and a session-owned visual artifact SHALL remain separate records even when they derive from the same source page. Deleting a visual artifact SHALL NOT delete the repository copy implicitly, and deleting or moving a repository copy SHALL NOT silently invalidate session authorization or cause the browser to read a new host path.

#### Scenario: Person deletes a visual artifact

- **WHEN** a person explicitly deletes a session document-image artifact
- **THEN** its session reference and governed asset SHALL follow the visual artifact deletion policy while any repository copy remains unchanged

### Requirement: Harvest remains bounded and non-interpretive by default

The implementation SHALL enforce configured limits for page count, image dimensions, encoded bytes, per-run assets, and retained storage before durable writes or browser delivery. Initial harvesting SHALL preserve source visuals and available Docling captions but SHALL NOT automatically claim an interpretation of chart values or diagram meaning.

#### Scenario: Document exceeds harvest bounds

- **WHEN** a document would exceed any configured page, pixel, byte, count, or retention limit
- **THEN** harvesting SHALL stop or omit additional images safely, retain a clear bounded diagnostic, and continue text OCR only when doing so remains safe

#### Scenario: Chart has no verified description

- **WHEN** Docling preserves a chart page but no separately verified interpretation exists
- **THEN** the artifact SHALL identify the source page and available caption without presenting generated chart conclusions as observed fact

### Requirement: Existing concept-map artifacts remain compatible

Adding document-image artifacts SHALL preserve valid existing `react_flow` concept-map artifacts, their provenance, session association, accessibility behavior, and renderer. Any response schema/version change SHALL be explicit and coordinated with the authoritative backend schema, generated client types, validators, persistence, and renderer dispatch.

#### Scenario: Existing session contains a concept map

- **WHEN** a session created before document-image support is reopened
- **THEN** its valid `react_flow` artifact SHALL validate and render unchanged without requiring migration through an image artifact

### Non-requirement: text-plus-image Visboard composition

This change SHALL NOT claim that selectable OCR text, synchronized text overlays, or composed text-plus-image document views are implemented. Those behaviors require a later compatibility-reviewed specification that reuses Docling page and element identifiers without re-running OCR.
