import { ContentBlock } from "@langchain/core/messages";
import { toast } from "sonner";

const EPUB_MIME_TYPE = "application/epub+zip";

export function isEpubFile(file: File): boolean {
  return (
    file.type === EPUB_MIME_TYPE ||
    file.name.toLocaleLowerCase().endsWith(".epub")
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

  if (isEpubFile(file)) {
    const body = new FormData();
    body.append("publication", file, file.name);
    const response = await fetch("http://127.0.0.1:8000/api/attachments/epub", {
      method: "POST",
      body,
    });
    const result = (await response.json()) as {
      detail?: string;
      filename?: string;
      title?: string;
      author?: string;
      text?: string;
      chapters?: Array<{ index: number; source: string; characters: number }>;
      truncated?: boolean;
      content_profile?: Record<string, unknown>;
    };
    if (!response.ok) {
      const message = result.detail || "The EPUB could not be read safely.";
      toast.error(message);
      throw new Error(message);
    }
    const title = result.title || file.name;
    const author = result.author ? ` by ${result.author}` : "";
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
      context: `Selected EPUB ${title}${author}.${limitation}`,
      mimeType: "text/markdown",
      metadata: {
        filename: result.filename || file.name,
        originalMimeType: EPUB_MIME_TYPE,
        chapters: result.chapters || [],
        truncated: Boolean(result.truncated),
        contentProfile: result.content_profile || {},
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
