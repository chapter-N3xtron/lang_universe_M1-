import { expect, test, type Page } from "@playwright/test";

const THREAD_ID = "visual-workspace-thread";
const SOURCE_ID = "repo-source";
const evidence = {
  id: SOURCE_ID,
  kind: "repo_file",
  locator: "backend/src/chat_ui.py",
  title: "Outer LangGraph workflow",
  content_sha256: "a".repeat(64),
};

const artifact = {
  renderer: "react_flow",
  artifact_id: "request-flow",
  title: "Request flow",
  alt_text: "A user request flows through Jasper to a validated visual.",
  source_message_id: "visual-answer",
  payload: {
    grounding_kind: "repo",
    sources: [evidence],
    nodes: [
      {
        id: "request",
        label: "User request",
        kind: "input",
        narration: "The user request enters the application.",
        claim_status: "observed",
        evidence_refs: [SOURCE_ID],
      },
      {
        id: "jasper",
        label: "Jasper",
        kind: "concept",
        narration: "Jasper interprets the request using grounded tools.",
        claim_status: "observed",
        evidence_refs: [SOURCE_ID],
      },
      {
        id: "visual",
        label: "Validated visual",
        kind: "output",
        narration: "The validated visual presents the grounded result.",
        claim_status: "observed",
        evidence_refs: [SOURCE_ID],
      },
    ],
    narration_order: ["request", "jasper", "visual"],
    edges: [
      {
        source: "request",
        target: "jasper",
        label: "enters",
        relation: "flows_to",
        claim_status: "observed",
        evidence_refs: [SOURCE_ID],
      },
      {
        source: "jasper",
        target: "visual",
        label: "renders",
        relation: "flows_to",
        claim_status: "observed",
        evidence_refs: [SOURCE_ID],
      },
    ],
    direction: "left_to_right",
  },
};

function historyState(
  threadId: string,
  structuredResponse: Record<string, unknown>,
) {
  return {
    values: {
      messages: [
        { id: "visual-question", type: "human", content: "Draw the flow" },
        {
          id: "visual-tool-call",
          type: "ai",
          content: "",
          tool_calls: [
            {
              id: "internal-visual-call",
              name: "draw_concept_map",
              args: {
                title: "INTERNAL_ONLY_TITLE",
                nodes: [{ id: "internal", label: "INTERNAL_ONLY_NODE" }],
                edges: [],
              },
              type: "tool_call",
            },
          ],
        },
        {
          id: "visual-tool-result",
          type: "tool",
          name: "draw_concept_map",
          tool_call_id: "internal-visual-call",
          content: JSON.stringify(artifact),
        },
        {
          id: "visual-answer",
          type: "ai",
          content: "Here is the request flow.",
        },
      ],
      jasper_structured_response: structuredResponse,
      visual_artifacts: [artifact],
      layout_suggestion: {
        mode: "split",
        reason: "See the flow beside the explanation.",
      },
      jasper_strategy: "two_pass",
    },
    next: [],
    tasks: [],
    metadata: {},
    created_at: "2026-07-30T00:00:00Z",
    checkpoint: {
      thread_id: threadId,
      checkpoint_ns: "",
      checkpoint_id: `${threadId}-checkpoint`,
    },
    parent_checkpoint: null,
  };
}

async function mockBase(page: Page) {
  await page.route("**/threads/search", (route) =>
    route.fulfill({ contentType: "application/json", body: "[]" }),
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
}

test.beforeEach(async ({ page }) => {
  await mockBase(page);
});

test("workspace modes remain available and persistent without an artifact", async ({
  page,
}) => {
  await page.goto("/");

  const workspace = page.locator("[data-workspace-mode]");
  await expect(page.getByRole("button", { name: "Focus chat" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Split chat and visual" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Focus visual" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Focus visual" }).click();
  await expect(workspace).toHaveAttribute("data-workspace-mode", "visual");
  await expect(page.getByText("Visual workspace ready")).toBeVisible();
  await expect(
    page.getByText(/Concept maps and grounded code visualizations/),
  ).toBeVisible();
  await expect(page.locator("textarea")).toBeVisible();

  await page.reload();
  await expect(workspace).toHaveAttribute("data-workspace-mode", "visual");
  await expect(page.getByText("Visual workspace ready")).toBeVisible();

  await page.getByRole("button", { name: "Split chat and visual" }).click();
  await expect(workspace).toHaveAttribute("data-workspace-mode", "split");
  await expect(
    page.getByRole("separator", { name: "Resize chat and visual panes" }),
  ).toBeVisible();
  await expect(page.locator('[data-workspace-surface="chat"]')).toBeVisible();
  await expect(page.locator('[data-workspace-surface="visual"]')).toBeVisible();
  await expect(page.locator("textarea")).toBeVisible();
});

test("the human controls whether a suggested visual takes the foreground", async ({
  page,
}) => {
  const response = {
    version: 2,
    voice_text: "Here is the request flow.",
    artifacts: [artifact],
    layout_suggestion: {
      mode: "split",
      reason: "See the flow beside the explanation.",
    },
    diagnostic: null,
  };
  await page.route(`**/threads/${THREAD_ID}/history`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([historyState(THREAD_ID, response)]),
    }),
  );

  await page.goto(`/?threadId=${THREAD_ID}`);

  const workspace = page.locator("[data-workspace-mode]");
  await expect(workspace).toHaveAttribute("data-workspace-mode", "chat");
  await expect(page.getByText("Here is the request flow.")).toBeVisible();
  await expect(
    page.getByText("draw_concept_map", { exact: false }),
  ).toHaveCount(0);
  await expect(
    page.getByText("INTERNAL_ONLY_NODE", { exact: false }),
  ).toHaveCount(0);
  await expect(page.getByText("Tool Result", { exact: false })).toHaveCount(0);
  await expect(
    page.getByText("See the flow beside the explanation."),
  ).toBeVisible();

  await page.getByRole("button", { name: "Apply" }).click();
  await expect(workspace).toHaveAttribute("data-workspace-mode", "split");
  await expect(page.getByRole("button", { name: "Focus chat" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Split chat and visual" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Focus visual" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /compact|put .* first/i }),
  ).toHaveCount(0);

  const chatBox = await page
    .locator('[data-workspace-surface="chat"]')
    .boundingBox();
  const visualBox = await page
    .locator('[data-workspace-surface="visual"]')
    .boundingBox();
  expect(chatBox).not.toBeNull();
  expect(visualBox).not.toBeNull();
  const composer = page.locator("[data-workspace-composer]");
  const composerBox = await composer.boundingBox();
  expect(composerBox).not.toBeNull();
  expect(chatBox!.x + chatBox!.width).toBeLessThanOrEqual(visualBox!.x + 2);
  expect(Math.abs(chatBox!.width - visualBox!.width)).toBeLessThan(20);
  expect(chatBox!.y + chatBox!.height).toBeLessThanOrEqual(composerBox!.y + 1);
  expect(visualBox!.y + visualBox!.height).toBeLessThanOrEqual(
    composerBox!.y + 1,
  );
  expect(composerBox!.x).toBeLessThanOrEqual(chatBox!.x + 1);
  expect(composerBox!.x + composerBox!.width).toBeGreaterThanOrEqual(
    visualBox!.x + visualBox!.width - 1,
  );

  const divider = page.getByRole("separator", {
    name: "Resize chat and visual panes",
  });
  const dividerBox = await divider.boundingBox();
  expect(dividerBox).not.toBeNull();
  await page.mouse.move(
    dividerBox!.x + dividerBox!.width / 2,
    dividerBox!.y + dividerBox!.height / 2,
  );
  await page.mouse.down();
  await page.mouse.move(
    dividerBox!.x + 100,
    dividerBox!.y + dividerBox!.height / 2,
    { steps: 8 },
  );
  await page.mouse.up();
  const resizedChatBox = await page
    .locator('[data-workspace-surface="chat"]')
    .boundingBox();
  expect(resizedChatBox!.width).toBeGreaterThan(chatBox!.width + 60);

  const textarea = page.locator("textarea");
  await expect(textarea).toBeVisible();
  const textareaBox = await textarea.boundingBox();
  expect(textareaBox).not.toBeNull();
  expect(textareaBox!.y + textareaBox!.height).toBeLessThanOrEqual(
    page.viewportSize()!.height,
  );

  const outline = page.getByRole("button", { name: "Outline" });
  await expect(outline).toBeVisible();
  await outline.click();
  await expect(page.getByText(artifact.alt_text)).toBeVisible();
  await expect(page.getByText("User request", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Validated visual", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Outer LangGraph workflow")).toBeVisible();
  await expect(page.getByText("backend/src/chat_ui.py")).toBeVisible();

  await page.getByRole("button", { name: "Focus chat" }).click();
  await expect(workspace).toHaveAttribute("data-workspace-mode", "chat");
  await expect(page.locator('[data-workspace-surface="visual"]')).toHaveCount(
    0,
  );
  await expect(textarea).toBeVisible();

  await page.getByRole("button", { name: "Focus visual" }).click();
  await expect(workspace).toHaveAttribute("data-workspace-mode", "visual");
  await expect(page.locator('[data-workspace-surface="chat"]')).toHaveCount(0);
  await expect(textarea).toBeVisible();
  const focusedComposerBox = await composer.boundingBox();
  const focusedTextareaBox = await textarea.boundingBox();
  expect(focusedComposerBox).not.toBeNull();
  expect(focusedTextareaBox).not.toBeNull();
  expect(
    focusedTextareaBox!.y + focusedTextareaBox!.height,
  ).toBeLessThanOrEqual(page.viewportSize()!.height);

  await page.reload();
  await expect(workspace).toHaveAttribute("data-workspace-mode", "visual");
});

test("concept-map controls and labels retain contrast in dark mode", async ({
  page,
}) => {
  const darkThread = "dark-visual-thread";
  const response = {
    version: 2,
    voice_text: "Here is the request flow.",
    artifacts: [artifact],
    layout_suggestion: { mode: "visual", reason: "Focus the map." },
    diagnostic: null,
  };
  await page.addInitScript(() => localStorage.setItem("theme", "dark"));
  await page.route(`**/threads/${darkThread}/history`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([historyState(darkThread, response)]),
    }),
  );

  await page.goto(`/?threadId=${darkThread}`);
  await page.getByRole("button", { name: "Apply" }).click();
  const control = page.locator(".react-flow__controls-button").first();
  await expect(control).toBeVisible();
  const colors = await control.evaluate((element) => {
    const style = getComputedStyle(element);
    return { background: style.backgroundColor, foreground: style.color };
  });
  expect(colors.background).not.toBe(colors.foreground);
  expect(colors.background).not.toBe("rgb(255, 255, 255)");
  await expect(page.locator(".react-flow__minimap")).toHaveCount(0);

  const label = page.locator(".react-flow__edge-text").first();
  const labelBackground = page.locator(".react-flow__edge-textbg").first();
  await expect(label).toBeVisible();
  await expect(labelBackground).toBeVisible();
  const labelFill = await label.evaluate(
    (element) => getComputedStyle(element).fill,
  );
  const backgroundFill = await labelBackground.evaluate(
    (element) => getComputedStyle(element).fill,
  );
  expect(labelFill).not.toBe(backgroundFill);
});

test("return edges use separate lanes around the left-to-right flow", async ({
  page,
}) => {
  const feedbackThread = "feedback-edge-thread";
  const feedbackArtifact = {
    ...artifact,
    artifact_id: "request-flow-with-feedback",
    payload: {
      ...artifact.payload,
      edges: [
        ...artifact.payload.edges,
        {
          source: "visual",
          target: "jasper",
          label: "returns result",
          relation: "flows_to",
          claim_status: "observed",
          evidence_refs: [SOURCE_ID],
        },
        {
          source: "visual",
          target: "request",
          label: "closes loop",
          relation: "flows_to",
          claim_status: "observed",
          evidence_refs: [SOURCE_ID],
        },
      ],
    },
  };
  const response = {
    version: 2,
    voice_text: "Here is the request flow with feedback.",
    artifacts: [feedbackArtifact],
    layout_suggestion: { mode: "visual", reason: "Inspect the flow." },
    diagnostic: null,
  };
  await page.route(`**/threads/${feedbackThread}/history`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([historyState(feedbackThread, response)]),
    }),
  );

  await page.goto(`/?threadId=${feedbackThread}`);
  await page.getByRole("button", { name: "Apply" }).click();

  const feedbackEdges = page.locator(".concept-map-feedback-edge");
  await expect(feedbackEdges).toHaveCount(2);
  const paths = await feedbackEdges.evaluateAll((elements) =>
    elements.map((element) => element.getAttribute("d")),
  );
  expect(paths[0]).not.toBe(paths[1]);
  expect(paths.every((path) => (path?.match(/[ML]/g)?.length ?? 0) === 4)).toBe(
    true,
  );
  await expect(page.getByText("returns result", { exact: true })).toBeVisible();
  await expect(page.getByText("closes loop", { exact: true })).toBeVisible();
});

test("node narration highlights, replays, and seeds a grounded Jasper follow-up", async ({
  page,
}) => {
  const interactionThread = "visual-node-interaction-thread";
  let spokenText = "";
  await page.route("http://127.0.0.1:8000/api/tts/stream", async (route) => {
    spokenText = route.request().postDataJSON().text;
    await route.fulfill({
      contentType: "text/event-stream",
      body: "",
    });
  });
  const response = {
    version: 2,
    voice_text: "Here is the grounded request flow.",
    artifacts: [artifact],
    layout_suggestion: { mode: "visual", reason: "Inspect each node." },
    diagnostic: null,
  };
  await page.route(`**/threads/${interactionThread}/history`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([historyState(interactionThread, response)]),
    }),
  );

  await page.goto(`/?threadId=${interactionThread}`);
  await page.getByRole("button", { name: "Apply" }).click();
  const jasperNode = page
    .locator(".react-flow__node")
    .filter({ hasText: "Jasper" });
  await jasperNode.click();

  await expect(
    page.getByRole("button", { name: "Discuss with Jasper" }),
  ).toBeVisible();
  await expect.poll(() => spokenText).toContain("grounded tools");

  await page.evaluate((artifactId) => {
    window.dispatchEvent(
      new CustomEvent("visual:narration-node", {
        detail: { artifactId, nodeId: "jasper" },
      }),
    );
  }, artifact.artifact_id);
  await expect(jasperNode.locator('[data-active-node="true"]')).toBeVisible();

  await page.getByRole("button", { name: "Discuss with Jasper" }).click();
  await expect(page.locator("textarea")).toHaveValue(
    /explore the “Jasper” node/,
  );
  await expect(page.getByRole("combobox", { name: "Select agent" })).toHaveText(
    "Jasper",
  );
});

test("malformed visual data is rejected without breaking chat", async ({
  page,
}) => {
  const badThread = "invalid-visual-thread";
  const invalidArtifact = {
    ...artifact,
    artifact_id: "invalid-flow",
    payload: {
      ...artifact.payload,
      edges: [
        {
          source: "request",
          target: "missing",
          relation: "flows_to",
          claim_status: "observed",
          evidence_refs: [SOURCE_ID],
        },
      ],
    },
  };
  const response = {
    version: 2,
    voice_text: "The text answer remains available.",
    artifacts: [invalidArtifact],
    layout_suggestion: null,
    diagnostic: null,
  };
  const state = historyState(badThread, response);
  state.values.messages[1].content = "The text answer remains available.";
  await page.route(`**/threads/${badThread}/history`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([state]),
    }),
  );

  await page.goto(`/?threadId=${badThread}`);

  await expect(
    page.getByText("The text answer remains available."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Focus visual" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Focus visual" }).click();
  await expect(page.getByText("Visual workspace ready")).toBeVisible();
});

test("a disconnected request-flow artifact is rejected", async ({ page }) => {
  const brokenThread = "disconnected-visual-thread";
  const disconnectedArtifact = {
    ...artifact,
    artifact_id: "disconnected-request-flow",
    payload: {
      ...artifact.payload,
      nodes: [
        {
          id: "user",
          label: "User",
          narration: "The user starts the flow.",
          kind: "input",
          claim_status: "observed",
          evidence_refs: [SOURCE_ID],
        },
        {
          id: "ui",
          label: "UI Layer",
          narration: "The UI receives the request.",
          kind: "concept",
          claim_status: "observed",
          evidence_refs: [SOURCE_ID],
        },
        {
          id: "langgraph",
          label: "LangGraph",
          narration: "LangGraph orchestrates work.",
          kind: "group",
          claim_status: "observed",
          evidence_refs: [SOURCE_ID],
        },
        {
          id: "jasper",
          label: "Jasper",
          narration: "Jasper processes the request.",
          kind: "concept",
          claim_status: "observed",
          evidence_refs: [SOURCE_ID],
        },
        {
          id: "tools",
          label: "Tool Dispatcher",
          narration: "Tools perform grounded actions.",
          kind: "code",
          claim_status: "observed",
          evidence_refs: [SOURCE_ID],
        },
        {
          id: "output",
          label: "Response Formatter",
          narration: "The response is formatted.",
          kind: "output",
          claim_status: "observed",
          evidence_refs: [SOURCE_ID],
        },
      ],
      narration_order: ["user", "ui", "langgraph", "jasper", "tools", "output"],
      edges: [
        {
          source: "user",
          target: "ui",
          relation: "flows_to",
          claim_status: "observed",
          evidence_refs: [SOURCE_ID],
        },
        {
          source: "ui",
          target: "langgraph",
          relation: "flows_to",
          claim_status: "observed",
          evidence_refs: [SOURCE_ID],
        },
        {
          source: "jasper",
          target: "tools",
          relation: "calls",
          claim_status: "observed",
          evidence_refs: [SOURCE_ID],
        },
        {
          source: "jasper",
          target: "output",
          relation: "flows_to",
          claim_status: "observed",
          evidence_refs: [SOURCE_ID],
        },
      ],
    },
  };
  const response = {
    version: 2,
    voice_text: "The explanation remains readable.",
    artifacts: [disconnectedArtifact],
    layout_suggestion: null,
    diagnostic: null,
  };
  const state = historyState(brokenThread, response);
  state.values.messages[3].content = "The explanation remains readable.";
  await page.route(`**/threads/${brokenThread}/history`, (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify([state]),
    }),
  );

  await page.goto(`/?threadId=${brokenThread}`);

  await expect(
    page.getByText("The explanation remains readable."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Focus visual" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Focus visual" }).click();
  await expect(page.getByText("Visual workspace ready")).toBeVisible();
});
