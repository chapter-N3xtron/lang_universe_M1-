import { test, expect } from "@playwright/test";

test.describe("UI controls render and respond", () => {
  test.beforeEach(async ({ page }) => {
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

    await expect(trigger).toHaveText("Auto");

    await trigger.click();
    const dropdown = page.locator('[data-slot="select-content"]');
    await expect(dropdown).toBeVisible();

    await expect(dropdown.getByText("Jasper")).toBeVisible();
    await expect(dropdown.getByText("Deep Agent")).toBeVisible();
    await expect(dropdown.getByText("Research")).toBeVisible();
    await expect(dropdown.getByText("Magic Coder")).toBeVisible();

    await dropdown.getByText("Jasper").click();
    await expect(trigger).toHaveText("Jasper");
  });

  test("model dropdown renders with options", async ({ page }) => {
    await page.goto("/");

    const trigger = page.locator('button[aria-label="Select model"]');
    await expect(trigger).toBeVisible({ timeout: 10000 });

    await expect(trigger).toHaveText("ollama-cloud/qwen3.5:397b");

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
    await expect(trigger).toContainText("ollama-cloud/qwen3.5:397b");
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

  test("Upload PDF or Image label is visible", async ({ page }) => {
    await page.goto("/");

    const uploadLabel = page.getByText("Upload PDF or Image");
    await expect(uploadLabel).toBeVisible({ timeout: 10000 });
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
          voices: ["alba", "pavo", "tango", "whispering"],
          total: 4,
        }),
      });
    });

    await page.goto("/");

    const trigger = page.locator('button[aria-label="Select voice"]');
    await expect(trigger).toBeVisible({ timeout: 10000 });
    await expect(trigger).toHaveText("Auto");

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
