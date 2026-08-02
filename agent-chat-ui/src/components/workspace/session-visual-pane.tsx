"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { parseAsStringLiteral, useQueryState } from "nuqs";
import { GitFork, Library, LogOut, Workflow } from "lucide-react";
import type { ReactNode } from "react";
import type { ConceptMapArtifact } from "@/lib/visual/jasper-response.generated";
import { validateJasperResponse } from "@/lib/visual/validate";
import {
  closeSession,
  fetchSessionArtifacts,
  fetchSessionDetail,
  forkSession,
} from "@/lib/session-catalog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ConceptMapRenderer } from "./concept-map-renderer";
import { SessionLibrary } from "./session-library";
import { setWorkspaceModeForThread } from "./use-workspace-preferences";

const viewParser = parseAsStringLiteral(["library", "session"] as const);
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
  const [closeOpen, setCloseOpen] = useState(false);
  const [reviewSummary, setReviewSummary] = useState("");
  const [reviewTentPoles, setReviewTentPoles] = useState("");
  const [reminderDismissed, setReminderDismissed] = useState(false);
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
  const closeMutation = useMutation({
    mutationFn: () => closeSession(
      apiUrl,
      threadId!,
      reviewSummary.trim(),
      reviewTentPoles.split("\n").map((line) => line.trim()).filter(Boolean),
      authScheme,
    ),
    onSuccess: async () => {
      setCloseOpen(false);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["session-detail", apiUrl, threadId] }),
        queryClient.invalidateQueries({ queryKey: ["session-catalog"] }),
      ]);
    },
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
      return artifact?.renderer === "react_flow" ? [{ ...entry, artifact }] : [];
    });
  }, [artifactsQuery.data]);
  const selectedArtifact =
    artifacts.find((entry) => entry.artifact.artifact_id === selectedArtifactId)
      ?.artifact ??
    artifacts.at(-1)?.artifact ??
    latestArtifact;

  useEffect(() => {
    if (selectedArtifact?.artifact_id && !selectedArtifactId) {
      void setSelectedArtifactId(selectedArtifact.artifact_id);
    }
  }, [selectedArtifact, selectedArtifactId, setSelectedArtifactId]);

  useEffect(() => {
    setReminderDismissed(
      threadId
        ? window.localStorage.getItem(`session-reminder-disabled:${threadId}`) === "true"
        : false,
    );
  }, [threadId]);

  function beginCloseReview() {
    setReviewSummary(detailQuery.data?.long_description ?? "");
    setReviewTentPoles((detailQuery.data?.tent_poles ?? []).join("\n"));
    setCloseOpen(true);
  }

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

  return (
    <section className="bg-background flex h-full min-w-0 flex-col overflow-hidden border-l">
      <header className="flex min-h-14 items-center gap-3 border-b px-4 pr-40">
        <Button
          size="sm"
          variant="outline"
          onClick={() => setView("library")}
        >
          <Library className="size-4" /> All sessions
        </Button>
        <h2 className="truncate text-sm font-semibold">
          {selectedArtifact?.title ?? legacyTitle ?? "Session visuals"}
        </h2>
        <div className="ml-auto flex gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={!threadId || forkMutation.isPending}
            onClick={() => forkMutation.mutate()}
          >
            <GitFork className="size-4" /> Fork as new session
          </Button>
          <Dialog open={closeOpen} onOpenChange={setCloseOpen}>
            <DialogTrigger asChild>
              <Button
                size="sm"
                variant="outline"
                disabled={!threadId || detailQuery.data?.status === "closed"}
                onClick={beginCloseReview}
              >
                <LogOut className="size-4" /> Close session
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Review this session before closing</DialogTitle>
                <DialogDescription>
                  This records your reviewed summary and tent poles. It does not commit or push repository changes.
                </DialogDescription>
              </DialogHeader>
              <label className="space-y-2 text-sm font-medium">
                Session summary
                <Textarea value={reviewSummary} onChange={(event) => setReviewSummary(event.target.value)} rows={7} />
              </label>
              <label className="space-y-2 text-sm font-medium">
                Tent poles, one per line
                <Textarea value={reviewTentPoles} onChange={(event) => setReviewTentPoles(event.target.value)} rows={6} />
              </label>
              {closeMutation.error && <p role="alert" className="text-destructive text-sm">{closeMutation.error.message}</p>}
              <DialogFooter>
                <DialogClose asChild><Button variant="outline">Keep open</Button></DialogClose>
                <Button disabled={closeMutation.isPending} onClick={() => closeMutation.mutate()}>Save review and close</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </header>
      {detailQuery.data?.status === "open" && detailQuery.data.active_minutes >= SESSION_REMINDER_MINUTES && !reminderDismissed && (
        <div className="bg-muted/40 flex flex-wrap items-center gap-2 border-b px-4 py-2 text-sm" role="status">
          <span>You have about {Math.floor(detailQuery.data.active_minutes / 60)} observed active hours here. What would serve you now?</span>
          <Button size="sm" variant="outline" onClick={() => setReminderDismissed(true)}>Break</Button>
          <Button size="sm" variant="outline" onClick={beginCloseReview}>Close</Button>
          <Button size="sm" variant="outline" onClick={() => setReminderDismissed(true)}>Continue</Button>
          <Button size="sm" variant="ghost" onClick={() => {
            if (threadId) window.localStorage.setItem(`session-reminder-disabled:${threadId}`, "true");
            setReminderDismissed(true);
          }}>Disable this reminder</Button>
        </div>
      )}
      {(forkMutation.error || detailQuery.error) && (
        <p role="alert" className="text-destructive border-b px-4 py-2 text-sm">
          {(forkMutation.error ?? detailQuery.error)?.message}
        </p>
      )}
      <div className="flex min-h-0 flex-1">
        {artifacts.length > 0 && (
          <nav className="w-48 shrink-0 overflow-y-auto border-r p-2" aria-label="Session visual timeline">
            <p className="text-muted-foreground px-2 py-1 text-xs font-medium uppercase">Visual timeline</p>
            {artifacts.map((entry, index) => (
              <Button
                key={entry.artifact.artifact_id}
                variant={entry.artifact.artifact_id === selectedArtifact?.artifact_id ? "secondary" : "ghost"}
                className="mb-1 h-auto w-full justify-start whitespace-normal py-2 text-left"
                onClick={() =>
                  setSelectedArtifactId(entry.artifact.artifact_id ?? null)
                }
              >
                <span>
                  <span className="block text-xs">{index + 1}. {entry.artifact.title}</span>
                  <span className="text-muted-foreground block text-[10px]">{entry.relationship.replace("_", " ")}</span>
                </span>
              </Button>
            ))}
          </nav>
        )}
        <div className="relative min-w-0 flex-1">
          {selectedArtifact ? (
            <ConceptMapRenderer artifact={selectedArtifact} selectedVoice={selectedVoice} />
          ) : legacyActive ? (
            legacyContent
          ) : (
            <div className="flex h-full items-center justify-center p-8 text-center">
              <div className="bg-muted/30 max-w-md rounded-2xl border border-dashed p-8">
                <Workflow className="text-muted-foreground mx-auto mb-4 size-9" />
                <h3 className="font-medium">No saved visualization in this session</h3>
                <p className="text-muted-foreground mt-2 text-sm leading-6">
                  Ask Jasper for a grounded visual, or return to All sessions to review other knowledge work.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
