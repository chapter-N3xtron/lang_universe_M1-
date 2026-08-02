import { ContentBlock } from "@langchain/core/messages";
import { toast } from "sonner";

export const EXTRACTABLE_DOCUMENT_EXTENSIONS = [
  ".txt",
  ".text",
  ".md",
  ".markdown",
  ".mdx",
  ".rst",
  ".adoc",
  ".asciidoc",
  ".tex",
  ".bib",
  ".csv",
  ".tsv",
  ".json",
  ".jsonl",
  ".ndjson",
  ".yaml",
  ".yml",
  ".toml",
  ".ini",
  ".cfg",
  ".conf",
  ".log",
  ".sql",
  ".graphql",
  ".gql",
  ".py",
  ".pyi",
  ".js",
  ".jsx",
  ".mjs",
  ".cjs",
  ".ts",
  ".tsx",
  ".java",
  ".kt",
  ".kts",
  ".go",
  ".rs",
  ".rb",
  ".php",
  ".swift",
  ".scala",
  ".sh",
  ".bash",
  ".zsh",
  ".fish",
  ".ps1",
  ".bat",
  ".cmd",
  ".c",
  ".h",
  ".cc",
  ".cpp",
  ".hpp",
  ".cs",
  ".dart",
  ".lua",
  ".r",
  ".jl",
  ".ex",
  ".exs",
  ".erl",
  ".hrl",
  ".clj",
  ".cljs",
  ".vue",
  ".svelte",
  ".vtt",
  ".srt",
  ".pdf",
  ".docx",
  ".xlsx",
  ".pptx",
  ".odt",
  ".ods",
  ".odp",
  ".rtf",
  ".html",
  ".htm",
  ".xhtml",
  ".xml",
  ".eml",
  ".ipynb",
  ".epub",
] as const;

export const DOCUMENT_ACCEPT = EXTRACTABLE_DOCUMENT_EXTENSIONS.join(",");

export function isExtractableDocumentFile(file: File): boolean {
  const name = file.name.toLocaleLowerCase();
  return EXTRACTABLE_DOCUMENT_EXTENSIONS.some((extension) =>
    name.endsWith(extension),
  );
}

// Returns a Promise of a typed multimodal block for images or PDFs
export async function fileToContentBlock(
  file: File,
): Promise<ContentBlock.Multimodal.Data> {
  const supportedImageTypes = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
  ];
  const supportedFileTypes = [...supportedImageTypes, "application/pdf"];

  if (isExtractableDocumentFile(file)) {
    const body = new FormData();
    body.append("document", file, file.name);
    const response = await fetch(
      "http://127.0.0.1:8000/api/attachments/document",
      { method: "POST", body },
    );
    const result = (await response.json()) as {
      detail?: string;
      filename?: string;
      format?: string;
      text?: string;
      segments?: Array<Record<string, unknown>>;
      truncated?: boolean;
    };
    if (!response.ok) {
      const message = result.detail || "The document could not be read safely.";
      toast.error(message);
      throw new Error(message);
    }
    const title = result.filename || file.name;
    const limitation = result.truncated
      ? " The extracted text was truncated at the attachment safety limit."
      : "";
    // LangChain's documented PlainText block uses `text` without a second
    // base64 copy. The installed declaration still inherits a DataRecord
    // requirement, so keep the standards-compliant runtime shape explicit.
    return {
      type: "text-plain",
      text: result.text || "",
      title,
      context: `Selected ${result.format || "document"} file ${title}.${limitation}`,
      mimeType: "text/markdown",
      metadata: {
        filename: result.filename || file.name,
        originalMimeType: file.type || "application/octet-stream",
        format: result.format || "document",
        segments: result.segments || [],
        truncated: Boolean(result.truncated),
      },
    } as unknown as ContentBlock.Multimodal.PlainText;
  }

  if (!supportedFileTypes.includes(file.type)) {
    toast.error(
      `Unsupported file type: ${file.type}. Supported types are: ${supportedFileTypes.join(", ")}`,
    );
    return Promise.reject(new Error(`Unsupported file type: ${file.type}`));
  }

  const data = await fileToBase64(file);

  if (supportedImageTypes.includes(file.type)) {
    return {
      type: "image",
      mimeType: file.type,
      data,
      metadata: { name: file.name },
    };
  }

  // PDF
  return {
    type: "file",
    mimeType: "application/pdf",
    data,
    metadata: { filename: file.name },
  };
}

// Helper to convert File to base64 string
export async function fileToBase64(file: File): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      // Remove the data:...;base64, prefix
      resolve(result.split(",")[1]);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

// Type guard for Base64ContentBlock
export function isBase64ContentBlock(
  block: unknown,
): block is ContentBlock.Multimodal.Data {
  if (typeof block !== "object" || block === null || !("type" in block))
    return false;
  // file type (legacy)
  if (
    (block as { type: unknown }).type === "file" &&
    "mimeType" in block &&
    typeof (block as { mimeType?: unknown }).mimeType === "string" &&
    ((block as { mimeType: string }).mimeType.startsWith("image/") ||
      (block as { mimeType: string }).mimeType === "application/pdf")
  ) {
    return true;
  }
  // image type (new)
  if (
    (block as { type: unknown }).type === "image" &&
    "mimeType" in block &&
    typeof (block as { mimeType?: unknown }).mimeType === "string" &&
    (block as { mimeType: string }).mimeType.startsWith("image/")
  ) {
    return true;
  }
  return false;
}
