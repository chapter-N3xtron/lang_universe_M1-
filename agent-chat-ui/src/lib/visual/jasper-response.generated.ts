/* Generated from backend/src/visual_models.py. Do not edit manually. */

/**
 * @maxItems 4
 */
export type Artifacts =
  | []
  | [ConceptMapArtifact | CoderReportArtifact]
  | [ConceptMapArtifact | CoderReportArtifact, ConceptMapArtifact | CoderReportArtifact]
  | [
      ConceptMapArtifact | CoderReportArtifact,
      ConceptMapArtifact | CoderReportArtifact,
      ConceptMapArtifact | CoderReportArtifact
    ]
  | [
      ConceptMapArtifact | CoderReportArtifact,
      ConceptMapArtifact | CoderReportArtifact,
      ConceptMapArtifact | CoderReportArtifact,
      ConceptMapArtifact | CoderReportArtifact
    ];
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
export type ArtifactId1 = string;
export type ArtifactVersion = "1";
export type AddedLines = number;
export type Availability = "available" | "binary" | "unavailable" | "redacted" | "too_large";
export type ChangeType = "added" | "modified" | "deleted" | "renamed";
export type Patch = string | null;
export type Path = string;
export type RemovedLines = number;
/**
 * @maxItems 256
 */
export type Files = CoderReportDiff[];
/**
 * @maxItems 32
 */
export type Blockers = string[];
export type ChangeType1 = "added" | "modified" | "deleted" | "renamed";
export type Path1 = string;
export type Summary = string;
/**
 * @maxItems 256
 */
export type ChangedFiles = ChangedFile[];
export type CompletionStatus = "completed" | "partial" | "blocked" | "failed" | "cancelled";
export type Impact = string;
export type Mitigation = string;
export type Risk = string;
/**
 * @maxItems 32
 */
export type MaterialRisks = MaterialRisk[];
export type CodingSessionId = string;
export type GeneratedAt = string;
export type Model = string | null;
export type Producer = "Coder";
export type ThreadIdentity = string;
export type Workspace = string;
export type Action = string;
export type Reason = string;
/**
 * @maxItems 32
 */
export type RemainingAuthorizationNeeds = AuthorizationNeed[];
/**
 * @maxItems 16
 */
export type SupportingReferences =
  | []
  | [SupportingReference]
  | [SupportingReference, SupportingReference]
  | [SupportingReference, SupportingReference, SupportingReference]
  | [SupportingReference, SupportingReference, SupportingReference, SupportingReference]
  | [SupportingReference, SupportingReference, SupportingReference, SupportingReference, SupportingReference]
  | [
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference
    ]
  | [
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference
    ]
  | [
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference
    ]
  | [
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference
    ]
  | [
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference
    ]
  | [
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference
    ]
  | [
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference
    ]
  | [
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference
    ]
  | [
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference
    ]
  | [
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference
    ]
  | [
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference,
      SupportingReference
    ];
export type Id2 = string;
export type Kind2 = "file" | "command_output" | "test_output" | "execution_manifest" | "other";
export type Locator1 = string;
export type Summary1 = string;
export type Note = string;
export type Status = "completed" | "incomplete" | "blocked" | "failed" | "skipped";
export type Task = string;
/**
 * @maxItems 64
 */
export type TaskNotes = TaskNote[];
export type Description = string;
/**
 * @maxItems 8
 */
export type ReferenceIds =
  | []
  | [string]
  | [string, string]
  | [string, string, string]
  | [string, string, string, string]
  | [string, string, string, string, string]
  | [string, string, string, string, string, string]
  | [string, string, string, string, string, string, string]
  | [string, string, string, string, string, string, string, string];
export type Result = "passed" | "failed" | "not_run" | "inconclusive";
export type Type =
  | "source_test"
  | "static_analysis"
  | "build"
  | "runtime_check"
  | "deployment_check"
  | "manual_inspection";
/**
 * @maxItems 64
 */
export type ValidationEvidence = ValidationEvidence1[];
export type Version = "1.0";
export type Renderer1 = "coder_report";
export type SourceMessageId1 = string | null;
export type Title2 = string;
export type ConfidenceBasis = string | null;
export type ConfidenceScore = number | null;
export type Code = "structured_output_unavailable" | "structured_output_invalid" | "provider_unavailable";
export type Message = string;
export type Recoverable = boolean;
export type Mode = "chat" | "visual" | "split" | "compact_chat";
export type Reason1 = string;
export type Version1 = 2;
export type VoiceText = string;

export interface JasperResponse {
  artifacts?: Artifacts;
  confidence_basis?: ConfidenceBasis;
  confidence_score?: ConfidenceScore;
  diagnostic?: ResponseDiagnostic | null;
  layout_suggestion?: LayoutSuggestion | null;
  version?: Version1;
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
export interface CoderReportArtifact {
  artifact_id: ArtifactId1;
  artifact_version?: ArtifactVersion;
  payload: CoderReportPayload;
  renderer?: Renderer1;
  source_message_id?: SourceMessageId1;
  title: Title2;
}
/**
 * A literal snapshot of the validated handoff plus captured Git evidence.
 */
export interface CoderReportPayload {
  files: Files;
  report: TechnicalReport;
}
/**
 * One changed file's bounded, non-executable visual evidence.
 */
export interface CoderReportDiff {
  added_lines: AddedLines;
  availability: Availability;
  change_type: ChangeType;
  patch?: Patch;
  path: Path;
  removed_lines: RemovedLines;
}
/**
 * The sole authoritative Coder result passed to Jasper.
 */
export interface TechnicalReport {
  blockers: Blockers;
  changed_files: ChangedFiles;
  completion_status: CompletionStatus;
  material_risks: MaterialRisks;
  provenance: ReportProvenance;
  remaining_authorization_needs: RemainingAuthorizationNeeds;
  supporting_references: SupportingReferences;
  task_notes: TaskNotes;
  validation_evidence: ValidationEvidence;
  version: Version;
}
export interface ChangedFile {
  change_type: ChangeType1;
  path: Path1;
  summary: Summary;
}
export interface MaterialRisk {
  impact: Impact;
  mitigation: Mitigation;
  risk: Risk;
}
export interface ReportProvenance {
  coding_session_id: CodingSessionId;
  generated_at: GeneratedAt;
  model?: Model;
  producer: Producer;
  thread_identity: ThreadIdentity;
  workspace: Workspace;
}
export interface AuthorizationNeed {
  action: Action;
  reason: Reason;
}
export interface SupportingReference {
  id: Id2;
  kind: Kind2;
  locator: Locator1;
  summary: Summary1;
}
export interface TaskNote {
  note: Note;
  status: Status;
  task: Task;
}
export interface ValidationEvidence1 {
  description: Description;
  reference_ids?: ReferenceIds;
  result: Result;
  type: Type;
}
export interface ResponseDiagnostic {
  code: Code;
  message: Message;
  recoverable?: Recoverable;
}
export interface LayoutSuggestion {
  mode: Mode;
  reason: Reason1;
}
