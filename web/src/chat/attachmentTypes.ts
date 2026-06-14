/** Composer attachment staged for the next prompt.submit. */
export interface ComposerAttachment {
  id: string;
  kind: "image" | "file";
  label: string;
  /** Original File name (client-side). */
  fileName: string;
  /** Base64 data URL for upload + inline preview. */
  dataUrl?: string;
  /** Gateway-side path after staging. */
  path?: string;
  /** Workspace-relative @file: ref after file.attach. */
  refText?: string;
  /** Session id when already staged on the gateway. */
  attachedSessionId?: string;
  uploadState?: "uploading" | "error";
}

export interface ImageAttachResponse {
  attached?: boolean;
  path?: string;
  text?: string;
  message?: string;
  count?: number;
  bytes?: number;
  name?: string;
}

export interface FileAttachResponse {
  attached?: boolean;
  message?: string;
  path?: string;
  ref_path?: string;
  ref_text?: string;
  uploaded?: boolean;
  name?: string;
}

export interface ImageDetachResponse {
  detached?: boolean;
  count?: number;
}

/** Snapshot stored on queued messages (no live File handles). */
export type QueuedAttachmentSnapshot = Pick<
  ComposerAttachment,
  | "id"
  | "kind"
  | "label"
  | "fileName"
  | "dataUrl"
  | "path"
  | "refText"
  | "attachedSessionId"
>;

export interface SubmitPayload {
  text: string;
  attachments: ComposerAttachment[];
}
