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
  await page.route("http://127.0.0.1:8123/runtime-identity", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        runtime_id: "backend-postgres-v1",
        durable: true,
        persistence: "postgres",
      }),
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
  const answerShell = page.locator("[data-answer-shell]").last();
  await expect(answerShell).toBeVisible();
  await expect(answerShell.locator("[data-answer-anchor-top]")).toHaveCount(1);
  await expect(answerShell.locator("[data-answer-anchor-bottom]")).toHaveCount(
    1,
  );
});

test("newly created threads top-anchor the submitted user turn once", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const originalScrollTo = HTMLElement.prototype.scrollTo;
    const target = window as typeof window & {
      __conversationScrolls?: Array<{
        top: number;
        behavior?: ScrollBehavior;
      }>;
    };
    target.__conversationScrolls = [];
    HTMLElement.prototype.scrollTo = function (
      options?: ScrollToOptions | number,
      y?: number,
    ) {
      if (
        this.matches("[data-conversation-viewport]") &&
        options !== undefined
      ) {
        const value =
          typeof options === "number"
            ? { top: y ?? options }
            : {
                top: options.top ?? this.scrollTop,
                behavior: options.behavior,
              };
        target.__conversationScrolls?.push(value);
      }
      return (originalScrollTo as (...args: unknown[]) => void).call(
        this,
        options,
        y,
      );
    };
  });

  await submitToJasper(page, "Anchor this new turn");
  await expect
    .poll(
      () =>
        page.evaluate(
          () =>
            (
              window as typeof window & {
                __conversationScrolls?: Array<{ behavior?: string }>;
              }
            ).__conversationScrolls?.length ?? 0,
        ),
      { timeout: 5000 },
    )
    .toBeGreaterThan(0);
  const placement = await page.evaluate(() => {
    const viewport = document.querySelector<HTMLElement>(
      "[data-conversation-viewport]",
    );
    const anchor = document.querySelector<HTMLElement>(
      '[data-conversation-arrival-anchor-top^="assistant:"]',
    );
    if (!viewport || !anchor) throw new Error("conversation anchor missing");
    return {
      scrolls: (window as typeof window & { __conversationScrolls?: unknown[] })
        .__conversationScrolls,
      hasArrivalAnchor: Boolean(anchor),
      viewportHeight: viewport.clientHeight,
    };
  });

  expect(placement.scrolls).toEqual(
    expect.arrayContaining([expect.objectContaining({ behavior: "auto" })]),
  );
  expect(placement.hasArrivalAnchor).toBe(true);
  expect(placement.viewportHeight).toBeGreaterThan(0);
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
