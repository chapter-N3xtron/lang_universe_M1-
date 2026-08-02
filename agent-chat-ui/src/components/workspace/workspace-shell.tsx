"use client";

import { ReactNode } from "react";
import { Columns2, MessageSquare, Rows2, Sparkles } from "lucide-react";
import {
  Group,
  Panel,
  Separator,
  useDefaultLayout,
} from "react-resizable-panels";
import type { LayoutStorage } from "react-resizable-panels";
import type { LayoutSuggestion } from "@/lib/visual/jasper-response.generated";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import {
  type WorkspaceMode,
  useWorkspacePreferences,
} from "./use-workspace-preferences";

type WorkspaceShellProps = {
  threadId: string | null;
  chat: ReactNode;
  visual: ReactNode;
  composer: ReactNode;
  visualAvailable: boolean;
  suggestion?: LayoutSuggestion | null;
};

const MODE_LAYOUTS: Record<WorkspaceMode, { chat: number; visual: number }> = {
  chat: { chat: 100, visual: 0 },
  visual: { chat: 0, visual: 100 },
  split: { chat: 50, visual: 50 },
  compact_chat: { chat: 28, visual: 72 },
};

const browserLayoutStorage: LayoutStorage = {
  getItem(key) {
    return typeof window === "undefined" ? null : window.localStorage.getItem(key);
  },
  setItem(key, value) {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(key, value);
    }
  },
};

export function WorkspaceShell({
  threadId,
  chat,
  visual,
  composer,
  visualAvailable,
  suggestion,
}: WorkspaceShellProps) {
  const { preferences, setMode } = useWorkspacePreferences(threadId);
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const preferredMode =
    preferences.mode === "compact_chat" ? "split" : preferences.mode;
  const effectiveMode = preferredMode;
  const suggestedMode =
    suggestion?.mode === "compact_chat" ? "split" : suggestion?.mode;
  const persistence = useDefaultLayout({
    id: `visual-workspace-panels:v2:${threadId || "new-thread"}:${effectiveMode}:chat-first`,
    panelIds: ["chat", "visual"],
    onlySaveAfterUserInteractions: true,
    storage: browserLayoutStorage,
  });

  const focusedSurface =
    effectiveMode === "chat" ? (
      <div
        className="h-full min-w-0 overflow-hidden"
        data-workspace-surface="chat"
      >
        {chat}
      </div>
    ) : effectiveMode === "visual" ? (
      <div
        className="h-full min-w-0 overflow-hidden"
        data-workspace-surface="visual"
      >
        {visual}
      </div>
    ) : null;

  const orderedPanels = [
    <Panel
      id="chat"
      key="chat"
      collapsible
      collapsedSize="0%"
      minSize="20%"
      className="min-w-0 overflow-hidden"
      data-workspace-surface="chat"
    >
      {chat}
    </Panel>,
    <Separator
      id="workspace-separator"
      key="separator"
      aria-label="Resize chat and visual panes"
      className="group bg-border/60 hover:bg-primary/25 focus-visible:ring-ring data-[separator=active]:bg-primary/35 relative flex w-2 cursor-col-resize items-center justify-center transition-colors focus-visible:ring-2 focus-visible:outline-none"
    >
      <span className="bg-muted-foreground/60 group-hover:bg-primary h-12 w-1 rounded-full transition-colors" />
    </Separator>,
    <Panel
      id="visual"
      key="visual"
      collapsible
      collapsedSize="0%"
      minSize="20%"
      className="min-w-0 overflow-hidden"
      data-workspace-surface="visual"
    >
      {visual}
    </Panel>,
  ];

  return (
    <div
      className="flex h-full min-w-0 flex-1 flex-col"
      data-workspace-mode={effectiveMode}
    >
      <div className="relative min-h-0 min-w-0 flex-1">
        <div className="bg-background/95 supports-[backdrop-filter]:bg-background/80 absolute top-2 left-1/2 z-30 flex -translate-x-1/2 items-center gap-1 rounded-lg border p-1 shadow-sm backdrop-blur">
          <Button
            size="sm"
            aria-label="Focus chat"
            variant={effectiveMode === "chat" ? "secondary" : "ghost"}
            onClick={() => setMode("chat")}
          >
            <MessageSquare className="size-4" />
            Chat
          </Button>
          <Button
            size="sm"
            aria-label="Split chat and visual"
            variant={effectiveMode === "split" ? "secondary" : "ghost"}
            onClick={() => setMode("split")}
          >
            <Columns2 className="size-4" />
            Split
          </Button>
          <Button
            size="sm"
            aria-label="Focus visual"
            variant={effectiveMode === "visual" ? "secondary" : "ghost"}
            onClick={() => setMode("visual")}
          >
            <Rows2 className="size-4 rotate-90" />
            Visual
          </Button>
        </div>

        {visualAvailable && suggestion && suggestedMode !== effectiveMode && (
          <div
            role="status"
            className="bg-background absolute right-3 bottom-3 z-30 flex max-w-sm items-center gap-3 rounded-lg border p-3 shadow-lg"
          >
            <Sparkles className="text-primary size-4 shrink-0" />
            <p className="text-muted-foreground text-sm">{suggestion.reason}</p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setMode(suggestedMode ?? "split")}
            >
              Apply
            </Button>
          </div>
        )}

        {isDesktop ? (
          focusedSurface ? (
            focusedSurface
          ) : (
            <Group
              key={effectiveMode}
              id={`visual-workspace:${threadId || "new-thread"}`}
              orientation="horizontal"
              defaultLayout={
                persistence.defaultLayout ?? MODE_LAYOUTS[effectiveMode]
              }
              onLayoutChanged={persistence.onLayoutChanged}
              resizeTargetMinimumSize={{ fine: 16, coarse: 32 }}
              className="h-full overflow-hidden"
            >
              {orderedPanels}
            </Group>
          )
        ) : (
          <div className="relative h-full">
            <div
              className={cn(
                "absolute inset-0",
                effectiveMode !== "chat" && "invisible",
              )}
              aria-hidden={effectiveMode !== "chat"}
            >
              {chat}
            </div>
            <div
              className={cn(
                "absolute inset-0",
                effectiveMode === "chat" && "invisible",
              )}
              aria-hidden={effectiveMode === "chat"}
            >
              {visual}
            </div>
          </div>
        )}
      </div>
      <div
        className="bg-background shrink-0 border-t"
        data-workspace-composer
      >
        {composer}
      </div>
    </div>
  );
}
