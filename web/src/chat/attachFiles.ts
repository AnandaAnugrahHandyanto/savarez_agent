import type { GatewayClient } from "@/lib/gatewayClient";

import type {
  ComposerAttachment,
  FileAttachResponse,
  ImageAttachResponse,
  QueuedAttachmentSnapshot,
} from "./attachmentTypes";

export const IMAGE_MAX_BYTES = 25 * 1024 * 1024;
export const FILE_MAX_BYTES = 25 * 1024 * 1024;

export const IMAGE_EXTENSIONS = new Set([
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".webp",
  ".bmp",
]);

const DEFAULT_IMAGE_PROMPT = "What do you see in this image?";

export type GatewayRequest = <T>(
  method: string,
  params?: Record<string, unknown>,
) => Promise<T>;

export function pathLabel(name: string): string {
  return name.split(/[\\/]/).filter(Boolean).pop() || name;
}

export function attachmentId(kind: ComposerAttachment["kind"], value: string): string {
  return `${kind}:${value}`;
}

export function isImageFile(file: File): boolean {
  if (file.type.startsWith("image/")) return true;
  const ext = file.name.includes(".")
    ? `.${file.name.split(".").pop()!.toLowerCase()}`
    : "";
  return IMAGE_EXTENSIONS.has(ext);
}

export function validateFileForAttach(file: File): string | null {
  if (file.size === 0) return "File is empty";
  const max = isImageFile(file) ? IMAGE_MAX_BYTES : FILE_MAX_BYTES;
  if (file.size > max) {
    const mb = Math.floor(max / (1024 * 1024));
    return `${pathLabel(file.name)} is too large (max ${mb} MB)`;
  }
  if (isImageFile(file)) return null;
  return null;
}

export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") resolve(reader.result);
      else reject(new Error("Failed to read file"));
    };
    reader.onerror = () => reject(reader.error ?? new Error("Failed to read file"));
    reader.readAsDataURL(file);
  });
}

export function base64FromDataUrl(dataUrl: string): string {
  const comma = dataUrl.indexOf(",");
  return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
}

export function buildSubmitText(
  visibleText: string,
  attachments: ComposerAttachment[],
): string {
  const contextRefs = attachments
    .map((a) => a.refText)
    .filter((r): r is string => Boolean(r))
    .join("\n");

  const trimmed = visibleText.trim();
  const hasImage = attachments.some((a) => a.kind === "image");

  const body =
    [contextRefs, trimmed].filter(Boolean).join("\n\n") ||
    (hasImage ? DEFAULT_IMAGE_PROMPT : "");

  return body;
}

export function buildUserDisplayContent(
  visibleText: string,
  attachments: ComposerAttachment[],
): string {
  const trimmed = visibleText.trim();
  if (trimmed) return trimmed;
  if (attachments.length === 0) return "";
  return attachments.map((a) => a.label).join(", ");
}

export function snapshotAttachments(
  attachments: ComposerAttachment[],
): QueuedAttachmentSnapshot[] {
  return attachments.map((a) => ({
    id: a.id,
    kind: a.kind,
    label: a.label,
    fileName: a.fileName,
    dataUrl: a.dataUrl,
    path: a.path,
    refText: a.refText,
    attachedSessionId: a.attachedSessionId,
  }));
}

export function restoreAttachmentsFromSnapshot(
  snapshots: QueuedAttachmentSnapshot[],
): ComposerAttachment[] {
  return snapshots.map((s) => ({ ...s }));
}

export async function uploadAttachment(
  attachment: ComposerAttachment,
  opts: { request: GatewayRequest; sessionId: string },
): Promise<ComposerAttachment> {
  const { request, sessionId } = opts;
  const label = attachment.label || attachment.fileName;

  if (attachment.kind === "image") {
    if (!attachment.dataUrl) {
      throw new Error(`Could not read ${label}`);
    }

    const result = await request<ImageAttachResponse>("image.attach_bytes", {
      session_id: sessionId,
      content_base64: base64FromDataUrl(attachment.dataUrl),
      filename: attachment.fileName,
    });

    if (!result.attached) {
      throw new Error(result.message || `Could not attach ${label}`);
    }

    const attachedPath = result.path ?? attachment.path;

    return {
      ...attachment,
      attachedSessionId: sessionId,
      label: attachedPath ? pathLabel(attachedPath) : attachment.label,
      path: attachedPath,
      uploadState: undefined,
    };
  }

  if (!attachment.dataUrl) {
    throw new Error(`Could not read ${label}`);
  }

  const result = await request<FileAttachResponse>("file.attach", {
    session_id: sessionId,
    path: attachment.fileName,
    name: attachment.fileName,
    data_url: attachment.dataUrl,
  });

  if (!result.attached || !result.ref_text) {
    throw new Error(result.message || `Could not attach ${label}`);
  }

  return {
    ...attachment,
    attachedSessionId: sessionId,
    refText: result.ref_text,
    path: result.path,
    label: result.name ?? attachment.label,
    uploadState: undefined,
  };
}

export async function detachStagedImage(
  gw: GatewayClient,
  sessionId: string,
  path: string,
): Promise<void> {
  await gw.request("image.detach", { session_id: sessionId, path });
}

export async function syncAttachmentsForSubmit(
  attachments: ComposerAttachment[],
  opts: { request: GatewayRequest; sessionId: string },
): Promise<ComposerAttachment[]> {
  const synced: ComposerAttachment[] = [];

  for (const original of attachments) {
    let attachment = original;

    if (attachment.attachedSessionId === opts.sessionId) {
      synced.push(attachment);
      continue;
    }

    if (attachment.kind === "image" || attachment.kind === "file") {
      attachment = await uploadAttachment(attachment, opts);
      synced.push(attachment);
      continue;
    }

    synced.push(attachment);
  }

  return synced;
}

const SESSION_BUSY_RETRY_TIMEOUT_MS = 6_000;
const SESSION_BUSY_RETRY_INTERVAL_MS = 150;

function isSessionBusyError(error: unknown): boolean {
  return /session busy/i.test(
    error instanceof Error ? error.message : String(error),
  );
}

export async function withSessionBusyRetry<T>(
  call: () => Promise<T>,
): Promise<T> {
  const deadline = Date.now() + SESSION_BUSY_RETRY_TIMEOUT_MS;

  for (;;) {
    try {
      return await call();
    } catch (err) {
      if (isSessionBusyError(err) && Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, SESSION_BUSY_RETRY_INTERVAL_MS));
        continue;
      }
      throw err;
    }
  }
}

export async function createAttachmentFromFile(
  file: File,
): Promise<ComposerAttachment> {
  const dataUrl = await fileToDataUrl(file);
  const kind = isImageFile(file) ? "image" : "file";
  const label = pathLabel(file.name);

  return {
    id: attachmentId(kind, `${file.name}-${file.size}-${file.lastModified}`),
    kind,
    label,
    fileName: file.name,
    dataUrl,
  };
}
