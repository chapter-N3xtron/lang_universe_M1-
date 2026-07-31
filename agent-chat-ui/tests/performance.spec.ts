import { expect, test } from "@playwright/test";

const THREAD_ID = "performance-thread";
const messageCount = 300;

const messages = Array.from({ length: messageCount }, (_, index) => ({
  id: `perf-message-${index}`,
  type: index % 2 === 0 ? "human" : "ai",
  content: `Performance message ${index}`,
}));

const state = {
  values: { messages, coding_status: "completed" },
  next: [],
  tasks: [],
  metadata: {},
  created_at: "2026-07-30T00:00:00Z",
  checkpoint: {
    thread_id: THREAD_ID,
    checkpoint_ns: "",
    checkpoint_id: "performance-checkpoint",
  },
  parent_checkpoint: null,
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    (window as typeof window & { __longTasks?: number[] }).__longTasks = [];
    (
      window as typeof window & {
        __messageRenders?: Record<string, number>;
      }
    ).__messageRenders = {};
    (
      window as typeof window & { __messageListRenders?: number }
    ).__messageListRenders = 0;
    const frameTarget = window as typeof window & { __frameDeltas?: number[] };
    frameTarget.__frameDeltas = [];
    let previousFrame = performance.now();
    const observeFrame = (now: number) => {
      frameTarget.__frameDeltas?.push(now - previousFrame);
      if ((frameTarget.__frameDeltas?.length ?? 0) > 600) {
        frameTarget.__frameDeltas?.shift();
      }
      previousFrame = now;
      requestAnimationFrame(observeFrame);
    };
    requestAnimationFrame(observeFrame);
    if ("PerformanceObserver" in window) {
      new PerformanceObserver((list) => {
        const target = window as typeof window & { __longTasks?: number[] };
        target.__longTasks?.push(
          ...list.getEntries().map((entry) => entry.duration),
        );
      }).observe({ type: "longtask", buffered: true });
    }
  });
  await page.route("**/threads/search", (route) =>
    route.fulfill({ contentType: "application/json", body: "[]" }),
  );
  await page.route(`**/threads/${THREAD_ID}/history`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([state]),
    }),
  );
  await page.route("**/info", (route) =>
    route.fulfill({ contentType: "application/json", body: "{}" }),
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
});

test("long threads stay windowed and within initial render budgets", async ({
  page,
}) => {
  const started = Date.now();
  await page.goto(`/?threadId=${THREAD_ID}`);
  await expect(page.getByText("Performance message 299")).toBeVisible();
  const readyMs = Date.now() - started;

  await expect(page.getByText("Performance message 0")).toHaveCount(0);
  const showEarlier = page.getByRole("button", {
    name: /Show 80 earlier messages/,
  });
  await expect(showEarlier).toBeVisible();

  const initialRows = await page
    .locator("[data-message-id^='perf-message-']")
    .count();
  const metrics = await page.evaluate(() => {
    const longTasks =
      (window as typeof window & { __longTasks?: number[] }).__longTasks ?? [];
    return {
      domNodes: document.getElementsByTagName("*").length,
      longTaskCount: longTasks.length,
      maxLongTaskMs: Math.max(0, ...longTasks),
      heapBytes:
        (performance as Performance & { memory?: { usedJSHeapSize: number } })
          .memory?.usedJSHeapSize ?? 0,
      messageListRenders:
        (window as typeof window & { __messageListRenders?: number })
          .__messageListRenders ?? 0,
    };
  });
  console.log("UI_PERF_BASELINE", JSON.stringify({ readyMs, ...metrics }));

  expect(initialRows).toBeLessThanOrEqual(80);
  expect(readyMs).toBeLessThan(2_500);
  expect(metrics.domNodes).toBeLessThan(5_000);
  expect(metrics.maxLongTaskMs).toBeLessThan(250);
  if (metrics.heapBytes > 0) {
    expect(metrics.heapBytes).toBeLessThan(150 * 1024 * 1024);
  }

  await showEarlier.click();
  await expect(page.getByText("Performance message 140")).toBeVisible();
});

test("a maximum-size coding event stream remains responsive", async ({
  page,
}) => {
  await page.route("**/threads/*/runs/stream", (route) => {
    const events: string[] = [
      "event: metadata",
      `data: ${JSON.stringify({ run_id: "perf-run", thread_id: "stream-performance-thread" })}`,
      "",
    ];
    const customEvents = [
      {
        type: "coding_event",
        version: 1,
        session_id: "opaque-performance-session",
        sequence: 0,
        kind: "status",
        status: "running",
        data: {},
      },
      ...Array.from({ length: 32 }, (_, index) => ({
        type: "coding_event",
        version: 1,
        session_id: "opaque-performance-session",
        sequence: index + 1,
        kind: "text",
        status: "streaming",
        data: { content: "x".repeat(512), transient: true },
      })),
      ...Array.from({ length: 94 }, (_, index) => ({
        type: "coding_event",
        version: 1,
        session_id: "opaque-performance-session",
        sequence: index + 33,
        kind: "tool",
        status: "running",
        data: { name: "read_file", tool_call_id: `call-${index}` },
      })),
      {
        type: "coding_event",
        version: 1,
        session_id: "opaque-performance-session",
        sequence: 127,
        kind: "status",
        status: "completed",
        data: {},
      },
    ];
    for (const event of customEvents) {
      events.push("event: custom", `data: ${JSON.stringify(event)}`, "");
    }
    events.push(
      "event: messages",
      `data: ${JSON.stringify([
        { id: "perf-final", type: "ai", content: "Streaming finished" },
        { langgraph_node: "coding" },
      ])}`,
      "",
      "event: end",
      "data: {}",
      "",
    );
    return route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: events.join("\n"),
    });
  });
  await page.goto(`/?threadId=${THREAD_ID}`);
  await expect(page.getByText("Performance message 299")).toBeVisible();
  const renderCountsBefore = await page.evaluate(
    () =>
      ({
        ...(
          window as typeof window & {
            __messageRenders?: Record<string, number>;
          }
        ).__messageRenders,
      }) as Record<string, number>,
  );
  const input = page.locator("textarea");
  await input.fill("profile the repository");
  const started = Date.now();
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Streaming finished")).toBeVisible();
  await expect(page.getByText("Coding: completed")).toBeVisible();
  const elapsedMs = Date.now() - started;
  const browserMetrics = await page.evaluate(() => ({
    longTasks:
      (window as typeof window & { __longTasks?: number[] }).__longTasks ?? [],
    frameDeltas:
      (window as typeof window & { __frameDeltas?: number[] }).__frameDeltas ??
      [],
    messageRenders:
      (
        window as typeof window & {
          __messageRenders?: Record<string, number>;
        }
      ).__messageRenders ?? {},
  }));
  const longTasks = browserMetrics.longTasks;
  const historicalRerenders = ["perf-message-220", "perf-message-221"].map(
    (id) =>
      (browserMetrics.messageRenders[id] ?? 0) - (renderCountsBefore[id] ?? 0),
  );
  console.log(
    "UI_STREAM_BASELINE",
    JSON.stringify({
      elapsedMs,
      longTaskCount: longTasks.length,
      maxLongTaskMs: Math.max(0, ...longTasks),
      maxFrameMs: Math.max(0, ...browserMetrics.frameDeltas),
      historicalRerenders,
    }),
  );
  expect(elapsedMs).toBeLessThan(2_500);
  expect(Math.max(0, ...longTasks)).toBeLessThan(250);
  expect(Math.max(0, ...browserMetrics.frameDeltas)).toBeLessThan(200);
  // The SDK performs one final checkpoint reconciliation after the stream.
  // Historical rows must not repaint for each custom event.
  expect(historicalRerenders.every((count) => count <= 1)).toBe(true);
});
