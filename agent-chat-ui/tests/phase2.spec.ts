import { test, expect } from "@playwright/test";

test("basic chat smoke test", async ({ page }) => {
  await page.goto("/");

  const textarea = page.locator("textarea");
  await expect(textarea).toBeVisible({ timeout: 10000 });

  await textarea.fill("Hello, who are you?");
  await textarea.press("Enter");

  const markdownContent = page.locator(".markdown-text, [class*='markdown']").first();
  await expect(markdownContent).toBeVisible({ timeout: 30000 });

  const content = await markdownContent.textContent();
  expect(content?.length).toBeGreaterThan(0);
});

test("thread persistence", async ({ page }) => {
  await page.goto("/");

  const textarea = page.locator("textarea");
  await expect(textarea).toBeVisible({ timeout: 10000 });

  await textarea.fill("Remember this: the secret code is 42");
  await textarea.press("Enter");

  const markdownContent = page.locator(".markdown-text, [class*='markdown']").first();
  await expect(markdownContent).toBeVisible({ timeout: 30000 });

  const url = page.url();
  expect(url).toContain("threadId");

  await page.reload();
  await expect(textarea).toBeVisible({ timeout: 10000 });

  await page.waitForTimeout(3000);

  const messagesAfterReload = page.locator(".markdown-text, [class*='markdown']");
  const count = await messagesAfterReload.count();
  expect(count).toBeGreaterThanOrEqual(1);
});
