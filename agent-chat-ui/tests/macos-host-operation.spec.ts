import { expect, Page, test } from "@playwright/test";

const digest = "a".repeat(64);
const sha = "b".repeat(64);

const plan = {
  action: {
    category: "https_download",
    url: "https://download.blender.org/release/Blender4.3/blender.dmg",
    destination: "/Users/test/Library/Caches/host-executor/blender.dmg",
    sha256: sha,
    max_bytes: 500_000_000,
    redirect_limit: 1,
    archive: "dmg",
  },
  expected_mutations: [
    {
      operation: "create",
      path: "/Users/test/Library/Caches/host-executor/blender.dmg",
      detail: "Create the verified downloaded artifact",
    },
  ],
  privilege: "user",
  timeout_seconds: 900,
  output_limit_bytes: 65536,
  rollback: {
    strategy: "remove_created_destination",
    removes_only_request_created_paths: true,
    may_require_human_inspection: false,
  },
  expiry_seconds: 600,
};

function interrupt(
  actionRequests: Record<string, unknown>[] = [
    {
      name: "request_macos_host_operation",
      args: plan,
      description: "Download Blender on the physical Mac",
    },
  ],
  reviewConfigs: Record<string, unknown>[] = [
    {
      action_name: "request_macos_host_operation",
      allowed_decisions: ["approve", "reject"],
    },
  ],
) {
  return {
    id: "mac-interrupt-1",
    value: { action_requests: actionRequests, review_configs: reviewConfigs },
  };
}

function sse(currentInterrupt?: Record<string, unknown>) {
  return [
    "event: metadata",
    `data: ${JSON.stringify({ run_id: crypto.randomUUID(), thread_id: "mac-thread" })}`,
    "",
    "event: values",
    `data: ${JSON.stringify({ messages: [], __interrupt__: currentInterrupt ? [currentInterrupt] : [] })}`,
    "",
    "event: end",
    "data: {}",
    "",
  ].join("\n");
}

async function prepare(page: Page, currentInterrupt = interrupt()) {
  const runBodies: Record<string, any>[] = [];
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
        thread_id: "mac-thread",
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
      // Keep the interrupt card mounted briefly so receipt-state assertions can
      // observe the executor-before-resume handoff.
      await new Promise((resolve) => setTimeout(resolve, 1_500));
    }
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: runBodies.length === 1 ? sse(currentInterrupt) : sse(),
    });
  });
  await page.goto("/");
  const continueButton = page.getByRole("button", { name: "Continue" });
  if (await continueButton.isVisible()) await continueButton.click();
  await page.locator("textarea").fill("Request a reviewed Mac operation");
  await page.locator("textarea").press("Enter");
  await expect(
    page
      .getByRole("heading", { name: "Mac approval needed" })
      .or(page.getByRole("alert").getByText("Mac host operation blocked")),
  ).toBeVisible();
  return runBodies;
}

function signedReceipt(status = "succeeded", manualStep: string | null = null) {
  return {
    receipt: {
      schema_version: 1,
      request_digest: digest,
      request_id: "request-1",
      terminal_status: status,
      started_at: null,
      finished_at: "2026-08-05T00:00:01Z",
      action_category: "https_download",
      executable: "download-adapter",
      argv_summary: [],
      working_directory: null,
      approved_paths: [],
      observed_paths: [],
      artifact_hashes: [],
      process: {},
      verified_outcome: status === "succeeded",
      observed_mutations: [],
      rollback: {},
      remaining_human_step: manualStep,
      message: "Executor terminal receipt",
    },
    algorithm: "Ed25519",
    key_id: "host-key-1",
    signature: "signed-receipt-value",
  };
}

test("renders immutable Mac-host fields, runtime boundary, and no generic controls", async ({
  page,
}) => {
  await prepare(page);
  const card = page.getByLabel("Mac host operation approval");
  await expect(
    card
      .getByRole("status")
      .getByText("Paused — waiting for your approval decision."),
  ).toBeVisible();
  await expect(
    card.getByText("Physical Mac host", { exact: false }).first(),
  ).toBeVisible();
  await expect(
    card.getByText("Linux container", { exact: false }),
  ).toBeVisible();
  await expect(
    card.getByText("Download one verified file to", { exact: false }),
  ).toBeVisible();
  await expect(
    card.getByText("Download Blender on the physical Mac", { exact: false }),
  ).toBeVisible();
  await card.getByText("Technical plan details", { exact: true }).click();
  await expect(card.getByText("https_download", { exact: true })).toBeVisible();
  await expect(card.getByText(plan.action.url, { exact: true })).toBeVisible();
  await expect(card.getByText(sha, { exact: true })).toBeVisible();
  await expect(
    card.getByText(plan.action.destination, { exact: true }).first(),
  ).toBeVisible();
  await expect(card.getByText("create:", { exact: false })).toBeVisible();
  await expect(card.getByText("user", { exact: true })).toBeVisible();
  await expect(card.getByText("900 seconds", { exact: true })).toBeVisible();
  await expect(card.getByText("65,536 bytes", { exact: true })).toBeVisible();
  await expect(
    card.getByText("remove_created_destination", { exact: true }),
  ).toBeVisible();
  await expect(
    card.getByText("600 seconds after executor acceptance", { exact: true }),
  ).toBeVisible();
  for (const forbidden of [
    "Approve All",
    "Mark as Resolved",
    "Save",
    "Capture",
    "Edit",
    "Submit all",
  ]) {
    await expect(
      card.getByRole("button", { name: new RegExp(forbidden, "i") }),
    ).toHaveCount(0);
  }
});

test("coordinates executor receipt before exactly one ordinary approve and locks duplicate clicks", async ({
  page,
}) => {
  const events: string[] = [];
  let executorPosts = 0;
  await page.route("http://127.0.0.1:8765/v1/confirmations", async (route) => {
    executorPosts += 1;
    events.push("executor-post");
    expect(route.request().postDataJSON()).toEqual({
      thread_id: "mac-thread",
      interrupt_id: "mac-interrupt-1",
      plan,
    });
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        plan_digest: digest,
        state: "succeeded",
        receipt_available: true,
      }),
    });
  });
  await page.route(`http://127.0.0.1:8765/v1/receipts/${digest}`, (route) => {
    events.push("signed-receipt");
    return route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(signedReceipt()),
    });
  });
  const runBodies = await prepare(page);
  const initialCount = runBodies.length;
  const button = page.getByRole("button", {
    name: "Review on Mac and approve",
  });
  await button.dblclick();
  await expect.poll(() => runBodies.length).toBe(initialCount + 1);
  events.push("langgraph-resume");
  expect(executorPosts).toBe(1);
  expect(events).toEqual([
    "executor-post",
    "signed-receipt",
    "langgraph-resume",
  ]);
  expect(runBodies.at(-1)?.command.resume.decisions).toEqual([
    { type: "approve" },
  ]);
  await expect(page.getByLabel("Mac host operation approval")).toHaveCount(0);
});

test("ordinary rejection sends one reject decision and never calls the executor", async ({
  page,
}) => {
  let executorCalls = 0;
  await page.route("http://127.0.0.1:8765/**", (route) => {
    executorCalls += 1;
    return route.abort();
  });
  const runBodies = await prepare(page);
  const initialCount = runBodies.length;
  await page
    .getByRole("button", {
      name: "Reject Mac action and return to Coder",
    })
    .dblclick();
  await expect.poll(() => runBodies.length).toBe(initialCount + 1);
  const rejection = runBodies.at(-1)?.command.resume.decisions[0];
  expect(rejection.type).toBe("reject");
  expect(rejection.message).toContain("Do not retry the same Mac tool call");
  expect(rejection.message).toContain("request_docker_compose_operation");
  expect(executorCalls).toBe(0);
});

test("digest mismatch or absent receipt fails closed without resume", async ({
  page,
}) => {
  await page.route("http://127.0.0.1:8765/v1/confirmations", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        plan_digest: digest,
        state: "failed",
        receipt_available: true,
      }),
    }),
  );
  await page.route(`http://127.0.0.1:8765/v1/receipts/${digest}`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ...signedReceipt("failed"),
        receipt: {
          ...signedReceipt("failed").receipt,
          request_digest: "c".repeat(64),
        },
      }),
    }),
  );
  const runBodies = await prepare(page);
  const initialCount = runBodies.length;
  await page.getByRole("button", { name: "Review on Mac and approve" }).click();
  await expect(page.getByText(/Approval did not complete/)).toBeVisible();
  expect(runBodies).toHaveLength(initialCount);
  await expect(
    page.getByText(/The result could not be verified safely/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Mac approval unavailable" }),
  ).toBeDisabled();
});

test("terminal status without a receipt fails closed and does not resume", async ({
  page,
}) => {
  await page.route("http://127.0.0.1:8765/v1/confirmations", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        plan_digest: digest,
        state: "cancelled",
        receipt_available: true,
      }),
    }),
  );
  await page.route(`http://127.0.0.1:8765/v1/receipts/${digest}`, (route) =>
    route.fulfill({ status: 404, body: "receipt unavailable" }),
  );
  const runBodies = await prepare(page);
  const initialCount = runBodies.length;
  await page.getByRole("button", { name: "Review on Mac and approve" }).click();
  await expect(page.getByText(/Approval did not complete/)).toBeVisible();
  expect(runBodies).toHaveLength(initialCount);
  await expect(page.getByText(/HTTP 404/)).toBeVisible();
});

test("permanent HTTP 409 explains the policy denial and disables futile retry", async ({
  page,
}) => {
  let executorAttempts = 0;
  await page.route("http://127.0.0.1:8765/v1/confirmations", (route) => {
    executorAttempts += 1;
    return route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ detail: "application is not allowlisted" }),
    });
  });
  const runBodies = await prepare(page);
  const initialCount = runBodies.length;

  await page.getByRole("button", { name: "Review on Mac and approve" }).click();

  await expect(
    page.getByRole("status").getByText(/Coder is not working on this task/),
  ).toBeVisible();
  await expect(page.getByText(/application is not allowlisted/)).toBeVisible();
  await expect(
    page.getByText(/Repeating approval will not change this policy decision/),
  ).toBeVisible();
  await expect(
    page.getByText(/including the Docker broker for Docker work/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Mac approval unavailable" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", {
      name: "Reject Mac action and return to Coder",
    }),
  ).toBeEnabled();
  expect(executorAttempts).toBe(1);
  expect(runBodies).toHaveLength(initialCount);
});

test("temporary executor conflict offers a deliberate retry with the same request", async ({
  page,
}) => {
  let executorAttempts = 0;
  await page.route("http://127.0.0.1:8765/v1/confirmations", (route) => {
    executorAttempts += 1;
    return route.fulfill({
      status: 409,
      contentType: "application/json",
      body: JSON.stringify({ detail: "operation is active" }),
    });
  });
  const runBodies = await prepare(page);
  const initialCount = runBodies.length;

  await page.getByRole("button", { name: "Review on Mac and approve" }).click();
  const retryButton = page.getByRole("button", { name: "Try approval again" });
  await expect(retryButton).toBeEnabled();
  await expect(
    page.getByText(/This may be temporary.*same reviewed request will be used/),
  ).toBeVisible();
  expect(runBodies).toHaveLength(initialCount);

  await retryButton.click();
  await expect.poll(() => executorAttempts).toBe(2);
  expect(runBodies).toHaveLength(initialCount);
});

test("terminal partial receipt presents manual-step language and resumes truthfully", async ({
  page,
}) => {
  await page.route("http://127.0.0.1:8765/v1/confirmations", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        plan_digest: digest,
        state: "partial",
        receipt_available: true,
      }),
    }),
  );
  await page.route(`http://127.0.0.1:8765/v1/receipts/${digest}`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify(
        signedReceipt("partial", "Remove the staged artifact in Finder"),
      ),
    }),
  );
  const runBodies = await prepare(page);
  const initialCount = runBodies.length;
  await page.getByRole("button", { name: "Review on Mac and approve" }).click();
  await expect.poll(() => runBodies.length).toBe(initialCount + 1);
  expect(runBodies.at(-1)?.command.resume.decisions).toEqual([
    { type: "approve" },
  ]);
  await expect(page.getByText("Mac executor status: partial")).toBeVisible();
  await expect(
    page.getByText(
      /Required manual Mac step: Remove the staged artifact in Finder/,
    ),
  ).toBeVisible();
  await expect(
    page.getByText(
      /will not automate or capture authorization, passwords, Touch ID/,
    ),
  ).toBeVisible();
  await expect(page.getByText(/partial mutation/).last()).toBeVisible();
});

test("mixed host envelopes fail closed with no bulk or generic escape path", async ({
  page,
}) => {
  const mixed = interrupt(
    [
      { name: "request_macos_host_operation", args: plan },
      { name: "run_workspace_command", args: { argv: ["git", "status"] } },
    ],
    [
      {
        action_name: "request_macos_host_operation",
        allowed_decisions: ["approve", "reject"],
      },
      {
        action_name: "run_workspace_command",
        allowed_decisions: ["approve", "edit", "reject"],
      },
    ],
  );
  await prepare(page, mixed);
  await expect(
    page.getByRole("alert").getByText("Mac host operation blocked"),
  ).toBeVisible();
  await expect(
    page
      .getByRole("alert")
      .getByRole("button", { name: /Approve|Resolve|Submit|Save|Edit/i }),
  ).toHaveCount(0);
});
