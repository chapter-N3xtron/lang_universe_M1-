import { expect, Page, Route, test } from "@playwright/test";

const operationDigest = "a".repeat(64);
const planDigest = "b".repeat(64);

const plan = {
  request_id: "plane-temporal-up",
  project_directory: "local-deployment-sandbox",
  compose_files: ["compose.yaml"],
  operation: "up",
  services: ["plane", "temporal"],
  profiles: [],
};

function interrupt(args: Record<string, unknown> = plan) {
  return {
    id: "docker-interrupt-1",
    value: {
      action_requests: [
        {
          name: "request_docker_compose_operation",
          args,
          description: "Start the local Plane and Temporal sandbox",
        },
      ],
      review_configs: [
        {
          action_name: "request_docker_compose_operation",
          allowed_decisions: ["approve", "reject"],
        },
      ],
    },
  };
}

function sse(
  currentInterrupt?: Record<string, unknown>,
  executionMode: "approval" | "autonomous" = "approval",
) {
  return [
    "event: metadata",
    `data: ${JSON.stringify({ run_id: crypto.randomUUID(), thread_id: "docker-thread" })}`,
    "",
    "event: values",
    `data: ${JSON.stringify({ messages: [], execution_mode: executionMode, __interrupt__: currentInterrupt ? [currentInterrupt] : [] })}`,
    "",
    "event: end",
    "data: {}",
    "",
  ].join("\n");
}

async function prepare(
  page: Page,
  executionMode: "approval" | "autonomous" = "approval",
  currentInterrupt = interrupt(),
) {
  const runBodies: Record<string, unknown>[] = [];
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
  await page.route("**/threads/search", (route) =>
    route.fulfill({ contentType: "application/json", body: "[]" }),
  );
  await page.route("**/threads", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        thread_id: "docker-thread",
        created_at: "2026-08-05T00:00:00Z",
        updated_at: "2026-08-05T00:00:00Z",
        metadata: {},
        status: "idle",
      }),
    }),
  );
  await page.route("**/threads/*/runs/stream", async (route) => {
    runBodies.push(route.request().postDataJSON());
    if (runBodies.length > 1) {
      await new Promise((resolve) => setTimeout(resolve, 1_000));
    }
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body:
        runBodies.length === 1
          ? sse(currentInterrupt, executionMode)
          : sse(undefined, executionMode),
    });
  });
  await page.goto("/");
  const continueButton = page.getByRole("button", { name: "Continue" });
  if (await continueButton.isVisible()) await continueButton.click();
  if (executionMode === "autonomous") {
    await page.getByRole("combobox", { name: "Select coding access" }).click();
    await page.getByRole("option", { name: "Full repo (autonomous)" }).click();
  }
  await page.locator("textarea").fill("Start the sandbox through the broker");
  await page.locator("textarea").press("Enter");
  await expect(
    page
      .getByLabel("Docker broker operation approval")
      .or(
        page.getByRole("alert").getByText("Docker Compose operation blocked"),
      ),
  ).toBeVisible();
  return runBodies;
}

async function fulfillCors(route: Route, body: unknown, status = 200) {
  if (route.request().method() === "OPTIONS") {
    await route.fulfill({
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": "http://127.0.0.1:3101",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
      },
    });
    return;
  }
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: { "Access-Control-Allow-Origin": "http://127.0.0.1:3101" },
    body: JSON.stringify(body),
  });
}

function terminalStatus() {
  return {
    operation_digest: operationDigest,
    plan_digest: planDigest,
    state: "succeeded",
    result_available: true,
  };
}

function terminalResult(digest = operationDigest) {
  return {
    operation_digest: digest,
    plan_digest: planDigest,
    state: "succeeded",
    result: { operation: "up", message: "Operation succeeded" },
  };
}

test("approval mode waits for review, then resumes only after a matching terminal result", async ({
  page,
}) => {
  let confirmations = 0;
  await page.route("http://127.0.0.1:8766/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() === "POST") {
      confirmations += 1;
      expect(route.request().postDataJSON()).toEqual({
        thread_id: "docker-thread",
        interrupt_id: "docker-interrupt-1",
        plan,
      });
      await fulfillCors(route, terminalStatus());
      return;
    }
    expect(path).toBe(`/v1/coder/results/${operationDigest}`);
    await fulfillCors(route, terminalResult());
  });

  const runBodies = await prepare(page);
  await expect.poll(() => confirmations).toBe(0);
  await page
    .getByRole("button", { name: "Confirm with broker and approve" })
    .click();
  await expect.poll(() => confirmations).toBe(1);
  await expect.poll(() => runBodies.length).toBe(2);
  expect(runBodies[1]).toMatchObject({
    command: { resume: { decisions: [{ type: "approve" }] } },
  });
});

test("autonomous mode submits once and resumes after the matching result", async ({
  page,
}) => {
  let confirmations = 0;
  await page.route("http://127.0.0.1:8766/**", async (route) => {
    if (route.request().method() === "POST") {
      confirmations += 1;
      await fulfillCors(route, terminalStatus());
      return;
    }
    await fulfillCors(route, terminalResult());
  });

  const runBodies = await prepare(page, "autonomous");
  await expect.poll(() => confirmations).toBe(1);
  await expect.poll(() => runBodies.length).toBe(2);
  expect(runBodies[1]).toMatchObject({
    command: { resume: { decisions: [{ type: "approve" }] } },
  });
});

test("mismatched terminal result blocks without LangGraph approval", async ({
  page,
}) => {
  await page.route("http://127.0.0.1:8766/**", async (route) => {
    if (route.request().method() === "POST") {
      await fulfillCors(route, terminalStatus());
      return;
    }
    await fulfillCors(route, terminalResult("c".repeat(64)));
  });

  const runBodies = await prepare(page);
  await page
    .getByRole("button", { name: "Confirm with broker and approve" })
    .click();
  await expect(
    page.getByText(/Blocked without LangGraph approval/),
  ).toBeVisible();
  expect(runBodies).toHaveLength(1);
});

test("reject resumes once without contacting the broker", async ({ page }) => {
  let brokerCalls = 0;
  await page.route("http://127.0.0.1:8766/**", async (route) => {
    brokerCalls += 1;
    await fulfillCors(route, {});
  });

  const runBodies = await prepare(page);
  await page
    .getByRole("button", { name: "Reject without broker call" })
    .click();
  await expect.poll(() => runBodies.length).toBe(2);
  expect(brokerCalls).toBe(0);
  expect(runBodies[1]).toMatchObject({
    command: { resume: { decisions: [{ type: "reject" }] } },
  });
});

test("malformed Docker envelope fails closed without generic controls", async ({
  page,
}) => {
  const malformed = interrupt({ ...plan, compose_files: [] });
  await prepare(page, "approval", malformed);
  await expect(
    page.getByRole("alert").getByText("Docker Compose operation blocked"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Submit" })).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Confirm with broker and approve" }),
  ).toHaveCount(0);
});
