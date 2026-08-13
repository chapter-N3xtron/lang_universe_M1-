"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
  type SortingState,
  type VisibilityState,
} from "@tanstack/react-table";
import {
  parseAsArrayOf,
  parseAsInteger,
  parseAsJson,
  parseAsString,
  useQueryState,
} from "nuqs";
import {
  QueryBuilder,
  type Field,
  type RuleGroupType,
} from "react-querybuilder";
import "react-querybuilder/dist/query-builder.css";
import { ArrowDown, ArrowUp, Filter, Save, Search, Workflow } from "lucide-react";
import { QueryBuilderShadcn } from "@/components/query-builder";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { getApiKey } from "@/lib/api-key";
import {
  LOCAL_OWNER_ID,
  defaultSessionFilters,
  fetchSavedSessionViews,
  fetchSessions,
  saveSessionView,
  type SessionCatalogRow,
  type SavedSessionView,
} from "@/lib/session-catalog";
import { createClient } from "@/providers/client";

const SESSION_FIELDS: Field[] = [
  { name: "created_at", label: "Created", inputType: "datetime-local" },
  { name: "last_activity_at", label: "Last activity", inputType: "datetime-local" },
  // Wire field remains `workspace`; the UI label describes its repository binding.
  { name: "workspace", label: "Repository" },
  { name: "agent", label: "Agent" },
  {
    name: "status",
    label: "Status",
    valueEditorType: "select",
    values: ["open", "closed", "forked"].map((name) => ({ name, label: name })),
  },
  {
    name: "has_visuals",
    label: "Has visuals",
    valueEditorType: "select",
    values: [
      { name: "true", label: "Yes" },
      { name: "false", label: "No" },
    ],
  },
  { name: "active_minutes", label: "Observed active minutes", inputType: "number" },
  { name: "text", label: "Summary text" },
];

const OPERATORS = [
  { name: "equals", label: "is" },
  { name: "notEquals", label: "is not" },
  { name: "contains", label: "contains" },
  { name: "doesNotContain", label: "does not contain" },
  { name: "greaterThan", label: "is greater than" },
  { name: "greaterThanOrEqual", label: "is at least" },
  { name: "lessThan", label: "is less than" },
  { name: "lessThanOrEqual", label: "is at most" },
  { name: "between", label: "is between" },
  { name: "isNull", label: "is empty" },
  { name: "isNotNull", label: "is not empty" },
];

const DEFAULT_ORDER = [
  "last_activity_at",
  "short_description",
  "active_minutes",
  "status",
  "workspaces",
  "agents",
  "visual_count",
];

function formatObservedMinutes(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  if (!hours) return `${remainder}m`;
  return `${hours}h ${remainder}m`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

const columnHelper = createColumnHelper<SessionCatalogRow>();

export function SessionLibrary({
  apiUrl,
  authScheme,
  onSelectSession,
}: {
  apiUrl: string;
  authScheme?: string;
  onSelectSession: (threadId: string) => void;
}) {
  const [filters, setFilters] = useQueryState(
    "sessionFilters",
    parseAsJson<RuleGroupType>((value) => value as RuleGroupType).withDefault(
      defaultSessionFilters,
    ),
  );
  const [sorting, setSorting] = useQueryState(
    "sessionSort",
    parseAsJson<SortingState>((value) => value as SortingState).withDefault([
      { id: "last_activity_at", desc: true },
    ]),
  );
  const [columnOrder, setColumnOrder] = useQueryState(
    "sessionColumns",
    parseAsArrayOf(parseAsString).withDefault(DEFAULT_ORDER),
  );
  const [cursor, setCursor] = useQueryState("sessionCursor");
  const [pageSize, setPageSize] = useQueryState(
    "sessionPageSize",
    parseAsInteger.withDefault(25),
  );
  const [search, setSearch] = useQueryState(
    "sessionSearch",
    parseAsString.withDefault(""),
  );
  const [cursorHistory, setCursorHistory] = useState<(string | null)[]>([]);
  const [viewName, setViewName] = useState("");
  const [visibility, setVisibility] = useState<VisibilityState>({});
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [sessionName, setSessionName] = useState("");
  const queryClient = useQueryClient();

  const storeClient = useMemo(
    () => createClient(apiUrl, getApiKey() ?? undefined, authScheme),
    [apiUrl, authScheme],
  );

  const visibleColumns = columnOrder.filter((id) => visibility[id] !== false);
  const queryInput = {
    apiUrl,
    authScheme,
    filters,
    sorting,
    cursor,
    pageSize,
    search,
    visibleColumns,
  };
  const sessionQuery = useQuery({
    queryKey: ["session-catalog", queryInput],
    queryFn: () => fetchSessions(queryInput),
    enabled: Boolean(apiUrl),
    placeholderData: (previous) => previous,
  });
  const sessionIds = sessionQuery.data?.rows.map((row) => row.session_id) ?? [];
  const sessionNamesQuery = useQuery({
    queryKey: ["session-store-names", apiUrl, sessionIds],
    queryFn: async () =>
      Object.fromEntries(
        await Promise.all(
          sessionIds.map(async (sessionId) => {
            const item = await storeClient.store.getItem(
              [LOCAL_OWNER_ID, "sessions"],
              sessionId,
            );
            return [sessionId, item?.value.display_name] as const;
          }),
        ),
      ),
    enabled: Boolean(apiUrl && sessionIds.length),
  });
  const renameSession = useMutation({
    mutationFn: async ({ sessionId, name }: { sessionId: string; name: string }) => {
      const item = await storeClient.store.getItem(
        [LOCAL_OWNER_ID, "sessions"],
        sessionId,
      );
      if (!item) throw new Error("Session not found.");
      await storeClient.store.putItem(
        [LOCAL_OWNER_ID, "sessions"],
        sessionId,
        { ...item.value, display_name: name },
        { index: false },
      );
    },
    onSuccess: async () => {
      setEditingSessionId(null);
      await queryClient.invalidateQueries({ queryKey: ["session-store-names"] });
    },
  });

  const columns = useMemo(
    () => [
      columnHelper.accessor("last_activity_at", {
        header: "Last activity",
        cell: (info) => formatDate(info.getValue()),
      }),
      columnHelper.accessor("short_description", {
        header: "Session",
        cell: (info) => {
          const sessionId = info.row.original.session_id;
          const name =
            sessionNamesQuery.data?.[sessionId] ?? info.getValue();
          return (
          <div className="min-w-64 max-w-xl" onClick={(event) => event.stopPropagation()}>
            {editingSessionId === sessionId ? (
              <Input
                autoFocus
                aria-label="Session name"
                value={sessionName}
                onChange={(event) => setSessionName(event.target.value)}
                onBlur={() => setEditingSessionId(null)}
                onKeyDown={(event) => {
                  event.stopPropagation();
                  if (event.key === "Escape") setEditingSessionId(null);
                  if (event.key === "Enter" && sessionName.trim()) {
                    renameSession.mutate({ sessionId, name: sessionName.trim() });
                  }
                }}
              />
            ) : (
              <button
                type="button"
                className="font-medium hover:underline"
                onClick={() => {
                  setEditingSessionId(sessionId);
                  setSessionName(String(name));
                }}
                onKeyDown={(event) => event.stopPropagation()}
              >
                {String(name)}
              </button>
            )}
            <p className="text-muted-foreground mt-1 line-clamp-3 text-sm leading-5">
              {info.row.original.long_description}
            </p>
          </div>
          );
        },
      }),
      columnHelper.accessor("active_minutes", {
        header: "Observed time",
        cell: (info) => (
          <span title="Observed activity; idle periods longer than 15 minutes are excluded">
            {formatObservedMinutes(info.getValue())}
          </span>
        ),
      }),
      columnHelper.accessor("status", { header: "Status" }),
      columnHelper.accessor("workspaces", {
        header: "Workspaces",
        enableSorting: false,
        cell: (info) =>
          info.getValue().length
            ? info.getValue().map((workspace) => workspace.name).join(", ")
            : "None",
      }),
      columnHelper.accessor("agents", {
        header: "Agents",
        enableSorting: false,
        cell: (info) =>
          info.getValue().length
            ? info
                .getValue()
                .map((agent) =>
                  agent.profile_id === "research" ? "librarian" : agent.profile_id,
                )
                .join(", ")
            : "None",
      }),
      columnHelper.accessor("visual_count", {
        header: "Visuals",
        cell: (info) => (
          <span className="inline-flex items-center gap-1">
            <Workflow className="size-4" aria-hidden /> {info.getValue()}
          </span>
        ),
      }),
    ],
    [editingSessionId, renameSession, sessionName, sessionNamesQuery.data],
  );

  const savedViewsQuery = useQuery({
    queryKey: ["session-catalog-views", apiUrl],
    queryFn: () => fetchSavedSessionViews(apiUrl, authScheme),
    enabled: Boolean(apiUrl),
  });
  const saveView = useMutation({
    mutationFn: () => {
      const name = viewName.trim();
      if (!name) throw new Error("Enter a name for this view.");
      const viewId = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
      return saveSessionView(apiUrl, viewId, name, queryInput, authScheme);
    },
    onSuccess: async () => {
      setViewName("");
      await queryClient.invalidateQueries({ queryKey: ["session-catalog-views", apiUrl] });
    },
  });

  function applySavedView(view: SavedSessionView) {
    const nextFilters = view.query.filters as unknown as RuleGroupType;
    const nextSorting = view.query.sort.map((sort) => ({
      id: sort.field,
      desc: sort.direction === "desc",
    }));
    void setFilters(nextFilters);
    void setSorting(nextSorting);
    void setPageSize(view.query.page_size);
    void setSearch(view.query.search);
    if (view.query.visible_columns.length) {
      const nextOrder = [
        ...view.query.visible_columns,
        ...DEFAULT_ORDER.filter((id) => !view.query.visible_columns.includes(id)),
      ];
      void setColumnOrder(nextOrder);
      setVisibility(
        Object.fromEntries(DEFAULT_ORDER.map((id) => [id, view.query.visible_columns.includes(id)])),
      );
    }
    void setCursor(null);
    setCursorHistory([]);
  }
  const table = useReactTable({
    data: sessionQuery.data?.rows ?? [],
    columns,
    state: { sorting, columnOrder, columnVisibility: visibility },
    onSortingChange: (updater) => {
      const next = typeof updater === "function" ? updater(sorting) : updater;
      void setSorting(next);
      void setCursor(null);
      setCursorHistory([]);
    },
    onColumnOrderChange: (updater) => {
      const next = typeof updater === "function" ? updater(columnOrder) : updater;
      void setColumnOrder(next);
    },
    onColumnVisibilityChange: setVisibility,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    manualPagination: true,
    enableMultiSort: true,
  });

  function moveColumn(id: string, direction: -1 | 1) {
    const current = [...columnOrder];
    const index = current.indexOf(id);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= current.length) return;
    [current[index], current[target]] = [current[target], current[index]];
    void setColumnOrder(current);
  }

  return (
    <section className="flex h-full min-h-0 flex-col" aria-labelledby="session-library-title">
      <header className="border-b px-4 py-3 pr-40">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <h2 id="session-library-title" className="font-semibold">All sessions</h2>
            <p className="text-muted-foreground text-xs">
              {sessionQuery.data?.total ?? 0} owner-controlled knowledge-work sessions
            </p>
          </div>
          <label className="relative ml-auto min-w-52 flex-1 sm:max-w-sm">
            <span className="sr-only">Search sessions</span>
            <Search className="text-muted-foreground absolute top-2.5 left-2.5 size-4" />
            <Input
              value={search}
              onChange={(event) => {
                void setSearch(event.target.value);
                void setCursor(null);
                setCursorHistory([]);
              }}
              placeholder="Search session summaries"
              className="pl-8"
            />
          </label>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-auto p-4">
        <details className="bg-muted/20 mb-4 rounded-lg border p-3">
          <summary className="flex cursor-pointer list-none items-center gap-2 font-medium">
            <Filter className="size-4" /> Filter and arrange
          </summary>
          <div className="mt-4 space-y-4">
            <QueryBuilderShadcn>
              <QueryBuilder
                fields={SESSION_FIELDS}
                operators={OPERATORS}
                query={filters}
                onQueryChange={(next) => {
                  void setFilters(next);
                  void setCursor(null);
                  setCursorHistory([]);
                }}
                showNotToggle
                controlClassnames={{ queryBuilder: "queryBuilder-responsive" }}
              />
            </QueryBuilderShadcn>
            <fieldset>
              <legend className="mb-2 text-sm font-medium">Visible column order</legend>
              <div className="flex flex-wrap gap-2">
                {columnOrder.map((id, index) => {
                  const column = table.getColumn(id);
                  if (!column) return null;
                  return (
                    <span key={id} className="bg-background inline-flex items-center rounded-md border">
                      <label className="flex items-center gap-2 px-2 text-xs">
                        <input
                          type="checkbox"
                          checked={column.getIsVisible()}
                          onChange={column.getToggleVisibilityHandler()}
                        />
                        {typeof column.columnDef.header === "string" ? column.columnDef.header : id}
                      </label>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label={`Move ${id} left`}
                        disabled={index === 0}
                        onClick={() => moveColumn(id, -1)}
                      >
                        <ArrowUp className="size-3 -rotate-90" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label={`Move ${id} right`}
                        disabled={index === columnOrder.length - 1}
                        onClick={() => moveColumn(id, 1)}
                      >
                        <ArrowDown className="size-3 -rotate-90" />
                      </Button>
                    </span>
                  );
                })}
              </div>
            </fieldset>
            <div className="flex max-w-2xl flex-wrap gap-2">
              <label className="sr-only" htmlFor="saved-session-view">Load saved view</label>
              <select
                id="saved-session-view"
                className="bg-background min-w-48 rounded-md border px-3 text-sm"
                defaultValue=""
                onChange={(event) => {
                  const view = savedViewsQuery.data?.find((item) => item.view_id === event.target.value);
                  if (view) applySavedView(view);
                  event.target.value = "";
                }}
              >
                <option value="">Load saved view…</option>
                {savedViewsQuery.data?.map((view) => (
                  <option key={view.view_id} value={view.view_id}>{view.name}</option>
                ))}
              </select>
              <Input
                value={viewName}
                onChange={(event) => setViewName(event.target.value)}
                placeholder="Name this filter view"
                aria-label="Saved view name"
              />
              <Button onClick={() => saveView.mutate()} disabled={saveView.isPending}>
                <Save className="size-4" /> Save view
              </Button>
            </div>
            {saveView.error && (
              <p role="alert" className="text-destructive text-sm">{saveView.error.message}</p>
            )}
          </div>
        </details>

        {sessionQuery.isLoading ? (
          <div className="space-y-2" aria-label="Loading sessions">
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-16 w-full" />
            ))}
          </div>
        ) : sessionQuery.error ? (
          <div role="alert" className="border-destructive/40 bg-destructive/5 rounded-lg border p-4">
            <p className="font-medium">The session library could not be loaded.</p>
            <p className="text-muted-foreground mt-1 text-sm">{sessionQuery.error.message}</p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-muted/50 sticky top-0 z-10">
                {table.getHeaderGroups().map((headerGroup) => (
                  <tr key={headerGroup.id}>
                    {headerGroup.headers.map((header) => (
                      <th key={header.id} scope="col" className="border-b px-3 py-2 font-medium">
                        {header.isPlaceholder ? null : header.column.getCanSort() ? (
                          <button
                            className="inline-flex items-center gap-1 text-left"
                            onClick={header.column.getToggleSortingHandler()}
                            title="Sort; hold Shift to combine sorts"
                          >
                            {flexRender(header.column.columnDef.header, header.getContext())}
                            {header.column.getIsSorted() === "asc" ? " ↑" : header.column.getIsSorted() === "desc" ? " ↓" : null}
                          </button>
                        ) : (
                          flexRender(header.column.columnDef.header, header.getContext())
                        )}
                      </th>
                    ))}
                  </tr>
                ))}
              </thead>
              <tbody>
                {table.getRowModel().rows.map((row) => (
                  <tr
                    key={row.id}
                    tabIndex={0}
                    className="hover:bg-muted/40 focus-visible:ring-ring cursor-pointer border-b last:border-b-0 focus-visible:ring-2 focus-visible:outline-none"
                    onClick={() => onSelectSession(row.original.thread_id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        onSelectSession(row.original.thread_id);
                      }
                    }}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-3 py-3 align-top">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                ))}
                {!table.getRowModel().rows.length && (
                  <tr><td colSpan={visibleColumns.length} className="text-muted-foreground p-8 text-center">No sessions match these filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <footer className="flex items-center justify-between gap-3 border-t px-4 py-2">
        <label className="text-muted-foreground flex items-center gap-2 text-xs">
          Rows
          <select
            className="bg-background rounded border px-2 py-1"
            value={pageSize}
            onChange={(event) => {
              void setPageSize(Number(event.target.value));
              void setCursor(null);
              setCursorHistory([]);
            }}
          >
            {[10, 25, 50, 100].map((size) => <option key={size}>{size}</option>)}
          </select>
        </label>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={!cursorHistory.length}
            onClick={() => {
              const previous = cursorHistory.at(-1) ?? null;
              setCursorHistory((history) => history.slice(0, -1));
              void setCursor(previous);
            }}
          >Previous</Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!sessionQuery.data?.next_cursor}
            onClick={() => {
              setCursorHistory((history) => [...history, cursor]);
              void setCursor(sessionQuery.data?.next_cursor ?? null);
            }}
          >Next</Button>
        </div>
      </footer>
    </section>
  );
}
