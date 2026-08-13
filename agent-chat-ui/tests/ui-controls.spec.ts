import { test, expect } from "@playwright/test";

test.describe("UI controls render and respond", () => {
  test.beforeEach(async ({ page }) => {
    await page.route(
      "**/session-catalog/preferences/model**",
      async (route) => {
        if (route.request().method() === "PUT") {
          const body = route.request().postDataJSON();
          await route.fulfill({
            contentType: "application/json",
            body: JSON.stringify({ model_id: body.model_id }),
          });
          return;
        }
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({ model_id: null }),
        });
      },
    );
    // LangGraph SDK polls threads on mount; mock it so the Suspense layout resolves.
    await page.route("**/threads/search", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify([]),
      });
    });
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
            {
              id: "ollama-cloud/kimi-k3",
              name: "kimi-k3",
              provider: "ollama-cloud",
            },
            {
              id: "ollama-cloud/glm-5.2",
              name: "glm-5.2",
              provider: "ollama-cloud",
            },
            {
              id: "ollama-cloud/kimi-k2.5",
              name: "kimi-k2.5",
              provider: "ollama-cloud",
            },
            {
              id: "ollama-cloud/kimi-k2.6",
              name: "kimi-k2.6",
              provider: "ollama-cloud",
            },
            {
              id: "ollama/dolphin-llama3:8b",
              name: "dolphin-llama3:8b",
              provider: "ollama",
            },
            {
              id: "ollama/mistral-small:22b",
              name: "mistral-small:22b",
              provider: "ollama",
            },
            {
              id: "ollama/gemma4:latest",
              name: "gemma4:latest",
              provider: "ollama",
            },
            {
              id: "ollama/qwen3.5:27b",
              name: "qwen3.5:27b",
              provider: "ollama",
            },
          ],
        }),
      });
    });
  });

  test("agent dropdown renders with options", async ({ page }) => {
    await page.goto("/");

    const trigger = page.locator('button[aria-label="Select agent"]');
    await expect(trigger).toBeVisible({ timeout: 10000 });

    await expect(trigger).toHaveText("Jasper");

    await trigger.click();
    const dropdown = page.locator('[data-slot="select-content"]');
    await expect(dropdown).toBeVisible();

    await expect(dropdown.getByText("Jasper")).toBeVisible();
    await expect(dropdown.getByText("Deep Agent")).toBeVisible();
    await expect(dropdown.getByText("Research", { exact: true })).toHaveCount(
      0,
    );
    await expect(dropdown.getByText("The Librarian")).toBeVisible();
    await expect(dropdown.getByText("Magic Coder")).toBeVisible();

    await dropdown.getByText("The Librarian").click();
    await expect(trigger).toHaveText("The Librarian");
  });

  test("model dropdown renders with options", async ({ page }) => {
    await page.goto("/");

    const trigger = page.locator('button[aria-label="Select model"]');
    await expect(trigger).toBeVisible({ timeout: 10000 });

    await expect(trigger).toHaveText("Cloud · ollama-cloud/qwen3.5:397b");

    await trigger.click();
    const dropdown = page.locator('[data-slot="select-content"]');
    await expect(dropdown).toBeVisible();

    await expect(dropdown.getByText("Auto", { exact: true })).toHaveCount(0);
    await expect(dropdown.getByText("Local", { exact: true })).toBeVisible();
    await expect(dropdown.getByText("Cloud", { exact: true })).toBeVisible();
    await expect(dropdown.getByText("ollama-cloud/qwen3.5:397b")).toBeVisible();
    await expect(dropdown.getByText("dolphin-llama3:8b")).toBeVisible();

    const groups = dropdown.locator('[data-slot="select-label"]');
    await expect(groups).toHaveText(["Local", "Cloud"]);

    const cloudItems = dropdown
      .locator('[data-slot="select-label"]', { hasText: "Cloud" })
      .locator("..")
      .locator('[data-slot="select-item"]');
    await expect(cloudItems).toHaveText([
      "glm-5.2",
      "kimi-k2.5",
      "kimi-k2.6",
      "kimi-k3",
      "ollama-cloud/qwen3.5:397b",
    ]);

    await dropdown.getByText("ollama-cloud/qwen3.5:397b").click();
    await expect(trigger).toHaveText("Cloud · ollama-cloud/qwen3.5:397b");
  });

  test("coding access defaults to full repository access with review", async ({
    page,
  }) => {
    await page.goto("/");

    const trigger = page.locator('button[aria-label="Select coding access"]');
    await expect(trigger).toBeVisible({ timeout: 10000 });
    await expect(trigger).toHaveText("Full repo (review)");

    await trigger.click();
    const dropdown = page.locator('[data-slot="select-content"]');
    await dropdown.getByText("Read only").click();
    await expect(trigger).toHaveText("Read only");
  });

  test("selected cloud model is sent in the run payload", async ({ page }) => {
    await page.route("**/threads", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue();
        return;
      }
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          thread_id: "cloud-model-thread",
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          metadata: {},
          status: "idle",
        }),
      });
    });
    await page.route("**/threads/*/runs/stream", (route) =>
      route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: "",
      }),
    );

    await page.goto("/");
    const modelTrigger = page.locator('button[aria-label="Select model"]');
    await modelTrigger.click();
    await page
      .locator('[data-slot="select-content"]')
      .getByText("glm-5.2", { exact: true })
      .click();
    await expect(modelTrigger).toHaveText("Cloud · glm-5.2");

    const runRequest = page.waitForRequest(
      (request) =>
        request.method() === "POST" && request.url().includes("/runs/stream"),
    );
    await page.locator("textarea").fill("Use the selected cloud model");
    await page.locator("textarea").press("Enter");

    const body = (await runRequest).postDataJSON();
    expect(body.input.model).toBe("ollama-cloud/glm-5.2");
    expect(body.stream_subgraphs).toBe(false);
    expect(body.on_disconnect).toBe("cancel");
    expect(body.input.messages).toHaveLength(1);
    expect(body.input.messages[0].type).toBe("human");
  });

  test("chained approvals submit only the current interrupt decisions", async ({
    page,
  }) => {
    const runBodies: Record<string, any>[] = [];
    const actions = (count: number) =>
      Array.from({ length: count }, (_, index) => ({
        name: "run_workspace_command",
        args: { argv: ["git", "status", `--short-${index + 1}`] },
        description: `Inspect workspace ${index + 1}`,
      }));
    const interrupt = (id: string, count: number) => ({
      id,
      value: {
        action_requests: actions(count),
        review_configs: Array.from({ length: count }, () => ({
          action_name: "run_workspace_command",
          allowed_decisions: ["approve", "edit", "reject"],
        })),
      },
    });
    const sse = (runId: string, currentInterrupt?: Record<string, unknown>) =>
      [
        "event: metadata",
        `data: ${JSON.stringify({ run_id: runId, thread_id: "approval-thread" })}`,
        "",
        "event: values",
        `data: ${JSON.stringify({ messages: [], __interrupt__: currentInterrupt ? [currentInterrupt] : [] })}`,
        "",
        "event: end",
        "data: {}",
        "",
      ].join("\n");

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
    await page.route("**/threads", (route) =>
      route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          thread_id: "approval-thread",
          created_at: "2026-08-05T00:00:00Z",
          updated_at: "2026-08-05T00:00:00Z",
          metadata: {},
          status: "idle",
        }),
      }),
    );
    await page.route("**/threads/*/runs/stream", async (route) => {
      runBodies.push(route.request().postDataJSON());
      const requestIndex = runBodies.length - 1;
      const body =
        requestIndex === 0
          ? sse("initial-run", interrupt("interrupt-four", 4))
          : requestIndex === 1
            ? sse("first-resume", interrupt("interrupt-one", 1))
            : sse("second-resume");
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body,
      });
    });

    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/");
    await page.locator("textarea").fill("Use Coder for approval testing");
    await page.locator("textarea").press("Enter");

    const approveAll = page.getByRole("button", { name: "Approve All" });
    await expect(approveAll).toBeVisible();
    await expect(page.getByText("(1/4)", { exact: false })).toBeVisible();
    await approveAll.dblclick();

    await expect(page.getByText("(1/4)", { exact: false })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Approve" })).toBeVisible();
    expect(runBodies).toHaveLength(2);
    expect(runBodies[1].command.resume.decisions).toEqual([
      { type: "approve" },
      { type: "approve" },
      { type: "approve" },
      { type: "approve" },
    ]);

    await page.evaluate(() => document.documentElement.classList.add("dark"));
    const card = page.locator("[data-agent-inbox-card]");
    const desktopBox = await card.boundingBox();
    expect(desktopBox?.width).toBeLessThanOrEqual(768);
    const colors = await card.evaluate((element) => {
      const style = getComputedStyle(element);
      return { color: style.color, backgroundColor: style.backgroundColor };
    });
    expect(colors.color).not.toBe(colors.backgroundColor);

    await page.setViewportSize({ width: 390, height: 844 });
    const narrowBox = await card.boundingBox();
    expect(narrowBox?.width).toBeLessThanOrEqual(390);

    await page.getByRole("button", { name: "Approve" }).click();
    await expect.poll(() => runBodies.length).toBe(3);
    expect(runBodies[2].command.resume.decisions).toEqual([
      { type: "approve" },
    ]);
  });

  test("does not synthesize a tool result after an incomplete tool call", async ({
    page,
  }) => {
    const runBodies: Record<string, unknown>[] = [];
    await page.route("**/threads", (route) =>
      route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          thread_id: "stop-regression-thread",
          created_at: "2026-08-03T00:00:00Z",
          updated_at: "2026-08-03T00:00:00Z",
          metadata: {},
          status: "idle",
        }),
      }),
    );
    await page.route("**/threads/*/runs/stream", async (route) => {
      runBodies.push(route.request().postDataJSON());
      const firstRun = runBodies.length === 1;
      const body = firstRun
        ? [
            "event: metadata",
            `data: ${JSON.stringify({ run_id: "incomplete-run", thread_id: "stop-regression-thread" })}`,
            "",
            "event: messages",
            `data: ${JSON.stringify([
              {
                id: "incomplete-ai",
                type: "ai",
                content: "",
                tool_calls: [
                  {
                    id: "incomplete-task",
                    name: "task",
                    args: { subagent_type: "research", description: "test" },
                    type: "tool_call",
                  },
                ],
              },
              { langgraph_node: "jasper" },
            ])}`,
            "",
            "event: end",
            "data: {}",
            "",
          ].join("\n")
        : "event: end\ndata: {}\n\n";
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body,
      });
    });

    await page.goto("/");
    const textarea = page.locator("textarea");
    await textarea.fill("Start a tool call");
    await textarea.press("Enter");
    await expect.poll(() => runBodies.length).toBe(1);
    await textarea.fill("Short follow-up");
    await textarea.press("Enter");
    await expect.poll(() => runBodies.length).toBe(2);

    const secondInput = runBodies[1].input as {
      messages: Array<{
        type: string;
        content: Array<{ type: string; text: string }>;
      }>;
    };
    expect(secondInput.messages).toHaveLength(1);
    expect(secondInput.messages[0]).toEqual(
      expect.objectContaining({
        type: "human",
        content: [
          expect.objectContaining({ type: "text", text: "Short follow-up" }),
        ],
      }),
    );
  });

  test("repo selector opens and displays the selected folder", async ({
    page,
  }) => {
    await page.route(
      "http://127.0.0.1:8000/api/fs/pick-folder",
      async (route) => {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            path: "/Volumes/Storage/example-repo",
            cancelled: false,
          }),
        });
      },
    );
    await page.goto("/");

    const button = page.getByRole("button", {
      name: "Select repository folder",
    });
    await expect(button).toBeVisible({ timeout: 10000 });
    await button.click();
    await expect(button).toContainText("example-repo");
  });

  test("Hide Tool Calls switch toggles", async ({ page }) => {
    await page.goto("/");

    const switchBtn = page.locator('button[role="switch"]');
    await expect(switchBtn).toBeVisible({ timeout: 10000 });

    const initialChecked = await switchBtn.getAttribute("aria-checked");
    await switchBtn.click();
    await expect(switchBtn).toHaveAttribute(
      "aria-checked",
      initialChecked === "true" ? "false" : "true",
    );
  });

  test("file attachment label is visible", async ({ page }) => {
    await page.goto("/");

    const uploadLabel = page.getByText("Upload file");
    await expect(uploadLabel).toBeVisible({ timeout: 10000 });
  });

  test("accepts an extension-identified EPUB without exposing a local path", async ({
    page,
  }) => {
    await page.route(
      "http://127.0.0.1:8000/api/attachments/document",
      async (route) => {
        expect(route.request().postData()).not.toContain("/Users/");
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({
            filename: "selected.epub",
            format: "epub",
            text: "## Chapter 1 [chapter.xhtml]\n\nSelected content",
            segments: [{ id: "publication", characters: 16 }],
            truncated: false,
          }),
        });
      },
    );
    await page.goto("/");

    await page.locator("#file-input").setInputFiles({
      name: "selected.epub",
      mimeType: "application/octet-stream",
      buffer: Buffer.from("selected publication bytes"),
    });

    await expect(
      page.getByText("selected.epub", { exact: true }),
    ).toBeVisible();
    await expect(page.getByText("EPUB · extracted safely")).toBeVisible();
  });

  test("Voice and Send buttons visible", async ({ page }) => {
    await page.goto("/");

    const voiceBtn = page.locator('button[title*="Hold to record"]');
    await expect(voiceBtn).toBeVisible({ timeout: 10000 });

    const sendBtn = page.getByText("Send");
    await expect(sendBtn).toBeVisible();
    await expect(sendBtn).toBeDisabled();
  });

  test("voice selector renders with options", async ({ page }) => {
    await page.route("http://127.0.0.1:8000/api/tts/voices", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          voices: ["eve", "alba", "pavo", "tango", "whispering"],
          total: 5,
        }),
      });
    });

    await page.goto("/");

    const trigger = page.locator('button[aria-label="Select voice"]');
    await expect(trigger).toBeVisible({ timeout: 10000 });
    await expect(trigger).toHaveText("Eve");

    await trigger.click();
    const dropdown = page.locator('[data-slot="select-content"]');
    await expect(dropdown).toBeVisible();

    await expect(dropdown.getByText("Alba")).toBeVisible();
    await expect(dropdown.getByText("Pavo")).toBeVisible();
    await expect(dropdown.getByText("Tango")).toBeVisible();
    await expect(dropdown.getByText("Whispering")).toBeVisible();

    await dropdown.getByText("Alba").click();
    await expect(trigger).toHaveText("Alba");
  });

  test("textarea accepts input and enables Send", async ({ page }) => {
    await page.goto("/");

    const textarea = page.locator("textarea");
    await expect(textarea).toBeVisible({ timeout: 10000 });

    const sendBtn = page.getByText("Send");
    await expect(sendBtn).toBeDisabled();

    await textarea.fill("test message");
    await expect(sendBtn).toBeEnabled();
  });
});
