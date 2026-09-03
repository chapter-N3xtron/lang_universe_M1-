import dynamic from "next/dynamic";
import type {
  Artifacts,
  ConceptMapArtifact,
} from "@/lib/visual/jasper-response.generated";
import type { UnsupportedCoderReportArtifact } from "@/lib/visual/validate";
import { ConceptMapRenderer } from "./concept-map-renderer";

const CoderReportRenderer = dynamic(
  () =>
    import("./coder-report-renderer").then((module) => module.CoderReportRenderer),
  { ssr: false },
);
const UnsupportedCoderReportVersion = dynamic(
  () =>
    import("./coder-report-renderer").then(
      (module) => module.UnsupportedCoderReportVersion,
    ),
  { ssr: false },
);

type VisualArtifact = Artifacts[number] | UnsupportedCoderReportArtifact;

function isConceptMapArtifact(
  artifact: VisualArtifact,
): artifact is ConceptMapArtifact {
  return (
    artifact.renderer !== "coder_report" &&
    artifact.renderer !== "unsupported_coder_report"
  );
}

export function VisualArtifactRenderer({
  artifact,
  selectedVoice,
}: {
  artifact: VisualArtifact;
  selectedVoice?: string;
}) {
  if (artifact.renderer === "unsupported_coder_report") {
    return (
      <UnsupportedCoderReportVersion version={artifact.artifact_version} />
    );
  }
  if (artifact.renderer === "coder_report") {
    return <CoderReportRenderer artifact={artifact} />;
  }
  if (isConceptMapArtifact(artifact)) {
    return (
      <ConceptMapRenderer
        artifact={artifact}
        selectedVoice={selectedVoice}
      />
    );
  }
  return null;
}
