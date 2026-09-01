"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { parseAsStringLiteral, useQueryState } from "nuqs";
import {
  BookOpen,
  FileText,
  FolderOpen,
  GitFork,
  Library,
  List,
  ListX,
  LogOut,
  SquarePen,
} from "lucide-react";
import {
  closeSession,
  fetchSessionDetail,
  forkSession,
} from "@/lib/session-catalog";
import { setWorkspaceModeForThread } from "./use-workspace-preferences";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { TooltipIconButton } from "@/components/thread/tooltip-icon-button";
import { GitHubSVG } from "@/components/icons/github";
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

const viewParser = parseAsStringLiteral([
  "library",
  "session",
  "sources",
  "installation-documents",
  "session-documents",
] as const);

type SessionWorkspaceTopBarProps = {
  apiUrl: string;
  authScheme?: string;
  threadId: string | null;
  todosOpen: boolean;
  isOpeningSession: boolean;
  onToggleTodos: () => void;
  onOpenSession: () => void;
  onSelectThread: (threadId: string) => void;
};

export function SessionWorkspaceTopBar({
  apiUrl,
  authScheme,
  threadId,
  todosOpen,
  isOpeningSession,
  onToggleTodos,
  onOpenSession,
  onSelectThread,
}: SessionWorkspaceTopBarProps) {
  const queryClient = useQueryClient();
  const [view, setView] = useQueryState("sessionView", viewParser);
  const [closeOpen, setCloseOpen] = useState(false);
  const [reviewSummary, setReviewSummary] = useState("");
  const [reviewTentPoles, setReviewTentPoles] = useState("");
  const detailQuery = useQuery({
    queryKey: ["session-detail", apiUrl, threadId],
    queryFn: () => fetchSessionDetail(apiUrl, threadId!, authScheme),
    enabled: Boolean(apiUrl && threadId),
  });
  const forkMutation = useMutation({
    mutationFn: () => forkSession(apiUrl, threadId!, authScheme),
    onSuccess: async (result) => {
      await queryClient.invalidateQueries({ queryKey: ["session-catalog"] });
      setWorkspaceModeForThread(result.thread_id, "visual");
      onSelectThread(result.thread_id);
    },
  });
  const closeMutation = useMutation({
    mutationFn: () =>
      closeSession(
        apiUrl,
        threadId!,
        reviewSummary.trim(),
        reviewTentPoles
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
        authScheme,
      ),
    onSuccess: async () => {
      setCloseOpen(false);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["session-detail", apiUrl, threadId],
        }),
        queryClient.invalidateQueries({ queryKey: ["session-catalog"] }),
      ]);
    },
  });

  const beginCloseReview = () => {
    setReviewSummary(detailQuery.data?.long_description ?? "");
    setReviewTentPoles((detailQuery.data?.tent_poles ?? []).join("\n"));
    setCloseOpen(true);
  };
  const showingSources = view === "sources";
  const showingInstallationDocuments = view === "installation-documents";
  const showingSessionDocuments = view === "session-documents";
  const showDocumentView = (
    nextView: "installation-documents" | "session-documents",
  ) => {
    void setView(nextView);
    setWorkspaceModeForThread(threadId ?? "", "visual");
  };

  return (
    <header className="bg-background flex min-h-14 shrink-0 flex-wrap items-center gap-2 border-b px-3 py-2 lg:flex-nowrap">
      <Button
        size="sm"
        variant="outline"
        onClick={() => setView("library")}
      >
        <Library className="size-4" /> All sessions
      </Button>
      <Button
        size="sm"
        variant={showingSources ? "secondary" : "outline"}
        disabled={!threadId}
        onClick={() => setView(showingSources ? "session" : "sources")}
      >
        <BookOpen className="size-4" /> {showingSources ? "Visuals" : "Sources"}
      </Button>
      <nav
        className="flex shrink-0 items-center rounded-md border p-0.5"
        aria-label="Document views"
      >
        <Button
          size="sm"
          variant={showingInstallationDocuments ? "secondary" : "ghost"}
          onClick={() => showDocumentView("installation-documents")}
        >
          <FolderOpen className="size-4" /> Installation Library
        </Button>
        <Button
          size="sm"
          variant={showingSessionDocuments ? "secondary" : "ghost"}
          disabled={!threadId}
          onClick={() => showDocumentView("session-documents")}
        >
          <FileText className="size-4" /> Session Documents
        </Button>
      </nav>
      <Button
        size="sm"
        variant="outline"
        disabled={!threadId || forkMutation.isPending}
        onClick={() => forkMutation.mutate()}
      >
        <GitFork className="size-4" /> Fork as new session
      </Button>
      <Dialog
        open={closeOpen}
        onOpenChange={setCloseOpen}
      >
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
        <DialogContent onOpenAutoFocus={(event) => event.preventDefault()}>
          <DialogHeader>
            <DialogTitle>Review this session before closing</DialogTitle>
            <DialogDescription>
              This records your reviewed summary and tent poles. It does not
              commit or push repository changes.
            </DialogDescription>
          </DialogHeader>
          <label className="space-y-2 text-sm font-medium">
            Session summary
            <Textarea
              value={reviewSummary}
              onChange={(event) => setReviewSummary(event.target.value)}
              rows={7}
            />
          </label>
          <label className="space-y-2 text-sm font-medium">
            Tent poles, one per line
            <Textarea
              value={reviewTentPoles}
              onChange={(event) => setReviewTentPoles(event.target.value)}
              rows={6}
            />
          </label>
          {closeMutation.error && (
            <p
              role="alert"
              className="text-destructive text-sm"
            >
              {closeMutation.error.message}
            </p>
          )}
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Keep open</Button>
            </DialogClose>
            <Button
              disabled={closeMutation.isPending}
              onClick={() => closeMutation.mutate()}
            >
              Save review and close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <div className="ml-auto flex items-center gap-1">
        <TooltipIconButton
          size="lg"
          className="p-2"
          tooltip={todosOpen ? "Close todos" : "Show todos"}
          variant="ghost"
          onClick={onToggleTodos}
        >
          {todosOpen ? (
            <ListX className="size-5" />
          ) : (
            <List className="size-5" />
          )}
        </TooltipIconButton>
        <ThemeToggle />
        <a
          href="https://github.com/langchain-ai/agent-chat-ui"
          target="_blank"
          aria-label="Open GitHub repo"
          className="hover:bg-accent flex size-9 items-center justify-center rounded-md"
        >
          <GitHubSVG
            width="20"
            height="20"
          />
        </a>
        <TooltipIconButton
          size="lg"
          className="p-2"
          tooltip="New session"
          variant="ghost"
          disabled={isOpeningSession}
          onClick={onOpenSession}
        >
          <SquarePen className="size-5" />
        </TooltipIconButton>
      </div>
    </header>
  );
}
