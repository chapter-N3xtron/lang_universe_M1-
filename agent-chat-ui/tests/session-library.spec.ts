import { expect, test, type Page } from "@playwright/test";

const rows = [
  {
    session_id: "session-one",
    thread_id: "session-one",
    parent_session_id: null,
    parent_thread_id: null,
    created_at: "2026-08-01T14:00:00Z",
    last_activity_at: "2026-08-02T14:00:00Z",
    short_description: "Design the durable session library",
    long_description:
      "Jasper and the human defined workspace links, observed time, visual history, and neutral break reminders.",
    active_minutes: 102,
    active_time_observed: true,
    status: "open",
    workspaces: [
      {
        workspace_id: "workspace-one",
        name: "LangGraph_AgentChat_ui_Opencode_CLI",
        repository_binding_state: "bound",
      },
    ],
    agents: [
      { profile_id: "jasper", profile_version: "1", role: "participant" },
      { profile_id: "coding", profile_version: "1", role: "participant" },
    ],
    visual_count: 2,
    has_visuals: true,
    summary_version: 3,
  },
];

async function mockBase(page: Page) {
  await page.route("**/threads/search", (route) =>
    route.fulfill({ contentType: "application/json", body: "[]" }),
  );
  await page.route("**/threads/session-one/history", (route) =>
    route.fulfill({ contentType: "application/json", body: "[]" }),
  );
  await page.route("**/session-catalog/session-one/artifacts**", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: '{"artifacts":[]}',
    }),
  );
  await page.route("**/session-catalog/session-one?**", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ...rows[0],
        tent_poles: ["Keep the session owner controlled"],
      }),
    }),
  );
  await page.route("**/session-catalog/views/saved?**", (route) =>
    route.fulfill({ contentType: "application/json", body: '{"views":[]}' }),
  );
  await page.route("**/session-catalog/query", async (route) => {
    const body = route.request().postDataJSON();
    expect(body.owner_id).toBe("local-owner-v1");
    expect(body).not.toHaveProperty("raw_sql");
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ rows, next_cursor: null, total: 1 }),
    });
  });
  await page.route("**/info", (route) =>
    route.fulfill({ contentType: "application/json", body: "{}" }),
  );
  await page.route("**/runtime-identity", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        runtime_id: "backend-postgres-v1",
        durable: true,
        persistence: "postgres",
      }),
    }),
  );
  await page.route("**/api/models", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ default: "ollama/test", models: [] }),
    }),
  );
  await page.route("**/api/tts/voices", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ voices: [] }),
    }),
  );
}

test.beforeEach(async ({ page }) => mockBase(page));

test("visual pane presents a sortable, keyboard-openable session library", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Focus visual" }).click();

  await expect(
    page.getByRole("heading", { name: "All sessions" }),
  ).toBeVisible();
  await expect(
    page.getByText("Design the durable session library"),
  ).toBeVisible();
  await expect(page.getByText("1h 42m")).toBeVisible();
  await expect(
    page.getByText("LangGraph_AgentChat_ui_Opencode_CLI"),
  ).toBeVisible();
  await expect(page.getByText("jasper, coding")).toBeVisible();

  const sessionRow = page.getByRole("row").filter({
    hasText: "Design the durable session library",
  });
  await sessionRow.focus();
  await sessionRow.press("Enter");
  await expect(page).toHaveURL(/threadId=session-one/);
  await expect(
    page.getByRole("button", { name: "All sessions" }),
  ).toBeVisible();
});

test("sorting, search, and column order are URL-persisted", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Focus visual" }).click();
  await expect(
    page.getByText("Design the durable session library"),
  ).toBeVisible();

  await page.getByRole("button", { name: /Session/ }).click();
  await page.getByPlaceholder("Search session summaries").fill("durable");
  await page.getByText("Filter and arrange").click();
  await page.getByRole("button", { name: "Move visual_count left" }).click();

  await expect(page).toHaveURL(/sessionSort=/);
  await expect(page).toHaveURL(/sessionSearch=durable/);
  await expect(page).toHaveURL(/sessionColumns=/);
  await page.reload();
  await expect(page.getByPlaceholder("Search session summaries")).toHaveValue(
    "durable",
  );
});

test("session review is keyboard reachable and keeps repository actions separate", async ({
  page,
}) => {
  await page.goto("/?threadId=session-one&sessionView=session");
  await page.getByRole("button", { name: "Focus visual" }).click();

  const closeButton = page.getByRole("button", { name: "Close session" });
  await closeButton.focus();
  await closeButton.press("Enter");

  await expect(
    page.getByRole("heading", { name: "Review this session before closing" }),
  ).toBeVisible();
  await expect(page.getByLabel("Session summary")).toHaveValue(
    rows[0].long_description,
  );
  await expect(page.getByLabel("Tent poles, one per line")).toHaveValue(
    "Keep the session owner controlled",
  );
  await expect(page.getByText(/does not commit or push/)).toBeVisible();
  await page.getByRole("button", { name: "Keep open" }).click();
});
