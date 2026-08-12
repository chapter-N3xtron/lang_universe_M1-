import { expect, test, type Page } from "@playwright/test";

const THREAD = "bottom-lock-thread";
const EMPTY = "bottom-lock-empty";

function history(threadId: string, count = 40) {
  return [{
    values: { messages: Array.from({ length: count }, (_, index) => ({
      id: `${threadId}-${index}`,
      type: index % 2 === 0 ? "human" : "ai",
      content: `${threadId} historical message ${index} `.repeat(10),
    })) },
    next: [], tasks: [], metadata: {}, created_at: "2026-07-30T00:00:00Z",
    checkpoint: { thread_id: threadId, checkpoint_ns: "", checkpoint_id: `${threadId}-checkpoint` },
    parent_checkpoint: null,
  }];
}

async function installRoutes(page: Page) {
  await page.route("**/threads/search", (route) => route.fulfill({ contentType: "application/json", body: "[]" }));
  await page.route("**/info", (route) => route.fulfill({ contentType: "application/json", body: "{}" }));
  await page.route("**/runtime-identity", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ runtime_id: "backend-postgres-v1", durable: true, persistence: "postgres" }) }));
  await page.route("**/api/models", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ default: "mock/model", models: [] }) }));
  await page.route("**/api/tts/voices", (route) => route.fulfill({ contentType: "application/json", body: '{"voices":[]}' }));
  await page.route("**/threads", (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify({ thread_id: THREAD, values: {}, status: "idle" }) }));
  await page.route(`**/threads/${THREAD}/history`, (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(history(THREAD)) }));
  await page.route(`**/threads/${EMPTY}/history`, (route) => route.fulfill({ contentType: "application/json", body: JSON.stringify(history(EMPTY, 0)) }));
}

async function distanceFromBottom(page: Page) {
  return page.locator("[data-conversation-viewport]").evaluate((element) => {
    const node = element as HTMLElement;
    return node.scrollHeight - node.clientHeight - node.scrollTop;
  });
}

test.describe("bottom-locked conversation scrolling", () => {
  test("reopens non-empty history at the latest content", async ({ page }) => {
    await installRoutes(page);
    await page.goto(`/?threadId=${THREAD}&apiUrl=http%3A%2F%2Fmock&assistantId=agent`);
    await expect(page.getByText(`${THREAD} historical message 39`, { exact: false })).toBeVisible();
    await expect.poll(() => distanceFromBottom(page)).toBeLessThan(4);
  });

  test("human scroll-away cancels following instead of reclaiming the viewport", async ({ page }) => {
    await installRoutes(page);
    await page.goto(`/?threadId=${THREAD}&apiUrl=http%3A%2F%2Fmock&assistantId=agent`);
    const viewport = page.locator("[data-conversation-viewport]");
    await expect(viewport).toBeVisible();
    await viewport.hover();
    await page.mouse.wheel(0, -600);
    const detachedTop = await viewport.evaluate((element) => (element as HTMLElement).scrollTop);
    await page.waitForTimeout(1000);
    expect(await viewport.evaluate((element) => (element as HTMLElement).scrollTop)).toBe(detachedTop);
  });

  test("empty/history-error sessions do not invent placement, including reduced motion", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await installRoutes(page);
    await page.goto(`/?threadId=${EMPTY}&apiUrl=http%3A%2F%2Fmock&assistantId=agent`);
    const viewport = page.locator("[data-conversation-viewport]");
    await expect(viewport).toBeVisible();
    await expect(viewport).toHaveJSProperty("scrollTop", 0);
  });
});
