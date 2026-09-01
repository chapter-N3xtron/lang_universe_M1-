"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ExternalLink,
  FileText,
  Library,
  Link2Off,
  Plus,
  Upload,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getApiKey } from "@/lib/api-key";
import {
  DOCUMENT_ACCEPT,
  isExtractableDocumentFile,
} from "@/lib/multimodal-utils";
import { createClient } from "@/providers/client";
import { useStreamContext } from "@/providers/Stream";

const LIBRARY_QUERY_KEY = "installation-document-library";
const SESSION_DOCUMENTS_QUERY_KEY = "session-documents";
const SEARCH_LIMIT = 20;
const MAX_QUERY_BYTES = 4096;
const MAX_TAG_BYTES = 1024;
const MAX_INGESTION_TAGS = 32;
const MAX_INGESTION_TAG_BYTES = 128;
const MAX_PUBLIC_URL_BYTES = 4096;

type CanonicalDocument = {
  id: string;
  title: string;
  tags: string[];
  sourceUri: string;
  sourceType: string;
  sourceRevision: string;
};

type SessionDocument =
  | { available: true; document: CanonicalDocument }
  | { available: false; documentId: string };

type LibraryOperation =
  | { operation: "resolve"; document_ids: string[]; limit: number }
  | {
      operation: "metadata";
      filters?: { tag: string };
      limit: number;
    }
  | {
      operation: "semantic";
      query: string;
      filters?: { tag: string };
      limit: number;
    };

function credentialDiscriminator(credential: string) {
  let hash = 2166136261;
  for (let index = 0; index < credential.length; index += 1) {
    hash ^= credential.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `auth-${(hash >>> 0).toString(16).padStart(8, "0")}`;
}

function readCanonicalDocument(
  value: Record<string, unknown>,
): CanonicalDocument | null {
  if (
    value.record_type !== "document" ||
    value.source_status !== "active" ||
    typeof value.id !== "string" ||
    typeof value.title !== "string" ||
    !Array.isArray(value.tags) ||
    !value.tags.every((tag) => typeof tag === "string")
  ) {
    return null;
  }

  return {
    id: value.id,
    title: value.title,
    tags: value.tags,
    sourceUri:
      typeof value.source_uri === "string" ? value.source_uri : "unknown",
    sourceType:
      typeof value.source_type === "string" ? value.source_type : "unknown",
    sourceRevision:
      typeof value.source_revision === "string"
        ? value.source_revision
        : "unknown",
  };
}

function validSourceUrl(sourceUri: string) {
  try {
    const url = new URL(sourceUri);
    return url.protocol === "https:" || url.protocol === "http:"
      ? url.href
      : null;
  } catch {
    return null;
  }
}

function DocumentMetadata({ document }: { document: CanonicalDocument }) {
  const sourceUrl = validSourceUrl(document.sourceUri);
  return (
    <div className="min-w-0 flex-1">
      <h3 className="truncate text-sm font-semibold">{document.title}</h3>
      <div
        className="mt-2 flex flex-wrap gap-1"
        aria-label="Document tags"
      >
        {document.tags.length ? (
          document.tags.map((tag) => (
            <span
              key={tag}
              className="bg-secondary rounded px-2 py-0.5 text-xs"
            >
              {tag}
            </span>
          ))
        ) : (
          <span className="text-muted-foreground text-xs">No tags</span>
        )}
      </div>
      <p className="text-muted-foreground mt-2 text-xs">
        {document.sourceType.replaceAll("_", " ")} · revision{" "}
        {document.sourceRevision}
      </p>
      <p className="text-muted-foreground mt-1 truncate text-xs">
        {sourceUrl ? (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noreferrer"
            className="text-primary inline-flex max-w-full items-center gap-1 underline"
          >
            <span className="truncate">{document.sourceUri}</span>
            <ExternalLink
              className="size-3 shrink-0"
              aria-hidden="true"
            />
          </a>
        ) : (
          <>Source: {document.sourceUri}</>
        )}
      </p>
    </div>
  );
}

export function SessionDocuments({
  apiUrl,
  authScheme,
  threadId,
  view,
}: {
  apiUrl: string;
  authScheme?: string;
  threadId: string | null;
  view: "installation-documents" | "session-documents";
}) {
  const queryClient = useQueryClient();
  const stream = useStreamContext();
  const apiKey = getApiKey() ?? "";
  const authContext = credentialDiscriminator(
    `${authScheme ?? ""}\u0000${apiKey}`,
  );
  const client = useMemo(
    () => createClient(apiUrl, apiKey || undefined, authScheme),
    [apiKey, apiUrl, authScheme],
  );
  const [contentDraft, setContentDraft] = useState("");
  const [tagDraft, setTagDraft] = useState("");
  const [search, setSearch] = useState({ content: "", tag: "" });
  const [validationError, setValidationError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [ingestionTitle, setIngestionTitle] = useState("");
  const [ingestionTags, setIngestionTags] = useState("");
  const [publicUrl, setPublicUrl] = useState("");
  const [publicTitle, setPublicTitle] = useState("");
  const [publicTags, setPublicTags] = useState("");

  function phase5Headers() {
    const headers = new Headers({ "Content-Type": "application/json" });
    if (apiKey) headers.set("X-Api-Key", apiKey);
    if (authScheme) headers.set("X-Auth-Scheme", authScheme);
    return headers;
  }

  async function runLibraryOperation(operation: LibraryOperation) {
    const response = await fetch(
      `${apiUrl.replace(/\/$/, "")}/phase5/installation-library`,
      {
        method: "POST",
        headers: phase5Headers(),
        body: JSON.stringify(operation),
      },
    );
    const result = (await response.json()) as Record<string, unknown>;
    if (
      !response.ok ||
      result.ok !== true ||
      !Array.isArray(result.documents)
    ) {
      throw new Error("Installation Library read failed.");
    }
    return result.documents.flatMap((value) => {
      const document =
        value && typeof value === "object"
          ? readCanonicalDocument(value as Record<string, unknown>)
          : null;
      return document ? [document] : [];
    });
  }

  const libraryQuery = useQuery({
    queryKey: [LIBRARY_QUERY_KEY, apiUrl, authContext, search],
    queryFn: () =>
      runLibraryOperation(
        search.content
          ? {
              operation: "semantic",
              query: search.content,
              ...(search.tag ? { filters: { tag: search.tag } } : {}),
              limit: SEARCH_LIMIT,
            }
          : {
              operation: "metadata",
              ...(search.tag ? { filters: { tag: search.tag } } : {}),
              limit: SEARCH_LIMIT,
            },
      ),
    enabled: Boolean(apiUrl && view === "installation-documents"),
  });

  const sessionDocumentsQuery = useQuery({
    queryKey: [SESSION_DOCUMENTS_QUERY_KEY, apiUrl, authContext, threadId],
    queryFn: async (): Promise<SessionDocument[]> => {
      const state = await client.threads.getState<Record<string, unknown>>(
        threadId!,
      );
      const stateIds = state.values.session_document_ids;
      const ids = stateIds === undefined ? [] : stateIds;
      if (
        !Array.isArray(ids) ||
        !ids.every((id) => typeof id === "string") ||
        new Set(ids).size !== ids.length ||
        ids.length > 100
      ) {
        throw new Error("Invalid authoritative session document state.");
      }
      const documentIds = ids as string[];
      const batches = [];
      for (
        let offset = 0;
        offset < documentIds.length;
        offset += SEARCH_LIMIT
      ) {
        batches.push(documentIds.slice(offset, offset + SEARCH_LIMIT));
      }
      const resolved = (
        await Promise.all(
          batches.map((document_ids) =>
            runLibraryOperation({
              operation: "resolve",
              document_ids,
              limit: document_ids.length,
            }),
          ),
        )
      ).flat();
      const documents = new Map(
        resolved.map((document) => [document.id, document]),
      );
      return documentIds.map((documentId) => {
        const document = documents.get(documentId);
        return document
          ? { available: true, document }
          : { available: false, documentId };
      });
    },
    enabled: Boolean(apiUrl && threadId && view === "session-documents"),
  });

  const ingestionMutation = useMutation({
    mutationFn: async ({
      file,
      title,
      tags,
    }: {
      file: File;
      title: string;
      tags: string[];
    }) => {
      const body = new FormData();
      body.append("document", file, file.name);
      const uploadResponse = await fetch(
        "http://127.0.0.1:8000/api/attachments/document",
        { method: "POST", body },
      );
      const upload = (await uploadResponse.json()) as {
        ocr_upload?: { reference?: string; filename?: string };
      };
      const uploadReference = upload.ocr_upload?.reference;
      const preservedFilename = upload.ocr_upload?.filename;
      if (
        !uploadResponse.ok ||
        typeof uploadReference !== "string" ||
        preservedFilename !== file.name
      ) {
        throw new Error("The selected document could not be preserved.");
      }

      const ingestionResponse = await fetch(
        `${apiUrl.replace(/\/$/, "")}/phase5/owner-upload`,
        {
          method: "POST",
          headers: phase5Headers(),
          body: JSON.stringify({
            upload_reference: uploadReference,
            filename: file.name,
            title,
            ...(tags.length ? { tags } : {}),
          }),
        },
      );
      const result = (await ingestionResponse.json()) as Record<
        string,
        unknown
      >;
      if (
        !ingestionResponse.ok ||
        result.ok !== true ||
        !("document_id" in result) ||
        typeof result.document_id !== "string" ||
        !("fragment_count" in result) ||
        typeof result.fragment_count !== "number"
      ) {
        throw new Error("The selected document could not be ingested.");
      }
      return {
        documentId: result.document_id,
        fragmentCount: result.fragment_count,
      };
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: [LIBRARY_QUERY_KEY] }),
        queryClient.invalidateQueries({
          queryKey: [SESSION_DOCUMENTS_QUERY_KEY],
        }),
      ]);
    },
  });

  const publicIngestionMutation = useMutation({
    mutationFn: async ({
      url,
      title,
      tags,
    }: {
      url: string;
      title: string;
      tags: string[];
    }) => {
      const response = await fetch(
        `${apiUrl.replace(/\/$/, "")}/phase5/public-document`,
        {
          method: "POST",
          headers: phase5Headers(),
          body: JSON.stringify({
            url,
            title,
            ...(tags.length ? { tags } : {}),
          }),
        },
      );
      const result = (await response.json()) as Record<string, unknown>;
      if (
        !response.ok ||
        result.ok !== true ||
        typeof result.document_id !== "string" ||
        typeof result.fragment_count !== "number"
      ) {
        throw new Error("The public document could not be ingested.");
      }
      return {
        documentId: result.document_id,
        fragmentCount: result.fragment_count,
      };
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: [LIBRARY_QUERY_KEY] }),
        queryClient.invalidateQueries({
          queryKey: [SESSION_DOCUMENTS_QUERY_KEY],
        }),
      ]);
    },
  });

  const linkMutation = useMutation({
    mutationFn: async ({
      action,
      documentId,
    }: {
      action: "add" | "remove";
      documentId: string;
    }) => {
      if (!threadId) throw new Error("A current session is required.");
      const result = (await client.runs.wait(threadId, "chat_ui", {
        input: {
          session_document_link_action: {
            action,
            document_id: documentId,
          },
        },
      })) as Record<string, unknown>;
      const mutationResult = result.session_document_link_result;
      if (
        !mutationResult ||
        typeof mutationResult !== "object" ||
        !("ok" in mutationResult) ||
        mutationResult.ok !== true
      ) {
        throw new Error("The session document link was not changed.");
      }
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: [LIBRARY_QUERY_KEY] }),
        queryClient.invalidateQueries({
          queryKey: [SESSION_DOCUMENTS_QUERY_KEY],
        }),
      ]);
    },
  });

  const streamedDocumentIds = (
    stream.values as Record<string, unknown> | undefined
  )?.session_document_ids;
  const streamProjection = Array.isArray(streamedDocumentIds)
    ? streamedDocumentIds.join("\u0000")
    : "";
  const previousStreamProjection = useRef(streamProjection);
  useEffect(() => {
    if (previousStreamProjection.current === streamProjection) return;
    previousStreamProjection.current = streamProjection;
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: [LIBRARY_QUERY_KEY] }),
      queryClient.invalidateQueries({
        queryKey: [SESSION_DOCUMENTS_QUERY_KEY],
      }),
    ]);
  }, [queryClient, streamProjection]);

  function submitIngestion(event: FormEvent) {
    event.preventDefault();
    const title = ingestionTitle.trim();
    const tags = ingestionTags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
    if (!selectedFile || !isExtractableDocumentFile(selectedFile)) {
      setValidationError("Choose a supported document or book file.");
      return;
    }
    if (!title || new TextEncoder().encode(title).length > 512) {
      setValidationError("Document title must be between 1 and 512 bytes.");
      return;
    }
    if (
      tags.length > MAX_INGESTION_TAGS ||
      tags.some(
        (tag) => new TextEncoder().encode(tag).length > MAX_INGESTION_TAG_BYTES,
      )
    ) {
      setValidationError("Use at most 32 tags of 128 bytes each.");
      return;
    }
    setValidationError(null);
    ingestionMutation.mutate({ file: selectedFile, title, tags });
  }

  function submitPublicIngestion(event: FormEvent) {
    event.preventDefault();
    const url = publicUrl.trim();
    const title = publicTitle.trim();
    const tags = publicTags
      .split(",")
      .map((tag) => tag.trim())
      .filter(Boolean);
    let parsedUrl: URL;
    try {
      parsedUrl = new URL(url);
    } catch {
      setValidationError("Enter a valid public HTTPS URL.");
      return;
    }
    if (
      parsedUrl.protocol !== "https:" ||
      new TextEncoder().encode(url).length > MAX_PUBLIC_URL_BYTES
    ) {
      setValidationError("Enter a public HTTPS URL of 4 KiB or less.");
      return;
    }
    if (!title || new TextEncoder().encode(title).length > 512) {
      setValidationError("Document title must be between 1 and 512 bytes.");
      return;
    }
    if (
      tags.length > MAX_INGESTION_TAGS ||
      tags.some(
        (tag) => new TextEncoder().encode(tag).length > MAX_INGESTION_TAG_BYTES,
      )
    ) {
      setValidationError("Use at most 32 tags of 128 bytes each.");
      return;
    }
    setValidationError(null);
    publicIngestionMutation.mutate({ url, title, tags });
  }

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    const content = contentDraft.trim();
    const tag = tagDraft.trim();
    if (new TextEncoder().encode(content).length > MAX_QUERY_BYTES) {
      setValidationError("Content search must be 4 KiB or less.");
      return;
    }
    if (new TextEncoder().encode(tag).length > MAX_TAG_BYTES) {
      setValidationError("Tag filter must be 1 KiB or less.");
      return;
    }
    setValidationError(null);
    setSearch({ content, tag });
  }

  if (view === "installation-documents") {
    const documents = libraryQuery.data ?? [];
    return (
      <section
        className="flex h-full min-w-0 flex-col overflow-hidden"
        aria-labelledby="installation-library-title"
      >
        <div className="shrink-0 border-b p-4">
          <h2
            id="installation-library-title"
            className="font-semibold"
          >
            Installation Library
          </h2>
          <p className="text-muted-foreground mt-1 text-sm">
            Canonical installation documents. Content search returns document
            metadata only.
          </p>
          <form
            className="bg-muted/20 mt-4 grid gap-2 rounded-md border p-3 sm:grid-cols-2"
            onSubmit={submitIngestion}
          >
            <label className="text-sm font-medium sm:col-span-2">
              Choose a document or book
              <input
                className="mt-1 block w-full text-sm"
                type="file"
                accept={DOCUMENT_ACCEPT}
                disabled={ingestionMutation.isPending}
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  setSelectedFile(file);
                  if (file) setIngestionTitle(file.name);
                  ingestionMutation.reset();
                }}
              />
            </label>
            <Input
              aria-label="Canonical document title"
              placeholder="Document title"
              value={ingestionTitle}
              disabled={ingestionMutation.isPending}
              onChange={(event) => setIngestionTitle(event.target.value)}
            />
            <Input
              aria-label="Canonical document tags"
              placeholder="Optional tags, comma separated"
              value={ingestionTags}
              disabled={ingestionMutation.isPending}
              onChange={(event) => setIngestionTags(event.target.value)}
            />
            <Button
              type="submit"
              disabled={ingestionMutation.isPending || !selectedFile}
              className="sm:col-span-2 sm:justify-self-start"
            >
              <Upload
                className="size-4"
                aria-hidden="true"
              />
              {ingestionMutation.isPending
                ? "Ingesting document…"
                : "Ingest document"}
            </Button>
            {ingestionMutation.isPending && (
              <p
                role="status"
                className="text-muted-foreground text-sm sm:col-span-2"
              >
                Preserving, reading, and indexing the selected document…
              </p>
            )}
            {ingestionMutation.isSuccess && (
              <p
                role="status"
                className="text-sm sm:col-span-2"
              >
                Ingested document {ingestionMutation.data.documentId} in{" "}
                {ingestionMutation.data.fragmentCount} fragment(s). Use Add to
                session when you want to link it.
              </p>
            )}
            {ingestionMutation.isError && (
              <p
                role="alert"
                className="text-destructive text-sm sm:col-span-2"
              >
                The selected document could not be ingested.
              </p>
            )}
          </form>
          <form
            className="bg-muted/20 mt-3 grid gap-2 rounded-md border p-3 sm:grid-cols-2"
            onSubmit={submitPublicIngestion}
          >
            <Input
              className="sm:col-span-2"
              aria-label="Public document URL"
              type="url"
              placeholder="https://public.example/document.pdf"
              value={publicUrl}
              disabled={publicIngestionMutation.isPending}
              onChange={(event) => {
                setPublicUrl(event.target.value);
                publicIngestionMutation.reset();
              }}
            />
            <Input
              aria-label="Public document title"
              placeholder="Document title"
              value={publicTitle}
              disabled={publicIngestionMutation.isPending}
              onChange={(event) => setPublicTitle(event.target.value)}
            />
            <Input
              aria-label="Public document tags"
              placeholder="Optional tags, comma separated"
              value={publicTags}
              disabled={publicIngestionMutation.isPending}
              onChange={(event) => setPublicTags(event.target.value)}
            />
            <Button
              type="submit"
              disabled={publicIngestionMutation.isPending || !publicUrl.trim()}
              className="sm:col-span-2 sm:justify-self-start"
            >
              <ExternalLink
                className="size-4"
                aria-hidden="true"
              />
              {publicIngestionMutation.isPending
                ? "Ingesting public document…"
                : "Ingest public URL"}
            </Button>
            {publicIngestionMutation.isPending && (
              <p
                role="status"
                className="text-muted-foreground text-sm sm:col-span-2"
              >
                Securely downloading, reading, and indexing the public document…
              </p>
            )}
            {publicIngestionMutation.isSuccess && (
              <p
                role="status"
                className="text-sm sm:col-span-2"
              >
                Ingested public document{" "}
                {publicIngestionMutation.data.documentId} in{" "}
                {publicIngestionMutation.data.fragmentCount} fragment(s). Use
                Add to session when you want to link it.
              </p>
            )}
            {publicIngestionMutation.isError && (
              <p
                role="alert"
                className="text-destructive text-sm sm:col-span-2"
              >
                The public document could not be ingested.
              </p>
            )}
          </form>
          <form
            className="mt-4 grid gap-2 sm:grid-cols-[1fr_12rem_auto]"
            onSubmit={submitSearch}
          >
            <Input
              aria-label="Search document content"
              placeholder="Search document content"
              value={contentDraft}
              onChange={(event) => setContentDraft(event.target.value)}
            />
            <Input
              aria-label="Filter by exact tag"
              placeholder="Exact tag"
              value={tagDraft}
              onChange={(event) => setTagDraft(event.target.value)}
            />
            <Button
              type="submit"
              disabled={libraryQuery.isFetching}
            >
              Search
            </Button>
          </form>
          {validationError && (
            <p
              role="alert"
              className="text-destructive mt-2 text-sm"
            >
              {validationError}
            </p>
          )}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {libraryQuery.isLoading ? (
            <p
              role="status"
              className="text-muted-foreground text-sm"
            >
              Loading Installation Library…
            </p>
          ) : libraryQuery.error ? (
            <p
              role="alert"
              className="text-destructive text-sm"
            >
              Installation Library could not be loaded.
            </p>
          ) : documents.length === 0 ? (
            <div className="text-muted-foreground rounded-lg border border-dashed p-8 text-center text-sm">
              No available documents match this view.
            </div>
          ) : (
            <ul
              className="space-y-2"
              aria-label="Installation documents"
            >
              {documents.map((document) => (
                <li
                  key={document.id}
                  className="bg-muted/20 flex items-start gap-3 rounded-lg border p-3"
                >
                  <FileText
                    className="text-muted-foreground mt-0.5 size-4 shrink-0"
                    aria-hidden="true"
                  />
                  <DocumentMetadata document={document} />
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!threadId || linkMutation.isPending}
                    onClick={() =>
                      linkMutation.mutate({
                        action: "add",
                        documentId: document.id,
                      })
                    }
                    title={
                      threadId
                        ? "Add to current session"
                        : "Open a session to add this document"
                    }
                  >
                    <Plus
                      className="size-4"
                      aria-hidden="true"
                    />{" "}
                    Add to session
                  </Button>
                </li>
              ))}
            </ul>
          )}
          {!threadId && (
            <p
              className="text-muted-foreground mt-3 text-sm"
              role="note"
            >
              Open a session to add a document.
            </p>
          )}
          {linkMutation.error && (
            <p
              role="alert"
              className="text-destructive mt-3 text-sm"
            >
              The document could not be added to this session.
            </p>
          )}
        </div>
      </section>
    );
  }

  const sessionDocuments = sessionDocumentsQuery.data ?? [];
  return (
    <section
      className="flex h-full min-w-0 flex-col overflow-hidden"
      aria-labelledby="session-documents-title"
    >
      <div className="shrink-0 border-b p-4">
        <h2
          id="session-documents-title"
          className="font-semibold"
        >
          Session Documents
        </h2>
        <p className="text-muted-foreground mt-1 text-sm">
          Documents linked to the current session, resolved from the canonical
          library.
        </p>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {!threadId ? (
          <div className="text-muted-foreground rounded-lg border border-dashed p-8 text-center text-sm">
            Open a session to view its documents.
          </div>
        ) : sessionDocumentsQuery.isLoading ? (
          <p
            role="status"
            className="text-muted-foreground text-sm"
          >
            Loading Session Documents…
          </p>
        ) : sessionDocumentsQuery.error ? (
          <p
            role="alert"
            className="text-destructive text-sm"
          >
            Session Documents could not be loaded.
          </p>
        ) : sessionDocuments.length === 0 ? (
          <div className="text-muted-foreground rounded-lg border border-dashed p-8 text-center text-sm">
            No documents are linked to this session.
          </div>
        ) : (
          <ol
            className="space-y-2"
            aria-label="Documents linked to this session"
          >
            {sessionDocuments.map((entry, index) => (
              <li
                key={
                  entry.available ? entry.document.id : `unavailable-${index}`
                }
                className="bg-muted/20 flex items-start gap-3 rounded-lg border p-3"
              >
                {entry.available ? (
                  <>
                    <FileText
                      className="text-muted-foreground mt-0.5 size-4 shrink-0"
                      aria-hidden="true"
                    />
                    <DocumentMetadata document={entry.document} />
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={linkMutation.isPending}
                      onClick={() =>
                        linkMutation.mutate({
                          action: "remove",
                          documentId: entry.document.id,
                        })
                      }
                    >
                      <Link2Off
                        className="size-4"
                        aria-hidden="true"
                      />{" "}
                      Remove
                    </Button>
                  </>
                ) : (
                  <>
                    <div className="text-muted-foreground flex flex-1 items-center gap-2 text-sm">
                      <Library
                        className="size-4"
                        aria-hidden="true"
                      />{" "}
                      Document unavailable
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={linkMutation.isPending}
                      onClick={() =>
                        linkMutation.mutate({
                          action: "remove",
                          documentId: entry.documentId,
                        })
                      }
                    >
                      <Link2Off
                        className="size-4"
                        aria-hidden="true"
                      />{" "}
                      Remove
                    </Button>
                  </>
                )}
              </li>
            ))}
          </ol>
        )}
        {linkMutation.error && (
          <p
            role="alert"
            className="text-destructive mt-3 text-sm"
          >
            The session document link could not be changed.
          </p>
        )}
      </div>
    </section>
  );
}
