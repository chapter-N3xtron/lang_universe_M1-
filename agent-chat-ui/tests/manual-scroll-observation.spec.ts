import { expect, test, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";

const THREAD_ID = "manual-scroll-capture-thread";

function historyState() {
  return {
    values: {
      messages: [
        {
          id: `${THREAD_ID}-human`,
          type: "human",
          content: "Safe visible message. bearer should-not-leak",
        },
        {
          id: `${THREAD_ID}-ai`,
          type: "ai",
          content: "Rendered assistant response for capture testing. ".repeat(
            30,
          ),
        },
      ],
    },
    next: [],
    tasks: [],
    metadata: {},
    created_at: "2026-08-11T00:00:00Z",
    checkpoint: {
      thread_id: THREAD_ID,
      checkpoint_ns: "",
      checkpoint_id: `${THREAD_ID}-checkpoint`,
    },
    parent_checkpoint: null,
  };
}

async function installRoutes(page: Page) {
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
  await page.route(`**/threads/${THREAD_ID}/history`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([historyState()]),
    }),
  );
}

test("visible capture control downloads one observation bundle", async ({
  page,
}) => {
  await installRoutes(page);
  let confirmationSeen = false;
  page.on("dialog", async (dialog) => {
    confirmationSeen =
      dialog.type() === "confirm" &&
      dialog.message().includes("rendered message content");
    await dialog.accept();
  });

  await page.goto(`/?threadId=${THREAD_ID}`);
  await expect(
    page.locator(`[data-message-id="${THREAD_ID}-ai"]`),
  ).toBeVisible();
  expect(await page.evaluate(() => "manualScrollObservation" in window)).toBe(
    false,
  );

  await page.getByRole("button", { name: "Start JSON Capture" }).click();
  expect(confirmationSeen).toBe(true);
  const activeStatus = page
    .getByRole("status")
    .filter({ hasText: "Capturing JSON" });
  await expect(activeStatus).toContainText("Capturing JSON · 00:00");
  await expect
    .poll(() => activeStatus.textContent(), { timeout: 2500 })
    .toContain("00:01");

  await page.locator("[data-conversation-viewport]").evaluate((viewport) => {
    viewport.scrollTo({ top: 40, behavior: "instant" });
    viewport.dispatchEvent(new Event("scroll"));
    viewport.setAttribute("data-capture-smoke", "active");
    viewport.removeAttribute("data-capture-smoke");
  });

  const downloads: import("@playwright/test").Download[] = [];
  page.on("download", (download) => downloads.push(download));
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Stop Capture" }).click();
  const download = await downloadPromise;
  await page.waitForTimeout(200);

  expect(downloads).toHaveLength(1);
  expect(download.suggestedFilename()).toMatch(/^scroll-observation-.*\.json$/);
  const bundle = JSON.parse(await readFile((await download.path())!, "utf8"));
  expect(bundle.schema).toBe("manual-scroll-observation/v1");
  expect(bundle.manifest.lifecycle).toBe("stopped");
  expect(bundle.manifest.event_count).toBe(bundle.events.length);
  expect(bundle.manifest.artifacts.manifest).toBeUndefined();

  const types = new Set(
    bundle.events.map((event: { type: string }) => event.type),
  );
  for (const type of [
    "session.start",
    "session.stop",
    "ui.snapshot",
    "user.scroll",
    "programmatic.scroll",
    "dom.mutation",
  ]) {
    expect(types.has(type)).toBe(true);
  }

  const snapshot = bundle.events.find(
    (event: { type: string }) => event.type === "ui.snapshot",
  );
  expect(snapshot.payload.observation.viewport.width).toBeGreaterThan(0);
  expect(snapshot.payload.observation.message_snapshots).toHaveLength(2);
  expect(
    snapshot.payload.observation.message_snapshots.every(
      (message: { thread_id: string }) => message.thread_id === THREAD_ID,
    ),
  ).toBe(true);
  expect(JSON.stringify(bundle)).not.toContain("should-not-leak");

  await expect(
    page.getByRole("button", { name: "Start JSON Capture" }),
  ).toBeVisible();
  await expect(page.getByText(/^Downloaded scroll-observation-/)).toBeVisible();
});
