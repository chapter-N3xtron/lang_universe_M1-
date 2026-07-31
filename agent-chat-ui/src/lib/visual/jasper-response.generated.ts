/* Generated from backend/src/visual_models.py. Do not edit manually. */

/**
 * @maxItems 4
 */
export type Artifacts =
  | []
  | [ConceptMapArtifact]
  | [ConceptMapArtifact, ConceptMapArtifact]
  | [ConceptMapArtifact, ConceptMapArtifact, ConceptMapArtifact]
  | [ConceptMapArtifact, ConceptMapArtifact, ConceptMapArtifact, ConceptMapArtifact];
export type AltText = string;
export type ArtifactId = string;
export type Direction = "top_to_bottom" | "left_to_right";
export type ClaimStatus = "observed" | "researched" | "user_defined" | "proposed" | "inferred";
/**
 * @minItems 1
 * @maxItems 8
 */
export type EvidenceRefs =
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string];
export type Label = string | null;
export type Relation = "relates_to" | "contains" | "calls" | "depends_on" | "flows_to";
export type Source = string;
export type Target = string;
/**
 * @maxItems 200
 */
export type Edges = ConceptMapEdge[];
export type GroundingKind = "repo" | "web" | "user_input" | "mixed";
/**
 * @minItems 1
 * @maxItems 100
 */
export type NarrationOrder = [string, ...string[]];
/**
 * @minItems 1
 * @maxItems 100
 */
export type Nodes = [ConceptMapNode, ...ConceptMapNode[]];
export type ClaimStatus1 = "observed" | "researched" | "user_defined" | "proposed" | "inferred";
export type Detail = string | null;
/**
 * @minItems 1
 * @maxItems 8
 */
export type EvidenceRefs1 =
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string];
export type Id = string;
export type Kind = "concept" | "group" | "code" | "decision" | "input" | "output";
export type Label1 = string;
export type Narration = string;
/**
 * @minItems 1
 * @maxItems 32
 */
export type Sources = [EvidenceSource, ...EvidenceSource[]];
export type ContentSha256 = string;
export type Id1 = string;
export type Kind1 = "repo_file" | "web_url" | "user_input";
export type Locator = string;
export type Title = string;
export type Renderer = "react_flow";
export type SourceMessageId = string | null;
export type Title1 = string;
export type Code = "structured_output_unavailable" | "structured_output_invalid" | "provider_unavailable";
export type Message = string;
export type Recoverable = boolean;
export type Mode = "chat" | "visual" | "split" | "compact_chat";
export type Reason = string;
export type Version = 2;
export type VoiceText = string;

export interface JasperResponse {
  artifacts?: Artifacts;
  diagnostic?: ResponseDiagnostic | null;
  layout_suggestion?: LayoutSuggestion | null;
  version?: Version;
  voice_text: VoiceText;
}
export interface ConceptMapArtifact {
  alt_text: AltText;
  artifact_id?: ArtifactId;
  payload: ConceptMapPayload;
  renderer?: Renderer;
  source_message_id?: SourceMessageId;
  title: Title1;
}
export interface ConceptMapPayload {
  direction?: Direction;
  edges?: Edges;
  grounding_kind: GroundingKind;
  narration_order: NarrationOrder;
  nodes: Nodes;
  sources: Sources;
}
export interface ConceptMapEdge {
  claim_status: ClaimStatus;
  evidence_refs: EvidenceRefs;
  label?: Label;
  relation?: Relation;
  source: Source;
  target: Target;
}
export interface ConceptMapNode {
  claim_status: ClaimStatus1;
  detail?: Detail;
  evidence_refs: EvidenceRefs1;
  id: Id;
  kind?: Kind;
  label: Label1;
  narration: Narration;
}
export interface EvidenceSource {
  content_sha256: ContentSha256;
  id: Id1;
  kind: Kind1;
  locator: Locator;
  title: Title;
}
export interface ResponseDiagnostic {
  code: Code;
  message: Message;
  recoverable?: Recoverable;
}
export interface LayoutSuggestion {
  mode: Mode;
  reason: Reason;
}
