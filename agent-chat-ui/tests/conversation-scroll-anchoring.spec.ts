import { expect, test, type Page } from "@playwright/test";

const THREAD_A = "scroll-thread-a";
const THREAD_B = "scroll-thread-b";

function historyState(threadId: string, count = 36) {
  const messages = Array.from({ length: count }, (_, index) => ({
    id: `${threadId}-message-${index}`,
    type: index % 2 === 0 ? "human" : "ai",
    content: `${threadId} historical message ${index} `.repeat(8),
  }));
  return {
    values: { messages },
    next: [],
    tasks: [],
    metadata: {},
    created_at: "2026-07-30T00:00:00Z",
    checkpoint: {
      thread_id: threadId,
      checkpoint_ns: "",
      checkpoint_id: `${threadId}-checkpoint`,
    },
    parent_checkpoint: null,
  };
}

async function installBaseRoutes(page: Page) {
  await page.route("**/threads/search", (route) =>
    route.fulfill({ contentType: "application/json", body: "[]" }),
  );
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
    route.fulfill({ contentType: "application/json", body: '{"voices":[]}' }),
  );
  await page.route("**/threads", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        thread_id: THREAD_A,
        created_at: "2026-07-30T00:00:00Z",
        updated_at: "2026-07-30T00:00:00Z",
        metadata: {},
        status: "idle",
        values: {},
      }),
    }),
  );
}

async function installScrollRecorder(page: Page) {
  await page.addInitScript(() => {
    const originalScrollTo = HTMLElement.prototype.scrollTo;
    const target = window as typeof window & {
      __conversationPlacements?: Array<{
        top: number;
        behavior?: ScrollBehavior;
        anchors: string[];
      }>;
    };
    target.__conversationPlacements = [];
    HTMLElement.prototype.scrollTo = function (
      options?: ScrollToOptions | number,
      y?: number,
    ) {
      if (
        this.matches("[data-conversation-viewport]") &&
        options !== undefined
      ) {
        target.__conversationPlacements?.push({
          top:
            typeof options === "number"
              ? (y ?? options)
              : (options.top ?? this.scrollTop),
          behavior: typeof options === "number" ? undefined : options.behavior,
          anchors: Array.from(
            this.querySelectorAll<HTMLElement>(
              "[data-conversation-arrival-anchor-top]",
            ),
          ).map((anchor) => anchor.dataset.conversationArrivalAnchorTop ?? ""),
        });
      }
      (originalScrollTo as (...args: unknown[]) => void).call(this, options, y);
      if (typeof options === "number") this.scrollTop = y ?? options;
      else if (options?.top != null) this.scrollTop = options.top;
    };
  });
}

async function expectAnchorNearTop(page: Page, selector: string) {
  await expect
    .poll(async () =>
      page
        .locator(selector)
        .last()
        .evaluate((element) => {
          const viewport = element.closest("[data-conversation-viewport]");
          if (!viewport) throw new Error("conversation viewport missing");
          const anchorRect = element.getBoundingClientRect();
          const viewportRect = viewport.getBoundingClientRect();
          return anchorRect.top - viewportRect.top;
        }),
    )
    .toBeCloseTo(32, 0);
}

async function installHydratedThread(page: Page, threadId: string, count = 36) {
  await page.route(`**/threads/${threadId}/history`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([historyState(threadId, count)]),
    }),
  );
}

test.describe("conversation scroll anchoring", () => {
  test("preserves later user scroll after a submitted user turn", async ({
    page,
  }) => {
    await installScrollRecorder(page);
    await installBaseRoutes(page);
    await installHydratedThread(page, THREAD_A);

    await page.goto(`/?threadId=${THREAD_A}`);
    await expect(
      page.locator(`[data-message-id="${THREAD_A}-message-35"]`),
    ).toBeVisible();
    await expectAnchorNearTop(
      page,
      `[data-message-id="${THREAD_A}-message-35"]`,
    );

    const textarea = page.locator("textarea");
    await textarea.fill("new user turn");
    await textarea.press("Enter");
    await expect(
      page.getByText("new user turn", { exact: true }),
    ).toBeVisible();
    const placementCount = await page.evaluate(
      () =>
        (window as typeof window & { __conversationPlacements?: unknown[] })
          .__conversationPlacements?.length ?? 0,
    );
    await page.locator("[data-conversation-viewport]").evaluate((viewport) => {
      (viewport as HTMLElement).scrollTop = 0;
      viewport.dispatchEvent(new Event("scroll"));
    });
    await page.waitForTimeout(300);
    await expect(page.locator("[data-conversation-viewport]")).toHaveJSProperty(
      "scrollTop",
      0,
    );
    await expect
      .poll(() =>
        page.evaluate(
          () =>
            (window as typeof window & { __conversationPlacements?: unknown[] })
              .__conversationPlacements?.length ?? 0,
        ),
      )
      .toBe(placementCount);
  });

  test("does not repeatedly move after the submitted turn arrives", async ({
    page,
  }) => {
    await installScrollRecorder(page);
    await installBaseRoutes(page);
    await installHydratedThread(page, THREAD_A);

    await page.goto(`/?threadId=${THREAD_A}`);
    await expect(
      page.locator(`[data-message-id="${THREAD_A}-message-35"]`),
    ).toBeVisible();
    await expectAnchorNearTop(
      page,
      `[data-message-id="${THREAD_A}-message-35"]`,
    );
    await page.evaluate(() => {
      const target = window as typeof window & {
        __conversationPlacements?: unknown[];
      };
      target.__conversationPlacements = [];
    });
    await page.locator("textarea").fill("new user turn");
    await page.locator("textarea").press("Enter");
    await expect(
      page.locator("[data-conversation-arrival-anchor-top^='human:']"),
    ).toHaveCount(1);
    const placements = await page.evaluate(
      () =>
        (window as typeof window & { __conversationPlacements?: unknown[] })
          .__conversationPlacements ?? [],
    );
    expect(placements).toHaveLength(1);
    expect(placements.at(-1)).toEqual(
      expect.objectContaining({ behavior: "auto" }),
    );

    await page.locator("[data-conversation-viewport]").evaluate((viewport) => {
      (viewport as HTMLElement).scrollTop = 0;
      viewport.dispatchEvent(new Event("scroll"));
    });
    await page.waitForTimeout(300);
    await expect(page.locator("[data-conversation-viewport]")).toHaveJSProperty(
      "scrollTop",
      0,
    );
    expect(
      await page.evaluate(
        () =>
          (window as typeof window & { __conversationPlacements?: unknown[] })
            .__conversationPlacements?.length ?? 0,
      ),
    ).toBe(1);
  });

  test("reopens hydrated and forked threads with the latest message top-anchored once, including reduced motion", async ({
    page,
  }) => {
    await installScrollRecorder(page);
    await installBaseRoutes(page);
    await installHydratedThread(page, THREAD_A);
    await installHydratedThread(page, THREAD_B, 12);
    await page.emulateMedia({ reducedMotion: "reduce" });

    await page.goto(`/?threadId=${THREAD_A}`);
    await expect(
      page.locator(`[data-message-id="${THREAD_A}-message-35"]`),
    ).toBeVisible();
    await expectAnchorNearTop(
      page,
      `[data-message-id="${THREAD_A}-message-35"]`,
    );
    const firstCount = await page.evaluate(
      () =>
        (window as typeof window & { __conversationPlacements?: unknown[] })
          .__conversationPlacements?.length ?? 0,
    );
    expect(firstCount).toBe(1);
    expect(
      await page.evaluate(() =>
        document.documentElement.outerHTML.includes("viewport"),
      ),
    ).toBe(true);

    await page.goto(`/?threadId=${THREAD_B}`);
    await expect(
      page.locator(`[data-message-id="${THREAD_B}-message-11"]`),
    ).toBeVisible();
    await expectAnchorNearTop(
      page,
      `[data-message-id="${THREAD_B}-message-11"]`,
    );
    expect(
      await page.evaluate(
        () =>
          (window as typeof window & { __conversationPlacements?: unknown[] })
            .__conversationPlacements?.length ?? 0,
      ),
    ).toBe(1);
  });

  test("does not place an empty session and reports history errors without a placement", async ({
    page,
  }) => {
    await installScrollRecorder(page);
    await installBaseRoutes(page);
    await page.route(`**/threads/empty-thread/history`, (route) =>
      route.fulfill({
        contentType: "application/json",
        body: JSON.stringify([]),
      }),
    );
    await page.route(`**/threads/error-thread/history`, (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: "history unavailable",
      }),
    );

    await page.goto("/?threadId=empty-thread");
    await expect(page.locator("textarea")).toBeVisible();
    await page.waitForTimeout(300);
    await expect(page.locator("[data-conversation-viewport]")).toHaveJSProperty(
      "scrollTop",
      0,
    );
    expect(
      await page.evaluate(
        () =>
          (window as typeof window & { __conversationPlacements?: unknown[] })
            .__conversationPlacements?.length ?? 0,
      ),
    ).toBe(0);

    await page.goto("/?threadId=error-thread");
    await expect(page.locator("textarea")).toBeVisible();
    await page.waitForTimeout(300);
    expect(
      await page.evaluate(
        () =>
          (window as typeof window & { __conversationPlacements?: unknown[] })
            .__conversationPlacements?.length ?? 0,
      ),
    ).toBe(0);
  });
});
