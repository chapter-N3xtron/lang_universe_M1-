import { expect, test, type Page } from "@playwright/test";

const THREAD_A = "empty-repository-thread";
const THREAD_B = "sibling-repository-thread";
const EMPTY_REPOSITORY =
  "/Users/chaptercaptaingeneral/programatic_3d_rendering";
const PICKED_REPOSITORY =
  "/Users/chaptercaptaingeneral/programatic_3d_rendering-empty";
const SIBLING_REPOSITORY = "/Users/chaptercaptaingeneral/another-project";

function history(threadId: string, workspace: string) {
  return [
    {
      values: { messages: [], workspace },
      next: [],
      tasks: [],
      metadata: {},
      created_at: "2026-08-14T00:00:00Z",
      checkpoint: {
        thread_id: threadId,
        checkpoint_ns: "",
        checkpoint_id: `${threadId}-checkpoint`,
      },
      parent_checkpoint: null,
    },
  ];
}

async function installRoutes(page: Page) {
  const workspaces: Record<string, string> = {
    [THREAD_A]: EMPTY_REPOSITORY,
    [THREAD_B]: SIBLING_REPOSITORY,
  };
  const runBodies: Record<string, unknown>[] = [];
  let pickerStartingPath: string | null = null;

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
  await page.route("**/threads/search", (route) =>
    route.fulfill({ contentType: "application/json", body: "[]" }),
  );
  await page.route("**/api/models", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ default: "mock/model", models: [] }),
    }),
  );
  await page.route("**/api/tts/voices", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ voices: [] }),
    }),
  );
  await page.route("**/session-catalog/preferences/model**", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ model_id: null }),
    }),
  );
  await page.route("**/threads/*/history", (route) => {
    const match = new URL(route.request().url()).pathname.match(
      /\/threads\/([^/]+)\/history$/,
    );
    const threadId = match?.[1] ?? THREAD_A;
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(history(threadId, workspaces[threadId])),
    });
  });
  await page.route("http://127.0.0.1:8000/api/fs/pick-folder**", (route) => {
    pickerStartingPath = new URL(route.request().url()).searchParams.get(
      "starting_path",
    );
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ cancelled: false, path: PICKED_REPOSITORY }),
    });
  });
  await page.route("**/threads/*/runs/stream", async (route) => {
    const body = route.request().postDataJSON() as {
      input?: { workspace?: string };
    };
    runBodies.push(body as Record<string, unknown>);
    const match = new URL(route.request().url()).pathname.match(
      /\/threads\/([^/]+)\/runs\/stream$/,
    );
    if (match?.[1] && body.input?.workspace) {
      workspaces[match[1]] = body.input.workspace;
    }
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "event: end\ndata: {}\n\n",
    });
  });

  return {
    runBodies,
    pickerStartingPath: () => pickerStartingPath,
  };
}

async function switchThread(page: Page, threadId: string) {
  await page.evaluate((nextThreadId) => {
    const url = new URL(window.location.href);
    url.searchParams.set("threadId", nextThreadId);
    window.history.pushState({}, "", url);
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, threadId);
  await expect(page).toHaveURL(new RegExp(`threadId=${threadId}`));
}

test("hydrates, drafts, submits, and reopens the exact workspace per thread", async ({
  page,
}) => {
  const routes = await installRoutes(page);
  await page.goto(
    `/?threadId=${THREAD_A}&apiUrl=http%3A%2F%2Fmock&assistantId=agent`,
  );

  const workspace = page.getByTestId("effective-workspace");
  await expect(workspace).toHaveText(EMPTY_REPOSITORY);
  await expect(workspace).not.toHaveText("/Users/chaptercaptaingeneral");
  await expect(workspace).not.toHaveText("/workspace");

  await page.getByRole("button", { name: "Select repository folder" }).click();
  await expect(workspace).toHaveText(PICKED_REPOSITORY);
  expect(routes.pickerStartingPath()).toBe(EMPTY_REPOSITORY);

  await switchThread(page, THREAD_B);
  await expect(workspace).toHaveText(SIBLING_REPOSITORY);
  await expect(workspace).not.toContainText(PICKED_REPOSITORY);

  await switchThread(page, THREAD_A);
  await expect(workspace).toHaveText(PICKED_REPOSITORY);

  await page.locator("textarea").fill("Initialize this empty repository only");
  await page.locator("textarea").press("Enter");
  await expect.poll(() => routes.runBodies.length).toBe(1);
  expect((routes.runBodies[0].input as { workspace?: string }).workspace).toBe(
    PICKED_REPOSITORY,
  );

  await page.reload();
  await expect(workspace).toHaveText(PICKED_REPOSITORY);
});
