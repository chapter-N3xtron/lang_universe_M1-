import { expect, test, type Page } from "@playwright/test";

const THREAD_ID = "phase2-persistence-thread";
const AI_MESSAGE = {
  id: "phase2-ai",
  type: "ai",
  content: [{ type: "text", text: "Jasper is ready." }],
};

async function installLangGraphMock(page: Page) {
  let persistedMessages: unknown[] = [];

  await page.route("**/threads/search", (route) =>
    route.fulfill({ contentType: "application/json", body: "[]" }),
  );
  await page.route("http://127.0.0.1:8123/info", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ assistant_id: "chat_ui", graph_id: "chat_ui" }),
    }),
  );
  await page.route("http://127.0.0.1:8000/api/models", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        default: "ollama-cloud/test",
        models: [
          {
            id: "ollama-cloud/test",
            name: "Test cloud model",
            provider: "ollama-cloud",
          },
        ],
      }),
    }),
  );
  await page.route("http://127.0.0.1:8000/api/tts/voices", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ voices: ["alba"], total: 1 }),
    }),
  );
  await page.route("http://127.0.0.1:8123/threads", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        thread_id: THREAD_ID,
        created_at: "2026-07-30T00:00:00Z",
        updated_at: "2026-07-30T00:00:00Z",
        metadata: {},
        status: "idle",
        values: {},
      }),
    }),
  );
  await page.route("**/threads/*/runs/stream", async (route) => {
    const request = route.request().postDataJSON() as {
      input?: { messages?: unknown[] };
    };
    const humanMessage = request.input?.messages?.at(-1);
    persistedMessages = humanMessage
      ? [humanMessage, AI_MESSAGE]
      : [AI_MESSAGE];
    const body = [
      "event: metadata",
      `data: ${JSON.stringify({ run_id: "phase2-run", thread_id: THREAD_ID })}`,
      "",
      "event: messages",
      `data: ${JSON.stringify([AI_MESSAGE, { langgraph_node: "jasper" }])}`,
      "",
      "event: end",
      "data: {}",
      "",
    ].join("\n");
    await route.fulfill({ contentType: "text/event-stream", body });
  });
  await page.route("**/threads/*/history", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          values: { messages: persistedMessages },
          next: [],
          tasks: [],
          metadata: {},
          created_at: "2026-07-30T00:00:01Z",
          checkpoint: {
            thread_id: THREAD_ID,
            checkpoint_ns: "",
            checkpoint_id: "phase2-checkpoint",
          },
          parent_checkpoint: null,
        },
      ]),
    }),
  );
}

async function submitToJasper(page: Page, prompt: string) {
  await page.goto("/");
  const textarea = page.locator("textarea");
  await expect(textarea).toBeVisible({ timeout: 10000 });
  await expect(page.getByLabel("Select agent")).toHaveText("Jasper");
  await textarea.fill(prompt);
  await textarea.press("Enter");
  await expect(
    page.getByText("Jasper is ready.", { exact: true }),
  ).toBeVisible();
}

test.beforeEach(async ({ page }) => installLangGraphMock(page));

test("basic chat smoke test", async ({ page }) => {
  await submitToJasper(page, "Hello, who are you?");
  await expect(page.getByRole("button", { name: "Read aloud" })).toBeVisible();
});

test("thread persistence", async ({ page }) => {
  const prompt = "Remember this: the secret code is 42";
  await submitToJasper(page, prompt);
  await expect(page).toHaveURL(new RegExp(`threadId=${THREAD_ID}`));

  await page.reload();

  await expect(page.getByText(prompt, { exact: true })).toBeVisible();
  await expect(
    page.getByText("Jasper is ready.", { exact: true }),
  ).toBeVisible();
});
