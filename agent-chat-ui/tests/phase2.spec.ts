import { test, expect } from "@playwright/test";

/**
 * Phase 2 end-to-end tests against the real LangGraph server (port 8123).
 *
 * Both tests select the Jasper agent before sending. Per HANDOFF Phase 3,
 * setting `target_agent` bypasses the supervisor's approval interrupt so the
 * first turn produces an assistant reply (which is what these assertions wait
 * for). Without this, turn 1 surfaces an Agent-Inbox "Approve/Reject" card and
 * no assistant markdown appears, causing a false timeout.
 */
async function selectJasper(page: import("@playwright/test").Page) {
  const trigger = page.locator('button[aria-label="Select agent"]');
  await expect(trigger).toBeVisible({ timeout: 10000 });
  await trigger.click();
  const dropdown = page.locator('[data-slot="select-content"]');
  await expect(dropdown).toBeVisible();
  await dropdown.getByText("Jasper").click();
  await expect(trigger).toHaveText("Jasper");
}

test("basic chat smoke test", async ({ page }) => {
  await page.goto("/");

  const textarea = page.locator("textarea");
  await expect(textarea).toBeVisible({ timeout: 10000 });

  await selectJasper(page);

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

  await selectJasper(page);

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