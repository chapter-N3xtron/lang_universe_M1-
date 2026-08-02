import { expect, test } from "@playwright/test";

test("refuses an unverified development runtime before creating a stream", async ({
  page,
}) => {
  let threadRequestObserved = false;
  await page.route("**/info", (route) =>
    route.fulfill({ contentType: "application/json", body: "{}" }),
  );
  await page.route("**/runtime-identity", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        runtime_id: "unverified",
        durable: false,
        persistence: "unverified",
      }),
    }),
  );
  await page.route("**/threads/**", (route) => {
    threadRequestObserved = true;
    return route.abort();
  });

  await page.goto("/");

  await expect(page.getByText("Session storage unavailable")).toBeVisible();
  await expect(
    page.getByText(/not the canonical PostgreSQL-backed Agent Server/),
  ).toBeVisible();
  expect(threadRequestObserved).toBe(false);
});
