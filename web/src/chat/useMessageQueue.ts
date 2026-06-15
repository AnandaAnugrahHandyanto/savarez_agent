import { useCallback, useRef, useState } from "react";

import type { QueuedAttachmentSnapshot } from "./attachmentTypes";
import { restoreAttachmentsFromSnapshot, snapshotAttachments } from "./attachFiles";
import type { ComposerAttachment } from "./attachmentTypes";

export interface QueuedMessage {
  id: string;
  text: string;
  attachments: QueuedAttachmentSnapshot[];
}

export function useMessageQueue() {
  const queueRef = useRef<QueuedMessage[]>([]);
  const [queue, setQueue] = useState<QueuedMessage[]>([]);

  const sync = useCallback(() => {
    setQueue([...queueRef.current]);
  }, []);

  const enqueue = useCallback(
    (text: string, attachments: ComposerAttachment[] = []) => {
      queueRef.current.push({
        id: crypto.randomUUID(),
        text,
        attachments: snapshotAttachments(attachments),
      });
      sync();
    },
    [sync],
  );

  const dequeue = useCallback((): QueuedMessage | undefined => {
    const head = queueRef.current.shift();
    sync();
    return head;
  }, [sync]);

  const remove = useCallback(
    (id: string) => {
      const before = queueRef.current.length;
      queueRef.current = queueRef.current.filter((m) => m.id !== id);
      if (queueRef.current.length !== before) sync();
    },
    [sync],
  );

  const take = useCallback(
    (id: string): QueuedMessage | undefined => {
      const item = queueRef.current.find((m) => m.id === id);
      queueRef.current = queueRef.current.filter((m) => m.id !== id);
      sync();
      return item;
    },
    [sync],
  );

  const clear = useCallback(() => {
    queueRef.current = [];
    sync();
  }, [sync]);

  const peek = useCallback(() => queueRef.current[0], []);

  return { queue, enqueue, dequeue, remove, take, clear, peek, restoreAttachmentsFromSnapshot };
}
