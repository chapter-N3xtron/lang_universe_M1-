import { expect, test, type Page } from "@playwright/test";

const API_URL = "http://phase5-agent.test";
const THREAD_A = "phase5-thread-a";
const THREAD_B = "phase5-thread-b";
const DOCUMENT_ID = "canonical-document-alpha";
const UNAVAILABLE_ID = "private-unavailable-document-id";
const FRAGMENT_BODY = "PRIVATE FRAGMENT BODY MUST NEVER RENDER";

const initialTag = "canonical-initial";
const updatedTag = "canonical-updated";

type RecordedRequest = {
  method: string;
  pathname: string;
  headers: Record<string, string>;
  body?: unknown;
};

function canonicalDocument(tag: string) {
  return {
    record_type: "document",
    source_status: "active",
    id: DOCUMENT_ID,
    title: "Canonical installation guide",
    tags: [tag],
    source_uri: "https://docs.example.test/guide",
    source_type: "approved_manual",
    source_revision: "revision-1",
    // Untrusted extra fields must never become a mutation contract.
    session_document_link_action: {
      action: "remove",
      document_id: "forged-document-id",
    },
    content: "STALE CACHED FULL DOCUMENT MUST NEVER RENDER",
  };
}

function storeItem(key: string, value: Record<string, unknown>) {
  return {
    namespace: ["installation-docs", "documents"],
    key,
    value,
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
  };
}

async function installFullyMockedAgentServer(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("lg:chat:apiKey", "phase5-test-key");
  });
  const requests: RecordedRequest[] = [];
  const stateReads: Record<string, number> = { [THREAD_A]: 0, [THREAD_B]: 0 };
  const links: Record<string, string[]> = {
    [THREAD_A]: [DOCUMENT_ID, UNAVAILABLE_ID],
    [THREAD_B]: [DOCUMENT_ID],
  };
  let canonicalTag = initialTag;
  let sidecarUploads = 0;

  await page.route(
    "http://127.0.0.1:8000/api/attachments/document",
    async (route) => {
      sidecarUploads += 1;
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          filename: "owner-book.pdf",
          ocr_upload: {
            reference: `upload:${"a".repeat(32)}-owner-book.pdf`,
            filename: "owner-book.pdf",
          },
        }),
      });
    },
  );

  await page.route(`${API_URL}/**`, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const body = request.postData() ? request.postDataJSON() : undefined;
    requests.push({
      method: request.method(),
      pathname: url.pathname,
      headers: request.headers(),
      body,
    });

    const json = (value: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(value),
      });

    if (url.pathname === "/info") return json({});
    if (url.pathname === "/runtime-identity") {
      return json({
        runtime_id: "backend-postgres-v1",
        durable: true,
        persistence: "postgres",
      });
    }
    if (url.pathname === "/threads/search") return json([]);
    if (url.pathname === "/api/models") {
      return json({ default: "mock/model", models: [] });
    }
    if (url.pathname === "/api/tts/voices") return json({ voices: [] });
    if (url.pathname === "/session-catalog/preferences/model") {
      return json({ model_id: null });
    }
    if (/^\/threads\/[^/]+\/history$/.test(url.pathname)) return json([]);
    if (/^\/session-catalog\/[^/]+$/.test(url.pathname)) {
      return json({
        session_id: url.pathname.split("/").at(-1),
        thread_id: url.pathname.split("/").at(-1),
        status: "open",
        active_minutes: 0,
        tent_poles: [],
      });
    }

    const stateMatch = url.pathname.match(/^\/threads\/([^/]+)\/state$/);
    if (stateMatch) {
      const threadId = stateMatch[1];
      stateReads[threadId] = (stateReads[threadId] ?? 0) + 1;
      return json({ values: { session_document_ids: links[threadId] ?? [] } });
    }

    if (url.pathname === "/store/items/search") {
      const payload = body as {
        namespace_prefix?: string[];
        filter?: unknown;
        query?: string;
      };
      if (
        payload.namespace_prefix?.[0] === "local-owner-v1" &&
        payload.namespace_prefix?.[1] === "session-sources"
      ) {
        return json({
          items: [
            storeItem("source-only", {
              id: "source-only",
              stable_evidence_id: "evidence-only",
              display_name: "Separate Librarian source",
              original_title: "Separate Librarian source",
              locator: "https://source.example.test",
              kind: "web_url",
              retrieved_at: "2026-09-01T00:00:00Z",
              truncated: false,
              content_sha256: "abc123",
            }),
          ],
        });
      }
      if (
        payload.namespace_prefix?.[1] === "fragments" ||
        payload.namespace_prefix?.[1] === "documents"
      ) {
        return json({ error: "Phase 5 direct Store access is forbidden" }, 403);
      }
    }

    if (url.pathname === "/phase5/owner-upload") {
      return json({
        ok: true,
        status: "complete",
        document_id: "owner-upload-document",
        fragment_count: 7,
      });
    }

    if (url.pathname === "/phase5/public-document") {
      return json({
        ok: true,
        status: "complete",
        document_id: "public-document-content-digest",
        fragment_count: 5,
      });
    }

    if (url.pathname === "/phase5/installation-library") {
      const operation = body as Record<string, unknown>;
      const kind = operation.operation;
      let documents: ReturnType<typeof canonicalDocument>[] = [];
      if (kind === "resolve") {
        const ids = operation.document_ids as string[];
        documents = ids.includes(DOCUMENT_ID)
          ? [canonicalDocument(canonicalTag)]
          : [];
      } else if (kind === "metadata" || kind === "semantic") {
        documents = [canonicalDocument(canonicalTag)];
      }
      return json({
        ok: true,
        status: "complete",
        operation: kind,
        documents,
      });
    }

    const runMatch = url.pathname.match(/^\/threads\/([^/]+)\/runs\/wait$/);
    if (runMatch) {
      const threadId = runMatch[1];
      const payload = body as {
        input: {
          session_document_link_action: {
            action: "add" | "remove";
            document_id: string;
          };
        };
      };
      const action = payload.input.session_document_link_action;
      if (
        action.action === "add" &&
        !links[threadId].includes(action.document_id)
      ) {
        links[threadId].push(action.document_id);
      }
      if (action.action === "remove") {
        links[threadId] = links[threadId].filter(
          (documentId) => documentId !== action.document_id,
        );
      }
      canonicalTag = updatedTag;
      return json({
        session_document_link_result: { ok: true },
        session_document_ids: links[threadId],
      });
    }

    return json(
      { error: `Unmocked Agent Server request: ${url.pathname}` },
      501,
    );
  });

  // These UI-owned preference calls are mocked too; no request reaches a backend.
  await page.route("**/api/models", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ default: "mock/model", models: [] }),
    }),
  );
  await page.route("**/api/tts/voices", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ voices: [] }),
    }),
  );

  return { requests, stateReads, sidecarUploads: () => sidecarUploads };
}

function matchingRequests(
  requests: RecordedRequest[],
  pathname: string,
  method?: string,
) {
  return requests.filter(
    (request) =>
      request.pathname === pathname && (!method || request.method === method),
  );
}

test("Phase 5 document views stay canonical, thread-authoritative, and contract-only", async ({
  page,
}) => {
  const mock = await installFullyMockedAgentServer(page);
  await page.goto(
    `/?threadId=${THREAD_A}&sessionView=session-documents&apiUrl=${encodeURIComponent(API_URL)}&assistantId=agent&authScheme=installation`,
  );
  await page.getByRole("button", { name: "Focus visual" }).click();

  const sessionHeading = page.getByRole("heading", {
    name: "Session Documents",
  });
  await expect(sessionHeading).toBeVisible();
  const linkedDocuments = page.getByRole("list", {
    name: "Documents linked to this session",
  });
  await expect(linkedDocuments.getByRole("listitem")).toHaveCount(2);
  await expect(linkedDocuments.getByRole("listitem").nth(0)).toContainText(
    "Canonical installation guide",
  );
  await expect(linkedDocuments.getByRole("listitem").nth(1)).toContainText(
    "Document unavailable",
  );
  await expect(page.getByText(UNAVAILABLE_ID)).toHaveCount(0);
  await expect(page.getByText(FRAGMENT_BODY)).toHaveCount(0);
  await expect(
    page.getByText("STALE CACHED FULL DOCUMENT MUST NEVER RENDER"),
  ).toHaveCount(0);

  const initialThreadAStateReads = mock.stateReads[THREAD_A];
  await page.getByRole("button", { name: "Installation Library" }).click();
  await expect(
    page.getByRole("heading", { name: "Installation Library" }),
  ).toBeVisible();
  await expect(
    page.getByRole("list", { name: "Installation documents" }),
  ).toBeVisible();

  const baselineSearches = matchingRequests(
    mock.requests,
    "/phase5/installation-library",
    "POST",
  ).length;
  await page
    .getByRole("textbox", { name: "Search document content" })
    .fill("bounded semantic phrase");
  await page
    .getByRole("textbox", { name: "Filter by exact tag" })
    .fill(initialTag);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByText("Canonical installation guide")).toBeVisible();

  await expect
    .poll(
      () =>
        matchingRequests(mock.requests, "/phase5/installation-library", "POST")
          .length,
    )
    .toBeGreaterThanOrEqual(baselineSearches + 1);
  const phase5SearchPayloads = matchingRequests(
    mock.requests,
    "/phase5/installation-library",
    "POST",
  ).map((request) => request.body as Record<string, unknown>);
  expect(phase5SearchPayloads).toContainEqual({
    operation: "semantic",
    query: "bounded semantic phrase",
    filters: { tag: initialTag },
    limit: 20,
  });
  const authenticatedSearch = matchingRequests(
    mock.requests,
    "/phase5/installation-library",
    "POST",
  ).at(-1)!;
  expect(authenticatedSearch.headers["x-api-key"]).toBe("phase5-test-key");
  expect(authenticatedSearch.headers["x-auth-scheme"]).toBe("installation");
  await expect(page.getByText(FRAGMENT_BODY)).toHaveCount(0);
  await expect(page.getByText("forged-thread")).toHaveCount(0);

  const librarySearchesBeforeAdd = phase5SearchPayloads.length;
  await page.getByRole("button", { name: "Add to session" }).click();
  await expect
    .poll(
      () =>
        matchingRequests(
          mock.requests,
          `/threads/${THREAD_A}/runs/wait`,
          "POST",
        ).length,
    )
    .toBe(1);
  const addRequest = matchingRequests(
    mock.requests,
    `/threads/${THREAD_A}/runs/wait`,
    "POST",
  )[0];
  expect(addRequest.body).toEqual({
    input: {
      session_document_link_action: {
        action: "add",
        document_id: DOCUMENT_ID,
      },
    },
    assistant_id: "chat_ui",
  });
  expect(
    Object.keys(addRequest.body as Record<string, unknown>).sort(),
  ).toEqual(["assistant_id", "input"]);
  await expect(page.getByText(updatedTag)).toBeVisible();
  expect(
    matchingRequests(mock.requests, "/phase5/installation-library", "POST")
      .length,
  ).toBeGreaterThan(librarySearchesBeforeAdd);

  await page.getByRole("button", { name: "Session Documents" }).click();
  await expect(sessionHeading).toBeVisible();
  await expect(page.getByText(updatedTag)).toBeVisible();
  expect(mock.stateReads[THREAD_A]).toBeGreaterThan(initialThreadAStateReads);

  const unavailableRow = linkedDocuments
    .getByRole("listitem")
    .filter({ hasText: "Document unavailable" });
  await unavailableRow.getByRole("button", { name: "Remove" }).click();
  await expect(unavailableRow).toHaveCount(0);
  const removeRequest = matchingRequests(
    mock.requests,
    `/threads/${THREAD_A}/runs/wait`,
    "POST",
  )[1];
  expect(removeRequest.body).toEqual({
    input: {
      session_document_link_action: {
        action: "remove",
        document_id: UNAVAILABLE_ID,
      },
    },
    assistant_id: "chat_ui",
  });
  expect(
    matchingRequests(mock.requests, `/threads/${THREAD_B}/runs/wait`, "POST"),
  ).toHaveLength(0);

  const libraryReadsBeforeRemoveRefresh = matchingRequests(
    mock.requests,
    "/phase5/installation-library",
    "POST",
  ).length;
  await page.getByRole("button", { name: "Installation Library" }).click();
  await expect(page.getByText(updatedTag)).toBeVisible();
  expect(
    matchingRequests(mock.requests, "/phase5/installation-library", "POST")
      .length,
  ).toBeGreaterThan(libraryReadsBeforeRemoveRefresh);

  await page.getByRole("button", { name: "Session Documents" }).click();
  await page.goto(
    `/?threadId=${THREAD_B}&sessionView=session-documents&apiUrl=${encodeURIComponent(API_URL)}&assistantId=agent&authScheme=installation`,
  );
  await page.getByRole("button", { name: "Focus visual" }).click();
  await expect(sessionHeading).toBeVisible();
  await expect(linkedDocuments.getByRole("listitem")).toHaveCount(1);
  await expect(linkedDocuments.getByRole("listitem")).toContainText(
    "Canonical installation guide",
  );
  await expect(page.getByText(updatedTag)).toBeVisible();
  expect(mock.stateReads[THREAD_B]).toBeGreaterThan(0);

  const mutationsBeforeReopen = matchingRequests(
    mock.requests,
    `/threads/${THREAD_B}/runs/wait`,
    "POST",
  ).length;
  const threadBReadsBeforeReopen = mock.stateReads[THREAD_B];
  await page.reload();
  await page.getByRole("button", { name: "Focus visual" }).click();
  await expect(sessionHeading).toBeVisible();
  await expect(linkedDocuments.getByRole("listitem")).toHaveCount(1);
  expect(mock.stateReads[THREAD_B]).toBeGreaterThan(threadBReadsBeforeReopen);
  expect(
    matchingRequests(mock.requests, `/threads/${THREAD_B}/runs/wait`, "POST"),
  ).toHaveLength(mutationsBeforeReopen);

  await page.getByRole("button", { name: "Sources" }).click();
  await expect(
    page.getByRole("heading", { name: "Session sources" }),
  ).toBeVisible();
  await expect(
    page.getByRole("list", { name: "Saved session sources" }),
  ).toContainText("Separate Librarian source");
  await expect(sessionHeading).toHaveCount(0);
  const sourceSearch = matchingRequests(
    mock.requests,
    "/store/items/search",
    "POST",
  )
    .map((request) => request.body as { namespace_prefix?: string[] })
    .find((payload) => payload.namespace_prefix?.[1] === "session-sources");
  expect(sourceSearch?.namespace_prefix).toEqual([
    "local-owner-v1",
    "session-sources",
    THREAD_B,
  ]);

  // Every mutation remained a runs/wait request with the exact ID-only action;
  // forged fragment/metadata fields and thread switches generated none.
  const allMutationRuns = mock.requests.filter((request) =>
    /^\/threads\/[^/]+\/runs\/wait$/.test(request.pathname),
  );
  expect(allMutationRuns).toHaveLength(2);
  expect(
    matchingRequests(mock.requests, "/store/items/search", "POST").filter(
      (request) => {
        const namespace = (request.body as { namespace_prefix?: string[] })
          .namespace_prefix;
        return namespace?.[1] === "documents" || namespace?.[1] === "fragments";
      },
    ),
  ).toHaveLength(0);
  expect(
    mock.requests.filter(
      (request) =>
        request.method !== "GET" &&
        request.pathname.startsWith("/store/") &&
        request.pathname !== "/store/items/search",
    ),
  ).toHaveLength(0);
});

test("owner upload uses the sidecar then the authenticated ingestion route and invalidates both views", async ({
  page,
}) => {
  const mock = await installFullyMockedAgentServer(page);
  await page.goto(
    `/?threadId=${THREAD_A}&sessionView=session-documents&apiUrl=${encodeURIComponent(API_URL)}&assistantId=agent&authScheme=installation`,
  );
  await page.getByRole("button", { name: "Focus visual" }).click();
  await expect(
    page.getByRole("heading", { name: "Session Documents" }),
  ).toBeVisible();
  const stateReadsBefore = mock.stateReads[THREAD_A];

  await page.getByRole("button", { name: "Installation Library" }).click();
  await expect(
    page.getByRole("heading", { name: "Installation Library" }),
  ).toBeVisible();
  const libraryReadsBefore = matchingRequests(
    mock.requests,
    "/phase5/installation-library",
    "POST",
  ).length;

  await page.getByLabel("Choose a document or book").setInputFiles({
    name: "owner-book.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("synthetic unchanged browser fixture"),
  });
  await page
    .getByRole("textbox", { name: "Canonical document title" })
    .fill("Owner book");
  await page
    .getByRole("textbox", { name: "Canonical document tags" })
    .fill("Guide, Owner");
  await page.getByRole("button", { name: "Ingest document" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Ingested document owner-upload-document in 7 fragment(s)",
  );

  expect(mock.sidecarUploads()).toBe(1);
  const ingestionRequests = matchingRequests(
    mock.requests,
    "/phase5/owner-upload",
    "POST",
  );
  expect(ingestionRequests).toHaveLength(1);
  expect(ingestionRequests[0].body).toEqual({
    upload_reference: `upload:${"a".repeat(32)}-owner-book.pdf`,
    filename: "owner-book.pdf",
    title: "Owner book",
    tags: ["Guide", "Owner"],
  });
  expect(ingestionRequests[0].headers["x-api-key"]).toBe("phase5-test-key");
  expect(ingestionRequests[0].headers["x-auth-scheme"]).toBe("installation");
  expect(matchingRequests(mock.requests, "/runs/wait", "POST")).toHaveLength(0);
  expect(
    matchingRequests(mock.requests, "/phase5/installation-library", "POST")
      .length,
  ).toBeGreaterThan(libraryReadsBefore);
  expect(
    mock.requests.filter((request) =>
      /^\/threads\/[^/]+\/runs\/wait$/.test(request.pathname),
    ),
  ).toHaveLength(0);

  await page.getByRole("button", { name: "Session Documents" }).click();
  await expect(
    page.getByRole("heading", { name: "Session Documents" }),
  ).toBeVisible();
  expect(mock.stateReads[THREAD_A]).toBeGreaterThan(stateReadsBefore);
  expect(
    mock.requests.filter(
      (request) =>
        request.method !== "GET" && request.pathname.startsWith("/store/"),
    ),
  ).toHaveLength(0);
});

test("public URL ingestion uses only the authenticated custom route and does not link the thread", async ({
  page,
}) => {
  const mock = await installFullyMockedAgentServer(page);
  await page.goto(
    `/?threadId=${THREAD_A}&sessionView=installation-documents&apiUrl=${encodeURIComponent(API_URL)}&assistantId=agent&authScheme=installation`,
  );
  await page.getByRole("button", { name: "Focus visual" }).click();
  await expect(
    page.getByRole("heading", { name: "Installation Library" }),
  ).toBeVisible();
  const libraryReadsBefore = matchingRequests(
    mock.requests,
    "/phase5/installation-library",
    "POST",
  ).length;
  const stateReadsBefore = mock.stateReads[THREAD_A];

  await page
    .getByRole("textbox", { name: "Public document URL" })
    .fill("https://public.example/guide.pdf?edition=1");
  await page
    .getByRole("textbox", { name: "Public document title" })
    .fill("Public guide");
  await page
    .getByRole("textbox", { name: "Public document tags" })
    .fill("Public, Guide");
  await page.getByRole("button", { name: "Ingest public URL" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Ingested public document public-document-content-digest in 5 fragment(s)",
  );

  const requests = matchingRequests(
    mock.requests,
    "/phase5/public-document",
    "POST",
  );
  expect(requests).toHaveLength(1);
  expect(requests[0].body).toEqual({
    url: "https://public.example/guide.pdf?edition=1",
    title: "Public guide",
    tags: ["Public", "Guide"],
  });
  expect(requests[0].headers["x-api-key"]).toBe("phase5-test-key");
  expect(requests[0].headers["x-auth-scheme"]).toBe("installation");
  expect(mock.sidecarUploads()).toBe(0);
  expect(
    mock.requests.filter((request) =>
      /^\/threads\/[^/]+\/runs\/wait$/.test(request.pathname),
    ),
  ).toHaveLength(0);
  expect(
    matchingRequests(mock.requests, "/phase5/installation-library", "POST")
      .length,
  ).toBeGreaterThan(libraryReadsBefore);

  await page.getByRole("button", { name: "Session Documents" }).click();
  await expect(
    page.getByRole("heading", { name: "Session Documents" }),
  ).toBeVisible();
  expect(mock.stateReads[THREAD_A]).toBeGreaterThan(stateReadsBefore);
});
