"use client";

import * as Tabs from "@radix-ui/react-tabs";
import { PatchDiff, Virtualizer } from "@pierre/diffs/react";
import { FileTree, useFileTree } from "@pierre/trees/react";
import { useState, type ReactNode } from "react";
import type {
  CoderReportArtifact,
  CoderReportDiff,
} from "@/lib/visual/jasper-response.generated";

const unavailableMessages: Record<
  Exclude<CoderReportDiff["availability"], "available">,
  string
> = {
  binary: "This file is binary, so a text diff is not available.",
  unavailable: "A safe diff was not captured for this file.",
  redacted: "The diff was withheld because it contains redacted content.",
  too_large:
    "The diff was omitted because it exceeded the safe artifact budget.",
};

function EmptyList({ children }: { children: ReactNode }) {
  return (
    <li className="text-muted-foreground list-none text-sm">{children}</li>
  );
}

function ReportDetails({ artifact }: { artifact: CoderReportArtifact }) {
  const report = artifact.payload.report;
  return (
    <div className="space-y-6 p-4">
      <section aria-labelledby="completion-status">
        <h3
          id="completion-status"
          className="text-sm font-semibold"
        >
          Completion status
        </h3>
        <p className="mt-1 text-sm capitalize">
          {report.completion_status.replace("_", " ")}
        </p>
      </section>
      <ReportList title="Task notes">
        {report.task_notes.length ? (
          report.task_notes.map((note, index) => (
            <li key={`${note.task}-${index}`}>
              <strong className="capitalize">
                {note.status.replace("_", " ")}:{" "}
              </strong>
              {note.task} — {note.note}
            </li>
          ))
        ) : (
          <EmptyList>No task notes were provided.</EmptyList>
        )}
      </ReportList>
      <ReportList title="Changed files">
        {report.changed_files.length ? (
          report.changed_files.map((file, index) => (
            <li key={`${file.path}-${index}`}>
              <code>{file.path}</code> ({file.change_type}): {file.summary}
            </li>
          ))
        ) : (
          <EmptyList>No changed files were reported.</EmptyList>
        )}
      </ReportList>
      <ReportList title="Validation evidence">
        {report.validation_evidence.length ? (
          report.validation_evidence.map((evidence, index) => (
            <li key={`${evidence.type}-${index}`}>
              <strong className="capitalize">
                {evidence.result.replace("_", " ")}:{" "}
              </strong>
              {evidence.type.replace("_", " ")} — {evidence.description}
            </li>
          ))
        ) : (
          <EmptyList>No validation evidence was provided.</EmptyList>
        )}
      </ReportList>
      <ReportList title="Blockers">
        {report.blockers.length ? (
          report.blockers.map((blocker, index) => (
            <li key={index}>{blocker}</li>
          ))
        ) : (
          <EmptyList>No blockers were reported.</EmptyList>
        )}
      </ReportList>
      <ReportList title="Authorization needs">
        {report.remaining_authorization_needs.length ? (
          report.remaining_authorization_needs.map((need, index) => (
            <li key={`${need.action}-${index}`}>
              <strong>{need.action}:</strong> {need.reason}
            </li>
          ))
        ) : (
          <EmptyList>No remaining authorization needs were reported.</EmptyList>
        )}
      </ReportList>
      <ReportList title="Material risks">
        {report.material_risks.length ? (
          report.material_risks.map((risk, index) => (
            <li key={`${risk.risk}-${index}`}>
              <strong>{risk.risk}:</strong> {risk.impact} Mitigation:{" "}
              {risk.mitigation}
            </li>
          ))
        ) : (
          <EmptyList>No material risks were reported.</EmptyList>
        )}
      </ReportList>
    </div>
  );
}

function ReportList({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section aria-label={title}>
      <h3 className="text-sm font-semibold">{title}</h3>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">{children}</ul>
    </section>
  );
}

function ReportFileTree({
  artifact,
  onSelectPath,
}: {
  artifact: CoderReportArtifact;
  onSelectPath: (path: string) => void;
}) {
  const files = artifact.payload.files;
  const { model } = useFileTree({
    paths: files.map((file) => file.path),
    gitStatus: files.map((file) => ({
      path: file.path,
      status: file.change_type,
    })),
    initialExpansion: "open",
    renaming: false,
    dragAndDrop: false,
    composition: { contextMenu: { enabled: false } },
    onSelectionChange: (selectedPaths) => {
      const path = selectedPaths.at(-1);
      if (path) {
        onSelectPath(path);
      }
    },
  });

  return (
    <section aria-labelledby="changed-file-tree" className="px-4 pb-4">
      <h3 id="changed-file-tree" className="text-sm font-semibold">
        Changed file tree
      </h3>
      <FileTree
        data-coder-report-file-tree
        model={model}
        className="mt-1"
        style={{ height: "240px" }}
      />
    </section>
  );
}

function FileDiff({ file }: { file: CoderReportDiff }) {
  if (file.availability !== "available" || !file.patch) {
    const message =
      file.availability === "available"
        ? "A patch was not included, so no diff can be displayed."
        : unavailableMessages[file.availability];
    return <p className="text-muted-foreground p-4 text-sm">{message}</p>;
  }

  return (
    <Virtualizer
      className="h-full overflow-auto"
      contentClassName="min-w-max"
    >
      <PatchDiff patch={file.patch} />
    </Virtualizer>
  );
}

export function UnsupportedCoderReportVersion({
  version,
}: {
  version: string;
}) {
  return (
    <div
      className="p-4"
      role="alert"
      aria-label="Unsupported Coder report version"
    >
      <h3 className="font-semibold">Unsupported Coder report version</h3>
      <p className="text-muted-foreground mt-1 text-sm">
        This report uses version {version}, which this client cannot safely
        display. Update the client to review its technical details and diffs.
      </p>
    </div>
  );
}

function CoderReportTabs({ artifact }: { artifact: CoderReportArtifact }) {
  const [activeTab, setActiveTab] = useState("report");

  function selectFilePath(path: string) {
    const fileIndex = artifact.payload.files.findIndex(
      (file) => file.path === path,
    );
    if (fileIndex >= 0) {
      setActiveTab(`file-${fileIndex}`);
    }
  }

  return (
    <Tabs.Root
      value={activeTab}
      onValueChange={setActiveTab}
      className="flex h-full min-h-0 flex-col"
    >
      <Tabs.List
        aria-label="Coder report sections and changed files"
        className="flex shrink-0 overflow-x-auto border-b p-2"
      >
        <Tabs.Trigger
          value="report"
          className="data-[state=active]:bg-secondary rounded px-3 py-2 text-sm"
        >
          Report
        </Tabs.Trigger>
        {artifact.payload.files.map((file, index) => (
          <Tabs.Trigger
            key={`${file.path}-${index}`}
            value={`file-${index}`}
            className="data-[state=active]:bg-secondary rounded px-3 py-2 text-left text-sm whitespace-nowrap"
          >
            {file.path} −{file.removed_lines} +{file.added_lines}
          </Tabs.Trigger>
        ))}
      </Tabs.List>
      <Tabs.Content
        value="report"
        className="min-h-0 flex-1 overflow-y-auto"
        tabIndex={0}
      >
        <ReportDetails artifact={artifact} />
        <ReportFileTree artifact={artifact} onSelectPath={selectFilePath} />
      </Tabs.Content>
      {artifact.payload.files.map((file, index) => (
        <Tabs.Content
          key={`${file.path}-${index}`}
          value={`file-${index}`}
          className="min-h-0 flex-1 overflow-hidden"
          tabIndex={0}
        >
          <FileDiff file={file} />
        </Tabs.Content>
      ))}
    </Tabs.Root>
  );
}

export function CoderReportRenderer({
  artifact,
}: {
  artifact: CoderReportArtifact;
}) {
  // Do not attempt to parse a later artifact shape as a patch. Widen the
  // generated literal here so the defensive UI branch remains future-safe.
  const artifactVersion: string | undefined = artifact.artifact_version;
  if (artifactVersion && artifactVersion !== "1") {
    return <UnsupportedCoderReportVersion version={artifactVersion} />;
  }

  return <CoderReportTabs artifact={artifact} />;
}
