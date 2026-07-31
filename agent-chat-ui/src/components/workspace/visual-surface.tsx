"use client";

import { ReactNode } from "react";
import { PanelsTopLeft } from "lucide-react";
import type { ConceptMapArtifact } from "@/lib/visual/jasper-response.generated";
import { ConceptMapRenderer } from "./concept-map-renderer";

export function VisualSurface({
  artifact,
  legacyTitle,
  legacyContent,
  legacyActive = false,
  selectedVoice,
}: {
  artifact?: ConceptMapArtifact;
  legacyTitle?: ReactNode;
  legacyContent?: ReactNode;
  legacyActive?: boolean;
  selectedVoice?: string;
}) {
  return (
    <div className="bg-background flex h-full min-w-0 flex-col overflow-hidden border-l">
      <header className="flex min-h-14 items-center border-b px-4 pr-40">
        <h2 className="truncate text-sm font-semibold">
          {artifact?.title ?? legacyTitle ?? "Visual workspace"}
        </h2>
      </header>
      <div className="relative min-h-0 flex-1">
        {artifact ? (
          <ConceptMapRenderer
            artifact={artifact}
            selectedVoice={selectedVoice}
          />
        ) : legacyActive ? (
          legacyContent
        ) : (
          <div
            className="flex h-full items-center justify-center p-8 text-center"
            data-visual-empty-state
          >
            <div className="bg-muted/30 max-w-md rounded-2xl border border-dashed p-8">
              <PanelsTopLeft className="text-muted-foreground mx-auto mb-4 size-9" />
              <h3 className="font-medium">Visual workspace ready</h3>
              <p className="text-muted-foreground mt-2 text-sm leading-6">
                Concept maps and grounded code visualizations will appear here.
                You can keep this surface open while you work with Jasper.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
