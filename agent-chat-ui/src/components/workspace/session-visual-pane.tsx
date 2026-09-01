"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { parseAsStringLiteral, useQueryState } from "nuqs";
import { Trash2, Workflow } from "lucide-react";
import type { ReactNode } from "react";
import type { ConceptMapArtifact } from "@/lib/visual/jasper-response.generated";
import { validateJasperResponse } from "@/lib/visual/validate";
import {
  deleteSessionArtifact,
  fetchSessionArtifacts,
  fetchSessionDetail,
  forkSession,
  renameSessionArtifact,
} from "@/lib/session-catalog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ConceptMapRenderer } from "./concept-map-renderer";
import { SessionLibrary } from "./session-library";
import { SessionSources } from "./session-sources";
import { SessionDocuments } from "./session-documents";
import { setWorkspaceModeForThread } from "./use-workspace-preferences";

const viewParser = parseAsStringLiteral([
  "library",
  "session",
  "sources",
  "installation-documents",
  "session-documents",
] as const);
const SESSION_REMINDER_MINUTES = Number(
  process.env.NEXT_PUBLIC_SESSION_REMINDER_MINUTES ?? 90,
);

export function SessionVisualPane({
  apiUrl,
  authScheme,
  threadId,
  latestArtifact,
  selectedVoice,
  legacyTitle,
  legacyContent,
  legacyActive = false,
  onSelectThread,
}: {
  apiUrl: string;
  authScheme?: string;
  threadId: string | null;
  latestArtifact?: ConceptMapArtifact;
  selectedVoice?: string;
  legacyTitle?: ReactNode;
  legacyContent?: ReactNode;
  legacyActive?: boolean;
  onSelectThread: (threadId: string) => void;
}) {
  const queryClient = useQueryClient();
  const [view, setView] = useQueryState("sessionView", viewParser);
  const [selectedArtifactId, setSelectedArtifactId] = useQueryState("visualId");

  const [reminderDismissed, setReminderDismissed] = useState(false);
  const [editingArtifactId, setEditingArtifactId] = useState<string | null>(
    null,
  );
  const [artifactTitle, setArtifactTitle] = useState("");
  const [deleteArtifactId, setDeleteArtifactId] = useState<string | null>(null);
  const effectiveView = view ?? (threadId ? "session" : "library");
  const artifactsQuery = useQuery({
    queryKey: ["session-artifacts", apiUrl, threadId],
    queryFn: () => fetchSessionArtifacts(apiUrl, threadId!, authScheme),
    enabled: Boolean(apiUrl && threadId && effectiveView === "session"),
  });
  const detailQuery = useQuery({
    queryKey: ["session-detail", apiUrl, threadId],
    queryFn: () => fetchSessionDetail(apiUrl, threadId!, authScheme),
    enabled: Boolean(apiUrl && threadId && effectiveView === "session"),
  });
  const forkMutation = useMutation({
    mutationFn: () => forkSession(apiUrl, threadId!, authScheme),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["session-catalog"] });
      setWorkspaceModeForThread(result.thread_id, "visual");
      onSelectThread(result.thread_id);
      void setSelectedArtifactId(null);
    },
  });
  const renameArtifactMutation = useMutation({
    mutationFn: ({
      artifactId,
      title,
    }: {
      artifactId: string;
      title: string;
    }) =>
      renameSessionArtifact(apiUrl, threadId!, artifactId, title, authScheme),
    onSuccess: async () => {
      setEditingArtifactId(null);
      await queryClient.invalidateQueries({
        queryKey: ["session-artifacts", apiUrl, threadId],
      });
    },
  });
  const deleteArtifactMutation = useMutation({
    mutationFn: (artifactId: string) =>
      deleteSessionArtifact(apiUrl, threadId!, artifactId, authScheme),
    onSuccess: async (_result, artifactId) => {
      setDeleteArtifactId(null);
      if (selectedArtifactId === artifactId) void setSelectedArtifactId(null);
      await queryClient.invalidateQueries({
        queryKey: ["session-artifacts", apiUrl, threadId],
      });
    },
  });
  const artifacts = useMemo(() => {
    return (artifactsQuery.data ?? []).flatMap((entry) => {
      const validated = validateJasperResponse({
        version: 2,
        voice_text: "Saved visualization",
        artifacts: [entry.artifact],
        layout_suggestion: null,
        diagnostic: null,
      });
      const artifact = validated.valid ? validated.value.artifacts?.[0] : null;
      return artifact?.renderer === "react_flow"
        ? [{ ...entry, artifact }]
        : [];
    });
  }, [artifactsQuery.data]);
  const selectedArtifact =
    artifacts.find((entry) => entry.artifact.artifact_id === selectedArtifactId)
      ?.artifact ??
    artifacts.at(-1)?.artifact ??
    latestArtifact;
  const sourceUsage = useMemo(() => {
    const usage = new Map<string, string[]>();
    for (const entry of artifacts) {
      for (const source of entry.artifact.payload.sources) {
        usage.set(source.id, [
          ...(usage.get(source.id) ?? []),
          entry.artifact.title,
        ]);
      }
    }
    return usage;
  }, [artifacts]);

  useEffect(() => {
    if (selectedArtifact?.artifact_id && !selectedArtifactId) {
      void setSelectedArtifactId(selectedArtifact.artifact_id);
    }
  }, [selectedArtifact, selectedArtifactId, setSelectedArtifactId]);

  useEffect(() => {
    setReminderDismissed(
      threadId
        ? window.localStorage.getItem(
            `session-reminder-disabled:${threadId}`,
          ) === "true"
        : false,
    );
  }, [threadId]);

  if (effectiveView === "library") {
    return (
      <div className="bg-background h-full min-w-0 overflow-hidden border-l">
        <SessionLibrary
          apiUrl={apiUrl}
          authScheme={authScheme}
          onSelectSession={(selectedThreadId) => {
            setWorkspaceModeForThread(selectedThreadId, "visual");
            onSelectThread(selectedThreadId);
            void setSelectedArtifactId(null);
            void setView("session");
          }}
        />
      </div>
    );
  }

  if (
    effectiveView === "installation-documents" ||
    effectiveView === "session-documents"
  ) {
    return (
      <div className="bg-background h-full min-w-0 overflow-hidden border-l">
        <SessionDocuments
          apiUrl={apiUrl}
          authScheme={authScheme}
          threadId={threadId}
          view={effectiveView}
        />
      </div>
    );
  }

  return (
    <section className="bg-background flex h-full min-w-0 flex-col overflow-hidden border-l">
      <div className="flex min-h-10 items-center border-b px-4">
        <h2 className="truncate text-sm font-semibold">
          {selectedArtifact?.title ?? legacyTitle ?? "Session visuals"}
        </h2>
      </div>
      {detailQuery.data?.status === "open" &&
        detailQuery.data.active_minutes >= SESSION_REMINDER_MINUTES &&
        !reminderDismissed && (
          <div
            className="bg-muted/40 flex flex-wrap items-center gap-2 border-b px-4 py-2 text-sm"
            role="status"
          >
            <span>
              You have about {Math.floor(detailQuery.data.active_minutes / 60)}{" "}
              observed active hours here. What would serve you now?
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setReminderDismissed(true)}
            >
              Break
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setReminderDismissed(true)}
            >
              Continue
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                if (threadId)
                  window.localStorage.setItem(
                    `session-reminder-disabled:${threadId}`,
                    "true",
                  );
                setReminderDismissed(true);
              }}
            >
              Disable this reminder
            </Button>
          </div>
        )}
      {(forkMutation.error || detailQuery.error) && (
        <p
          role="alert"
          className="text-destructive border-b px-4 py-2 text-sm"
        >
          {(forkMutation.error ?? detailQuery.error)?.message}
        </p>
      )}
      {effectiveView === "sources" && threadId ? (
        <SessionSources
          apiUrl={apiUrl}
          authScheme={authScheme}
          threadId={threadId}
          usage={sourceUsage}
        />
      ) : (
        <div className="flex min-h-0 flex-1">
          {artifacts.length > 0 && (
            <nav
              className="w-48 shrink-0 overflow-y-auto border-r p-2"
              aria-label="Session visual timeline"
            >
              <p className="text-muted-foreground px-2 py-1 text-xs font-medium uppercase">
                Visual timeline
              </p>
              {artifacts.map((entry, index) => {
                const artifactId = entry.artifact.artifact_id;
                if (!artifactId) return null;
                const selected = artifactId === selectedArtifact?.artifact_id;
                return (
                  <div
                    key={artifactId}
                    className={`mb-1 rounded-md border p-1 ${selected ? "bg-secondary" : ""}`}
                  >
                    {editingArtifactId === artifactId ? (
                      <Input
                        autoFocus
                        aria-label="Board title"
                        value={artifactTitle}
                        onChange={(event) =>
                          setArtifactTitle(event.target.value)
                        }
                        onBlur={() => setEditingArtifactId(null)}
                        onKeyDown={(event) => {
                          event.stopPropagation();
                          if (event.key === "Escape")
                            setEditingArtifactId(null);
                          if (
                            event.key === "Enter" &&
                            artifactTitle.trim() &&
                            threadId
                          )
                            renameArtifactMutation.mutate({
                              artifactId,
                              title: artifactTitle.trim(),
                            });
                        }}
                      />
                    ) : (
                      <button
                        type="button"
                        className="w-full py-1 text-left whitespace-normal"
                        onClick={(event) => {
                          event.stopPropagation();
                          void setSelectedArtifactId(artifactId);
                          setEditingArtifactId(artifactId);
                          setArtifactTitle(entry.artifact.title);
                        }}
                        aria-label={`Edit board title ${entry.artifact.title}`}
                      >
                        <span className="block text-xs">
                          {index + 1}. {entry.artifact.title}
                        </span>
                        <span className="text-muted-foreground block text-[10px]">
                          {entry.relationship.replace("_", " ")}
                        </span>
                      </button>
                    )}
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-destructive ml-auto block p-1"
                      aria-label={`Delete visualization board ${entry.artifact.title}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        setDeleteArtifactId(artifactId);
                      }}
                    >
                      <Trash2
                        className="size-4"
                        aria-hidden="true"
                      />
                    </button>
                  </div>
                );
              })}
            </nav>
          )}
          <div className="relative min-w-0 flex-1">
            {selectedArtifact ? (
              <ConceptMapRenderer
                artifact={selectedArtifact}
                selectedVoice={selectedVoice}
              />
            ) : legacyActive ? (
              legacyContent
            ) : (
              <div className="flex h-full items-center justify-center p-8 text-center">
                <div className="bg-muted/30 max-w-md rounded-2xl border border-dashed p-8">
                  <Workflow className="text-muted-foreground mx-auto mb-4 size-9" />
                  <h3 className="font-medium">
                    No saved visualization in this session
                  </h3>
                  <p className="text-muted-foreground mt-2 text-sm leading-6">
                    Ask Jasper for a grounded visual, or return to All sessions
                    to review other knowledge work.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      <Dialog
        open={Boolean(deleteArtifactId)}
        onOpenChange={(open) => !open && setDeleteArtifactId(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete visualization board?</DialogTitle>
            <DialogDescription>
              Deleting “
              {artifacts.find(
                (entry) => entry.artifact.artifact_id === deleteArtifactId,
              )?.artifact.title ?? "this board"}
              ” is permanent. This removes only the visualization board, not the
              session, chat, sources, shared evidence, or reports.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Keep board</Button>
            </DialogClose>
            <Button
              variant="destructive"
              disabled={deleteArtifactMutation.isPending || !deleteArtifactId}
              onClick={() =>
                deleteArtifactId &&
                deleteArtifactMutation.mutate(deleteArtifactId)
              }
            >
              Delete permanently
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      ;
    </section>
  );
}
