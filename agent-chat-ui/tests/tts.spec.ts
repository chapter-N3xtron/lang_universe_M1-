import { test, expect } from "@playwright/test";

/**
 * TTS play/stop state test.
 *
 * This exercises the Volume2 button on AI messages, asserting that:
 *   1. Clicking it switches the icon to a stop square.
 *   2. Clicking again reverts to Volume2.
 *
 * The backend TTS endpoint is mocked so we don't need the real sidecar running.
 */

test.describe("TTS play/stop button", () => {
  let spokenText: string | undefined;

  test.beforeEach(async ({ page }) => {
    spokenText = undefined;
    await page.route("http://127.0.0.1:8123/info", (route) =>
      route.fulfill({ contentType: "application/json", body: "{}" }),
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
    // LangGraph SDK polls threads on mount; mock it so the Suspense layout resolves.
    await page.route("**/threads/search", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });

    // Provide a valid voice list so the voice selector loads.
    await page.route("http://127.0.0.1:8000/api/tts/voices", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          voices: ["alba"],
          total: 1,
        }),
      });
    });

    // Provide a valid model list.
    await page.route("http://127.0.0.1:8000/api/models", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          default: "ollama-cloud/qwen3.5:397b",
          models: [
            {
              id: "ollama-cloud/qwen3.5:397b",
              name: "ollama-cloud/qwen3.5:397b",
              provider: "ollama-cloud",
            },
          ],
        }),
      });
    });

    // Mock the streaming TTS endpoint with one silence chunk.
    await page.route("http://127.0.0.1:8000/api/tts/stream", async (route) => {
      spokenText = route.request().postDataJSON().text;
      // 24000 samples of silence as Float32 little-endian PCM.
      const silence = new Float32Array(24000).fill(0);
      const bytes = new Uint8Array(silence.buffer);
      const b64 = Buffer.from(bytes).toString("base64");
      const sse = `data: ${JSON.stringify({ audio: b64, shape: [24000], dtype: "float32" })}\n\n`;
      await route.fulfill({
        contentType: "text/event-stream",
        headers: {
          "Cache-Control": "no-cache",
          "X-Accel-Buffering": "no",
        },
        body: sse,
      });
    });
  });

  test("toggles between Volume2 and stop icon", async ({ page }) => {
    await page.goto("/");

    const textarea = page.locator("textarea");
    await expect(textarea).toBeVisible({ timeout: 10000 });

    await textarea.fill("Hello");

    // Mock the LangGraph stream with a single assistant message.
    // The SDK posts to /threads/{thread_id}/runs
    // with streamMode=["values"]; a minimal event-stream response is enough to produce
    // an AI message in the thread.
    // Mock the LangGraph server endpoints so the test doesn't need a real graph.
    await page.route("http://127.0.0.1:8123/threads", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          thread_id: "thread-1",
          created_at: "2026-07-30T00:00:00Z",
          updated_at: "2026-07-30T00:00:00Z",
          metadata: {},
          status: "idle",
          values: {},
        }),
      });
    });
    await page.route(
      "http://127.0.0.1:8123/threads/*/runs/stream",
      async (route) => {
        const sseBody = [
          "event: metadata",
          `data: ${JSON.stringify({ run_id: "run-1", thread_id: "thread-1" })}`,
          "",
          "event: messages",
          `data: ${JSON.stringify([
            {
              id: "msg-ai-1",
              type: "ai",
              content: [{ type: "text", text: "Hello back to you." }],
              additional_kwargs: {
                jasper_confidence_score: 0.82,
                jasper_confidence_basis: "Grounded in the supplied documentation.",
              },
            },
            { langgraph_node: "jasper" },
          ])}`,
          "",
          "event: end",
          "data: {}",
          "",
        ].join("\n");
        await route.fulfill({
          contentType: "text/event-stream",
          status: 200,
          body: sseBody,
        });
      },
    );
    await page.route(
      "http://127.0.0.1:8123/threads/*/history",
      async (route) => {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify([
            {
              values: {
                messages: [
                  {
                    id: "msg-ai-1",
                    type: "ai",
                    content: [{ type: "text", text: "Hello back to you." }],
                    additional_kwargs: {
                      jasper_confidence_score: 0.82,
                      jasper_confidence_basis:
                        "Grounded in the supplied documentation.",
                    },
                  },
                ],
              },
              next: [],
              tasks: [],
              metadata: {},
              created_at: "2026-07-30T00:00:00Z",
              checkpoint: {
                thread_id: "thread-1",
                checkpoint_ns: "",
                checkpoint_id: "tts-checkpoint",
              },
              parent_checkpoint: null,
            },
          ]),
        });
      },
    );

    const sendBtn = page.getByText("Send");
    await expect(sendBtn).toBeEnabled();

    // Capture console errors; AudioContext issues would surface here.
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        consoleErrors.push(msg.text());
      }
    });

    await sendBtn.click();

    // Wait for the assistant message to render.
    const aiMessage = page.locator("text=Hello back to you.").first();
    await expect(aiMessage).toBeVisible({ timeout: 15000 });
    await expect(page.locator("[data-jasper-confidence]")).toContainText(
      "Confidence 0.82 — model estimate, not empirically calibrated",
    );

    // Locate the speak button within the AI message row.
    // It is a TooltipIconButton rendered by CommandBar inside AssistantMessage.
    const speakBtn = page.getByRole("button", { name: "Read aloud" });
    await expect(speakBtn).toBeVisible();

    // Click to speak.
    await speakBtn.click();
    await expect.poll(() => spokenText).toBe("Hello back to you.");

    // The icon should switch to a stop square.
    const stopBtn = page.getByRole("button", { name: "Stop playback" });
    await expect(stopBtn).toBeVisible({ timeout: 5000 });

    // Click stop.
    await stopBtn.click();

    // The icon should revert to Volume2.
    await expect(speakBtn).toBeVisible({ timeout: 5000 });

    // Ensure no AudioContext/InvalidStateError leaked.
    expect(
      consoleErrors.filter(
        (e) =>
          e.toLowerCase().includes("audiocontext") ||
          e.toLowerCase().includes("invalidstate") ||
          e.toLowerCase().includes("cannot close"),
      ),
    ).toHaveLength(0);
  });
});
