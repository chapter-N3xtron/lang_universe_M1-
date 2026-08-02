import { expect, test } from "@playwright/test";

test("long TTS playback keeps the Web Audio queue bounded", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const originalCreateBufferSource =
      AudioContext.prototype.createBufferSource;
    Object.defineProperty(window, "__ttsSourcesCreated", {
      configurable: true,
      writable: true,
      value: 0,
    });
    AudioContext.prototype.createBufferSource = function () {
      Object.defineProperty(window, "__ttsSourcesCreated", {
        configurable: true,
        writable: true,
        value:
          Number(
            (window as typeof window & { __ttsSourcesCreated?: number })
              .__ttsSourcesCreated ?? 0,
          ) + 1,
      });
      return originalCreateBufferSource.call(this);
    };
  });

  await page.route("**/threads/search", (route) =>
    route.fulfill({ contentType: "application/json", body: "[]" }),
  );
  await page.route("http://127.0.0.1:8000/api/tts/voices", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ voices: ["alba"], total: 1 }),
    }),
  );
  await page.route("http://127.0.0.1:8000/api/models", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        default: "ollama/qwen3.5:27b",
        models: [
          {
            id: "ollama/qwen3.5:27b",
            name: "qwen3.5:27b",
            provider: "ollama",
          },
        ],
      }),
    }),
  );

  await page.route("http://127.0.0.1:8000/api/tts/stream", (route) => {
    const silence = new Float32Array(2400);
    const audio = Buffer.from(new Uint8Array(silence.buffer)).toString(
      "base64",
    );
    const events = Array.from(
      { length: 100 },
      (_, index) =>
        `data: ${JSON.stringify({
          audio,
          shape: [silence.length],
          dtype: "float32",
          last: index === 99,
        })}\n\n`,
    ).join("");
    return route.fulfill({
      contentType: "text/event-stream",
      headers: { "Cache-Control": "no-cache", "X-Accel-Buffering": "no" },
      body: events,
    });
  });

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
  await page.route("http://127.0.0.1:8123/threads", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        thread_id: "thread-long-tts",
        created_at: "2026-07-30T00:00:00Z",
        updated_at: "2026-07-30T00:00:00Z",
        metadata: {},
        status: "idle",
        values: {},
      }),
    }),
  );
  await page.route("http://127.0.0.1:8123/threads/*/runs/stream", (route) => {
    const body = [
      "event: metadata",
      `data: ${JSON.stringify({ run_id: "run-long-tts", thread_id: "thread-long-tts" })}`,
      "",
      "event: messages",
      `data: ${JSON.stringify([
        {
          id: "msg-long-tts",
          type: "ai",
          content: [{ type: "text", text: "A long response to read aloud." }],
        },
        { langgraph_node: "jasper" },
      ])}`,
      "",
      "event: end",
      "data: {}",
      "",
    ].join("\n");
    return route.fulfill({ contentType: "text/event-stream", body });
  });
  await page.route("http://127.0.0.1:8123/threads/*/history", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([
        {
          values: {
            messages: [
              {
                id: "msg-long-tts",
                type: "ai",
                content: [
                  { type: "text", text: "A long response to read aloud." },
                ],
              },
            ],
          },
          next: [],
          tasks: [],
          metadata: {},
          created_at: "2026-07-30T00:00:00Z",
          checkpoint: {
            thread_id: "thread-long-tts",
            checkpoint_ns: "",
            checkpoint_id: "long-tts-checkpoint",
          },
          parent_checkpoint: null,
        },
      ]),
    }),
  );

  await page.goto("/");
  const textarea = page.locator("textarea");
  await expect(textarea).toBeVisible({ timeout: 10_000 });
  await textarea.fill("Give me a long response");
  await page.getByText("Send").click();
  await expect(page.getByText("A long response to read aloud.")).toBeVisible({
    timeout: 15_000,
  });

  await page.getByRole("button", { name: "Read aloud" }).click();
  const stopButton = page.getByRole("button", { name: "Stop playback" });
  await expect(stopButton).toBeVisible();
  await page.waitForTimeout(500);

  const sourcesCreated = await page.evaluate(
    () =>
      (window as typeof window & { __ttsSourcesCreated?: number })
        .__ttsSourcesCreated ?? 0,
  );
  expect(sourcesCreated).toBeGreaterThan(0);
  expect(sourcesCreated).toBeLessThanOrEqual(10);

  await stopButton.click();
  await expect(page.getByRole("button", { name: "Read aloud" })).toBeVisible();
});
