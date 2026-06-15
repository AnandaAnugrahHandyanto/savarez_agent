import type { GatewayClient } from "@/lib/gatewayClient";
import { useCallback, useEffect, useRef, useState } from "react";

import type { ComposerAttachment } from "./attachmentTypes";
import {
  createAttachmentFromFile,
  detachStagedImage,
  uploadAttachment,
  validateFileForAttach,
} from "./attachFiles";

interface UseComposerAttachmentsOptions {
  gw: GatewayClient | null;
  sessionId: string | null;
  onError?: (message: string) => void;
}

export function useComposerAttachments({
  gw,
  sessionId,
  onError,
}: UseComposerAttachmentsOptions) {
  const [attachments, setAttachments] = useState<ComposerAttachment[]>([]);
  const eagerInFlight = useRef<Map<string, Promise<void>>>(new Map());

  const clear = useCallback(() => {
    setAttachments([]);
    eagerInFlight.current.clear();
  }, []);

  const addFiles = useCallback(
    async (files: FileList | File[]) => {
      if (!sessionId) return;

      const list = Array.from(files);
      for (const file of list) {
        const validationError = validateFileForAttach(file);
        if (validationError) {
          onError?.(validationError);
          continue;
        }

        try {
          const attachment = await createAttachmentFromFile(file);
          setAttachments((prev) => {
            if (prev.some((a) => a.id === attachment.id)) return prev;
            return [...prev, attachment];
          });

          if (attachment.kind === "file" && gw) {
            const task = (async () => {
              setAttachments((prev) =>
                prev.map((a) =>
                  a.id === attachment.id
                    ? { ...a, uploadState: "uploading" as const }
                    : a,
                ),
              );
              try {
                const synced = await uploadAttachment(attachment, {
                  request: (method, params) => gw.request(method, params),
                  sessionId,
                });
                setAttachments((prev) => {
                  if (!prev.some((a) => a.id === attachment.id)) return prev;
                  return prev.map((a) => (a.id === attachment.id ? synced : a));
                });
              } catch (err) {
                const msg =
                  err instanceof Error ? err.message : String(err);
                onError?.(msg);
                setAttachments((prev) => {
                  if (!prev.some((a) => a.id === attachment.id)) return prev;
                  return prev.map((a) =>
                    a.id === attachment.id
                      ? { ...a, uploadState: "error" as const }
                      : a,
                  );
                });
              }
            })().finally(() => {
              eagerInFlight.current.delete(attachment.id);
            });
            eagerInFlight.current.set(attachment.id, task);
          }
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          onError?.(msg);
        }
      }
    },
    [gw, sessionId, onError],
  );

  const remove = useCallback(
    (id: string) => {
      setAttachments((prev) => {
        const target = prev.find((a) => a.id === id);
        if (
          target?.kind === "image" &&
          target.path &&
          target.attachedSessionId &&
          gw &&
          sessionId
        ) {
          void detachStagedImage(gw, sessionId, target.path).catch(() => {});
        }
        return prev.filter((a) => a.id !== id);
      });
    },
    [gw, sessionId],
  );

  useEffect(() => {
    clear();
  }, [sessionId, clear]);

  return {
    attachments,
    addFiles,
    remove,
    clear,
    eagerInFlight,
  };
}
