import type { RuleGroupType, RuleType } from "react-querybuilder";
import type { SortingState } from "@tanstack/react-table";
import { getApiKey } from "@/lib/api-key";

export const LOCAL_OWNER_ID = "local-owner-v1";

export type WorkspaceSummary = {
  workspace_id: string;
  name: string;
  repository_binding_state: "bound" | "unbound" | "unavailable";
};

export type AgentSummary = {
  profile_id: string;
  profile_version: string;
  role: string;
};

export type SessionCatalogRow = {
  session_id: string;
  thread_id: string;
  parent_session_id: string | null;
  parent_thread_id: string | null;
  created_at: string;
  last_activity_at: string;
  short_description: string;
  long_description: string;
  active_minutes: number;
  active_time_observed: boolean;
  status: "open" | "closed" | "forked";
  workspaces: WorkspaceSummary[];
  agents: AgentSummary[];
  visual_count: number;
  has_visuals: boolean;
  summary_version: number;
};

export type SessionQueryResponse = {
  rows: SessionCatalogRow[];
  next_cursor: string | null;
  total: number;
};

export const defaultSessionFilters: RuleGroupType = {
  combinator: "and",
  rules: [],
};

function serializeRule(
  rule: RuleType | RuleGroupType,
): Record<string, unknown> {
  if ("rules" in rule) {
    return {
      kind: "group",
      combinator: rule.combinator === "or" ? "or" : "and",
      rules: rule.rules.map((child) =>
        serializeRule(child as RuleType | RuleGroupType),
      ),
      not: Boolean(rule.not),
    };
  }
  let value = rule.value ?? null;
  if (rule.field === "has_visuals" && typeof value === "string") {
    value = value === "true";
  } else if (rule.field === "active_minutes" && typeof value === "string") {
    value = value.includes(",")
      ? value.split(",").map((part) => Number(part.trim()))
      : Number(value);
  }
  return {
    kind: "rule",
    field: rule.field,
    operator: rule.operator,
    value,
  };
}

function headers(authScheme?: string) {
  const result = new Headers({ "Content-Type": "application/json" });
  const apiKey = getApiKey();
  if (apiKey) result.set("X-Api-Key", apiKey);
  if (authScheme) result.set("X-Auth-Scheme", authScheme);
  return result;
}

async function checkedJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      body.detail || `Session catalog request failed (${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}

export async function fetchSessions(input: {
  apiUrl: string;
  authScheme?: string;
  filters: RuleGroupType;
  sorting: SortingState;
  cursor: string | null;
  pageSize: number;
  search: string;
  visibleColumns: string[];
}): Promise<SessionQueryResponse> {
  const response = await fetch(`${input.apiUrl}/session-catalog/query`, {
    method: "POST",
    headers: headers(input.authScheme),
    body: JSON.stringify({
      owner_id: LOCAL_OWNER_ID,
      filters: serializeRule(input.filters),
      sort: input.sorting.map((sort) => ({
        field: sort.id,
        direction: sort.desc ? "desc" : "asc",
      })),
      cursor: input.cursor,
      page_size: input.pageSize,
      search: input.search,
      visible_columns: input.visibleColumns,
    }),
  });
  return checkedJson(response);
}

export type SessionArtifactEntry = {
  artifact: Record<string, unknown>;
  relationship: "created" | "inherited" | "deep_dive";
  position: number;
  linked_at: string;
};

export type SessionDetail = {
  session_id: string;
  thread_id: string;
  status: "open" | "closed" | "forked";
  short_description: string;
  long_description: string;
  parent_session_id: string | null;
  parent_thread_id: string | null;
  created_at: string;
  last_activity_at: string;
  active_minutes: number;
  tent_poles: string[];
};

export type SavedSessionView = {
  owner_id: string;
  view_id: string;
  name: string;
  query: {
    filters: Record<string, unknown>;
    sort: { field: string; direction: "asc" | "desc" }[];
    page_size: number;
    search: string;
    visible_columns: string[];
  };
};

export async function fetchSessionDetail(
  apiUrl: string,
  sessionId: string,
  authScheme?: string,
): Promise<SessionDetail> {
  const response = await fetch(
    `${apiUrl}/session-catalog/${encodeURIComponent(sessionId)}?owner_id=${encodeURIComponent(LOCAL_OWNER_ID)}`,
    { headers: headers(authScheme) },
  );
  return checkedJson(response);
}

export async function renameSessionArtifact(
  apiUrl: string,
  sessionId: string,
  artifactId: string,
  title: string,
  authScheme?: string,
) {
  const response = await fetch(
    `${apiUrl}/session-catalog/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent(artifactId)}`,
    {
      method: "PUT",
      headers: headers(authScheme),
      body: JSON.stringify({ owner_id: LOCAL_OWNER_ID, title }),
    },
  );
  return checkedJson<{ artifact_id: string; title: string }>(response);
}

export async function deleteSessionArtifact(
  apiUrl: string,
  sessionId: string,
  artifactId: string,
  authScheme?: string,
) {
  const response = await fetch(
    `${apiUrl}/session-catalog/${encodeURIComponent(sessionId)}/artifacts/${encodeURIComponent(artifactId)}?owner_id=${encodeURIComponent(LOCAL_OWNER_ID)}`,
    { method: "DELETE", headers: headers(authScheme) },
  );
  return checkedJson<{ deleted: boolean }>(response);
}

export async function fetchSessionArtifacts(
  apiUrl: string,
  sessionId: string,
  authScheme?: string,
): Promise<SessionArtifactEntry[]> {
  const response = await fetch(
    `${apiUrl}/session-catalog/${encodeURIComponent(sessionId)}/artifacts?owner_id=${encodeURIComponent(LOCAL_OWNER_ID)}`,
    { headers: headers(authScheme) },
  );
  const result = await checkedJson<{ artifacts: SessionArtifactEntry[] }>(
    response,
  );
  return result.artifacts;
}

export async function saveSessionView(
  apiUrl: string,
  viewId: string,
  name: string,
  query: Parameters<typeof fetchSessions>[0],
  authScheme?: string,
) {
  const response = await fetch(
    `${apiUrl}/session-catalog/views/saved/${encodeURIComponent(viewId)}`,
    {
      method: "PUT",
      headers: headers(authScheme),
      body: JSON.stringify({
        owner_id: LOCAL_OWNER_ID,
        view_id: viewId,
        name,
        query: {
          owner_id: LOCAL_OWNER_ID,
          filters: serializeRule(query.filters),
          sort: query.sorting.map((sort) => ({
            field: sort.id,
            direction: sort.desc ? "desc" : "asc",
          })),
          cursor: null,
          page_size: query.pageSize,
          search: query.search,
          visible_columns: query.visibleColumns,
        },
      }),
    },
  );
  return checkedJson(response);
}

export async function fetchSavedSessionViews(
  apiUrl: string,
  authScheme?: string,
): Promise<SavedSessionView[]> {
  const response = await fetch(
    `${apiUrl}/session-catalog/views/saved?owner_id=${encodeURIComponent(LOCAL_OWNER_ID)}`,
    { headers: headers(authScheme) },
  );
  const result = await checkedJson<{ views: SavedSessionView[] }>(response);
  return result.views;
}

export async function closeSession(
  apiUrl: string,
  sessionId: string,
  summary: string,
  tentPoles: string[],
  authScheme?: string,
) {
  const response = await fetch(
    `${apiUrl}/session-catalog/${encodeURIComponent(sessionId)}/close`,
    {
      method: "POST",
      headers: headers(authScheme),
      body: JSON.stringify({
        owner_id: LOCAL_OWNER_ID,
        summary,
        tent_poles: tentPoles,
      }),
    },
  );
  return checkedJson<{ session_id: string; status: "closed" }>(response);
}

export async function openSession(apiUrl: string, authScheme?: string) {
  const response = await fetch(`${apiUrl}/session-catalog/open`, {
    method: "POST",
    headers: headers(authScheme),
    body: JSON.stringify({ owner_id: LOCAL_OWNER_ID }),
  });
  return checkedJson<{ thread_id: string; status: "open" }>(response);
}

export async function fetchModelPreference(
  apiUrl: string,
  authScheme?: string,
) {
  const response = await fetch(
    `${apiUrl}/session-catalog/preferences/model?owner_id=${encodeURIComponent(LOCAL_OWNER_ID)}`,
    { headers: headers(authScheme) },
  );
  return checkedJson<{ model_id: string | null }>(response);
}

export async function saveModelPreference(
  apiUrl: string,
  modelId: string,
  authScheme?: string,
) {
  const response = await fetch(`${apiUrl}/session-catalog/preferences/model`, {
    method: "PUT",
    headers: headers(authScheme),
    body: JSON.stringify({ owner_id: LOCAL_OWNER_ID, model_id: modelId }),
  });
  return checkedJson<{ model_id: string }>(response);
}

export async function forkSession(
  apiUrl: string,
  sessionId: string,
  authScheme?: string,
) {
  const response = await fetch(
    `${apiUrl}/session-catalog/${encodeURIComponent(sessionId)}/fork`,
    {
      method: "POST",
      headers: headers(authScheme),
      body: JSON.stringify({ owner_id: LOCAL_OWNER_ID }),
    },
  );
  return checkedJson<{ thread_id: string; parent_session_id: string }>(
    response,
  );
}
