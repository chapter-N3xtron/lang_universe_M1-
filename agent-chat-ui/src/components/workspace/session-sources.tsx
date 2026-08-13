"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, FileText, Network } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiKey } from "@/lib/api-key";
import { LOCAL_OWNER_ID } from "@/lib/session-catalog";
import { createClient } from "@/providers/client";

export type SessionSource = {
  id: string;
  stable_evidence_id: string;
  display_name: string;
  original_title: string;
  locator: string;
  kind: "web_url" | "web_snippet" | "upload" | "workspace_file";
  retrieved_at: string;
  truncated: boolean;
  content_sha256: string;
};

export function SessionSources({
  apiUrl,
  authScheme,
  threadId,
  usage,
}: {
  apiUrl: string;
  authScheme?: string;
  threadId: string;
  usage: Map<string, string[]>;
}) {
  const queryClient = useQueryClient();
  const client = useMemo(
    () => createClient(apiUrl, getApiKey() ?? undefined, authScheme),
    [apiUrl, authScheme],
  );
  const [editingId, setEditingId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const queryKey = ["session-sources", apiUrl, threadId];
  const sourcesQuery = useQuery({
    queryKey,
    queryFn: async () => {
      const result = await client.store.searchItems(
        [LOCAL_OWNER_ID, "session-sources", threadId],
        { limit: 100 },
      );
      return result.items.map((item) => item.value as SessionSource);
    },
    enabled: Boolean(apiUrl && threadId),
  });
  const rename = useMutation({
    mutationFn: async ({
      source,
      displayName,
    }: {
      source: SessionSource;
      displayName: string;
    }) => {
      await client.store.putItem(
        [LOCAL_OWNER_ID, "session-sources", threadId],
        source.id,
        { ...source, display_name: displayName },
        { index: false },
      );
    },
    onSuccess: async () => {
      setEditingId(null);
      await queryClient.invalidateQueries({ queryKey });
    },
  });
  const sources = sourcesQuery.data ?? [];

  function requestMap() {
    const chosen = selected.size
      ? sources.filter((source) => selected.has(source.id))
      : sources;
    const labels = chosen
      .map((source) => `${source.display_name} (${source.id})`)
      .join(", ");
    window.dispatchEvent(
      new CustomEvent("jasper:discuss-node", {
        detail: {
          prompt: `Create a visual concept map using only these saved session sources: ${labels}.`,
        },
      }),
    );
  }

  if (sourcesQuery.isLoading)
    return (
      <p className="text-muted-foreground p-6 text-sm">
        Loading session sources…
      </p>
    );
  if (sourcesQuery.error)
    return (
      <p
        role="alert"
        className="text-destructive p-6 text-sm"
      >
        Saved sources could not be loaded.
      </p>
    );

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold">Session sources</h3>
          <p className="text-muted-foreground text-sm">
            Librarian evidence saved for this session, including sources not
            used in a visual.
          </p>
        </div>
        <Button
          size="sm"
          disabled={!sources.length}
          onClick={requestMap}
        >
          <Network className="size-4" /> Map{" "}
          {selected.size ? "selected" : "all"}
        </Button>
      </div>
      {!sources.length ? (
        <div className="text-muted-foreground rounded-lg border border-dashed p-8 text-center text-sm">
          No Librarian sources have been saved in this session.
        </div>
      ) : (
        <ul
          className="space-y-2"
          aria-label="Saved session sources"
        >
          {sources.map((source) => (
            <li
              key={source.id}
              className="bg-muted/20 rounded-lg border p-3"
            >
              <div className="flex items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1"
                  aria-label={`Select ${source.display_name}`}
                  checked={selected.has(source.id)}
                  onChange={(event) =>
                    setSelected((current) => {
                      const next = new Set(current);
                      if (event.target.checked) next.add(source.id);
                      else next.delete(source.id);
                      return next;
                    })
                  }
                />
                <FileText className="text-muted-foreground mt-0.5 size-4 shrink-0" />
                <div className="min-w-0 flex-1">
                  {editingId === source.id ? (
                    <Input
                      autoFocus
                      aria-label="Source name"
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      onBlur={() => setEditingId(null)}
                      onKeyDown={(event) => {
                        if (event.key === "Escape") setEditingId(null);
                        if (event.key === "Enter" && name.trim())
                          rename.mutate({ source, displayName: name.trim() });
                      }}
                    />
                  ) : (
                    <button
                      className="text-left text-sm font-medium hover:underline"
                      onClick={() => {
                        setEditingId(source.id);
                        setName(source.display_name);
                      }}
                    >
                      {source.display_name}
                    </button>
                  )}
                  <p className="text-muted-foreground mt-1 text-xs">
                    Original: {source.original_title}
                  </p>
                  <p className="text-muted-foreground mt-1 text-xs">
                    {source.kind.replace("_", " ")} ·{" "}
                    {new Date(source.retrieved_at).toLocaleString()}
                    {source.truncated ? " · truncated" : ""}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2 text-xs">
                    {source.locator.startsWith("http") ? (
                      <a
                        className="text-primary inline-flex items-center gap-1 underline"
                        href={source.locator}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open source <ExternalLink className="size-3" />
                      </a>
                    ) : (
                      <span className="text-muted-foreground">
                        {source.locator}
                      </span>
                    )}
                    <span className="text-muted-foreground">
                      Used by:{" "}
                      {usage.get(source.id)?.join(", ") ||
                        "no visual concept maps"}
                    </span>
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
