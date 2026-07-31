"use client";

import { useCallback, useSyncExternalStore } from "react";

export type WorkspaceMode = "chat" | "visual" | "split" | "compact_chat";

export type WorkspacePreferences = {
  mode: WorkspaceMode;
  visualFirst: boolean;
};

const DEFAULT_PREFERENCES: WorkspacePreferences = {
  mode: "chat",
  visualFirst: false,
};
const EVENT_NAME = "visual-workspace-preferences";

function storageKey(threadId: string | null): string {
  return `visual-workspace:v1:${threadId || "new-thread"}`;
}

function parsePreferences(raw: string | null): WorkspacePreferences {
  if (!raw) return DEFAULT_PREFERENCES;
  try {
    const value = JSON.parse(raw) as Partial<WorkspacePreferences>;
    if (
      !["chat", "visual", "split", "compact_chat"].includes(value.mode ?? "") ||
      typeof value.visualFirst !== "boolean"
    ) {
      return DEFAULT_PREFERENCES;
    }
    return {
      mode: value.mode as WorkspaceMode,
      visualFirst: value.visualFirst,
    };
  } catch {
    return DEFAULT_PREFERENCES;
  }
}

function subscribe(callback: () => void): () => void {
  window.addEventListener("storage", callback);
  window.addEventListener(EVENT_NAME, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(EVENT_NAME, callback);
  };
}

export function useWorkspacePreferences(threadId: string | null) {
  const key = storageKey(threadId);
  const raw = useSyncExternalStore(
    subscribe,
    () => window.localStorage.getItem(key),
    () => null,
  );
  const preferences = parsePreferences(raw);

  const update = useCallback(
    (next: WorkspacePreferences) => {
      window.localStorage.setItem(key, JSON.stringify(next));
      window.dispatchEvent(new Event(EVENT_NAME));
    },
    [key],
  );

  const setMode = useCallback(
    (mode: WorkspaceMode) => update({ ...preferences, mode }),
    [preferences, update],
  );
  const setVisualFirst = useCallback(
    (visualFirst: boolean) => update({ ...preferences, visualFirst }),
    [preferences, update],
  );

  return { preferences, setMode, setVisualFirst };
}
