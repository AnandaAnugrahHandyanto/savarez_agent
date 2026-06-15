import { describe, expect, it, vi } from "vitest";

import type { ComposerAttachment } from "./attachmentTypes";
import {
  base64FromDataUrl,
  buildSubmitText,
  buildUserDisplayContent,
  isImageFile,
  restoreAttachmentsFromSnapshot,
  snapshotAttachments,
  syncAttachmentsForSubmit,
  uploadAttachment,
  validateFileForAttach,
  IMAGE_MAX_BYTES,
} from "./attachFiles";

describe("attachFiles", () => {
  it("buildSubmitText joins file refs and visible text", () => {
    const attachments: ComposerAttachment[] = [
      {
        id: "f:1",
        kind: "file",
        label: "notes.txt",
        fileName: "notes.txt",
        refText: "@file:notes.txt",
      },
    ];
    expect(buildSubmitText("summarize this", attachments)).toBe(
      "@file:notes.txt\n\nsummarize this",
    );
  });

  it("buildSubmitText uses default image prompt when only images attached", () => {
    const attachments: ComposerAttachment[] = [
      {
        id: "i:1",
        kind: "image",
        label: "photo.png",
        fileName: "photo.png",
      },
    ];
    expect(buildSubmitText("", attachments)).toBe(
      "What do you see in this image?",
    );
  });

  it("buildUserDisplayContent falls back to attachment labels", () => {
    const attachments: ComposerAttachment[] = [
      {
        id: "i:1",
        kind: "image",
        label: "photo.png",
        fileName: "photo.png",
      },
    ];
    expect(buildUserDisplayContent("", attachments)).toBe("photo.png");
  });

  it("validateFileForAttach rejects oversized files", () => {
    const big = new File([new Uint8Array(IMAGE_MAX_BYTES + 1)], "big.png", {
      type: "image/png",
    });
    expect(validateFileForAttach(big)).toMatch(/too large/i);
  });

  it("isImageFile detects by mime and extension", () => {
    expect(
      isImageFile(new File([], "x.PNG", { type: "application/octet-stream" })),
    ).toBe(true);
    expect(
      isImageFile(new File([], "doc.pdf", { type: "application/pdf" })),
    ).toBe(false);
  });

  it("base64FromDataUrl strips data URL prefix", () => {
    expect(base64FromDataUrl("data:image/png;base64,abc123")).toBe("abc123");
  });

  it("uploadAttachment calls image.attach_bytes for images", async () => {
    const request = vi.fn().mockResolvedValue({
      attached: true,
      path: "/tmp/upload.png",
    });

    const next = await uploadAttachment(
      {
        id: "i:1",
        kind: "image",
        label: "shot.png",
        fileName: "shot.png",
        dataUrl: "data:image/png;base64,QUJD",
      },
      { request, sessionId: "sess-1" },
    );

    expect(request).toHaveBeenCalledWith("image.attach_bytes", {
      session_id: "sess-1",
      content_base64: "QUJD",
      filename: "shot.png",
    });
    expect(next.attachedSessionId).toBe("sess-1");
    expect(next.path).toBe("/tmp/upload.png");
  });

  it("uploadAttachment calls file.attach for non-images", async () => {
    const request = vi.fn().mockResolvedValue({
      attached: true,
      ref_text: "@file:notes.txt",
      path: "/workspace/notes.txt",
      name: "notes.txt",
    });

    const next = await uploadAttachment(
      {
        id: "f:1",
        kind: "file",
        label: "notes.txt",
        fileName: "notes.txt",
        dataUrl: "data:text/plain;base64,SGk=",
      },
      { request, sessionId: "sess-1" },
    );

    expect(request).toHaveBeenCalledWith("file.attach", {
      session_id: "sess-1",
      path: "notes.txt",
      name: "notes.txt",
      data_url: "data:text/plain;base64,SGk=",
    });
    expect(next.refText).toBe("@file:notes.txt");
  });

  it("syncAttachmentsForSubmit skips already-staged attachments", async () => {
    const request = vi.fn();
    const attachments: ComposerAttachment[] = [
      {
        id: "f:1",
        kind: "file",
        label: "done.txt",
        fileName: "done.txt",
        refText: "@file:done.txt",
        attachedSessionId: "sess-1",
      },
    ];

    const synced = await syncAttachmentsForSubmit(attachments, {
      request,
      sessionId: "sess-1",
    });

    expect(request).not.toHaveBeenCalled();
    expect(synced).toHaveLength(1);
  });

  it("snapshotAttachments round-trips through restore", () => {
    const attachments: ComposerAttachment[] = [
      {
        id: "i:1",
        kind: "image",
        label: "a.png",
        fileName: "a.png",
        dataUrl: "data:image/png;base64,x",
        uploadState: "uploading",
      },
    ];
    const snap = snapshotAttachments(attachments);
    const restored = restoreAttachmentsFromSnapshot(snap);
    expect(restored[0]?.dataUrl).toBe("data:image/png;base64,x");
    expect(restored[0]?.uploadState).toBeUndefined();
  });
});
