/**
 * useImageAttachment — intercepts clipboard paste and drag-and-drop of images
 * on the terminal host, and forwards them to the gateway via `image.attach_bytes`
 * so the agent can see them inline (native vision).
 *
 * The GatewayClient (from ChatSidebar's JSON-RPC sidecar) shares the same
 * session_id as the PTY child — both receive `session.info` events on the
 * same channel.  Calling `image.attach_bytes` appends to
 * `session["attached_images"]`, which `_run_prompt_submit` picks up on the
 * next prompt submission.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { GatewayClient } from "@/lib/gatewayClient";

/** Accepted MIME prefixes for image clipboard data. */
const IMAGE_MIME_RE = /^image\//;

export interface AttachedImage {
  /** Original filename or generated label. */
  name: string;
  /** Approximate dimensions if available. */
  width?: number;
  height?: number;
}

interface UseImageAttachmentOptions {
  /** Terminal host element to listen on. */
  hostRef: React.RefObject<HTMLDivElement | null>;
  /** Sidebar's GatewayClient — must be connected. */
  gw: GatewayClient | null;
  /** PTY session id — from session.info events. */
  sessionId: string | null;
}

interface UseImageAttachmentResult {
  /** Currently attached images (pending next prompt submit). */
  attachedImages: AttachedImage[];
  /** Manually clear attached images (e.g. after submit). */
  clearAttached: () => void;
}

export function useImageAttachment({
  hostRef,
  gw,
  sessionId,
}: UseImageAttachmentOptions): UseImageAttachmentResult {
  const [attachedImages, setAttachedImages] = useState<AttachedImage[]>([]);
  const gwRef = useRef(gw);
  const sidRef = useRef(sessionId);

  // Keep refs in sync so event handlers always see current values without
  // re-registering listeners on every render.
  useEffect(() => {
    gwRef.current = gw;
  }, [gw]);

  useEffect(() => {
    sidRef.current = sessionId;
  }, [sessionId]);

  const attachImage = useCallback(
    async (dataUrl: string, filename: string) => {
      const currentGw = gwRef.current;
      const currentSid = sidRef.current;
      if (!currentGw || currentGw.state !== "open" || !currentSid) {
        console.warn(
          "[image-attach] gateway not ready or session unknown — skipping",
        );
        return;
      }

      // Strip the data URL prefix to get raw base64.
      const base64 = dataUrl.replace(/^data:[^;]+;base64,/, "");

      try {
        const result = await currentGw.request<{
          attached?: boolean;
          name?: string;
          width?: number;
          height?: number;
        }>("image.attach_bytes", {
          content_base64: base64,
          filename,
          session_id: currentSid,
        });

        if (result?.attached !== false) {
          const info: AttachedImage = {
            name: result?.name ?? filename,
            width: result?.width,
            height: result?.height,
          };
          setAttachedImages((prev) => [...prev, info]);
          console.log("[image-attach] attached:", info.name);
        }
      } catch (err) {
        console.warn("[image-attach] failed:", err);
      }
    },
    [],
  );

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    // ---- Clipboard paste ----
    const onPaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;

      for (const item of items) {
        if (!IMAGE_MIME_RE.test(item.type)) continue;

        e.preventDefault();
        e.stopPropagation();

        const blob = item.getAsFile();
        if (!blob) continue;

        const reader = new FileReader();
        reader.onload = () => {
          if (typeof reader.result === "string") {
            const ext = extFromMime(blob.type);
            attachImage(reader.result, `clipboard${ext}`);
          }
        };
        reader.readAsDataURL(blob);
        return; // handle first image only
      }
    };

    // ---- Drag and drop ----
    const onDragOver = (e: DragEvent) => {
      if (e.dataTransfer?.types.includes("Files")) {
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
      }
    };

    const onDrop = (e: DragEvent) => {
      const files = e.dataTransfer?.files;
      if (!files?.length) return;

      // Check if any file is an image.
      const images = Array.from(files).filter((f) =>
        IMAGE_MIME_RE.test(f.type),
      );
      if (!images.length) return;

      e.preventDefault();
      e.stopPropagation();

      for (const file of images) {
        const reader = new FileReader();
        reader.onload = () => {
          if (typeof reader.result === "string") {
            const ext = extFromMime(file.type) || extFromName(file.name);
            const name = file.name || `dropped${ext}`;
            attachImage(reader.result, name);
          }
        };
        reader.readAsDataURL(file);
      }
    };

    host.addEventListener("paste", onPaste, { capture: true });
    host.addEventListener("dragover", onDragOver);
    host.addEventListener("drop", onDrop);

    return () => {
      host.removeEventListener("paste", onPaste, { capture: true });
      host.removeEventListener("dragover", onDragOver);
      host.removeEventListener("drop", onDrop);
    };
  }, [hostRef, attachImage]);

  // Clear attached images when session changes (new PTY child).
  useEffect(() => {
    setAttachedImages([]);
  }, [sessionId]);

  return {
    attachedImages,
    clearAttached: () => setAttachedImages([]),
  };
}

function extFromMime(mime: string): string {
  const map: Record<string, string> = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
  };
  return map[mime] ?? ".png";
}

function extFromName(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot) : ".png";
}
