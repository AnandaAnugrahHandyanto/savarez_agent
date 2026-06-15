import { Button } from "@nous-research/ui/ui/components/button";
import { useToast } from "@nous-research/ui/hooks/use-toast";
import { useCallback, useEffect, useRef, useState } from "react";

import { PluginSlot } from "@/plugins";
import {
  buildBranchSeedMessages,
  sliceBranchDisplayMessages,
} from "@/lib/chatBranch";

import type { SubmitPayload } from "./attachmentTypes";
import {
  buildSubmitText,
  buildUserDisplayContent,
  restoreAttachmentsFromSnapshot,
  syncAttachmentsForSubmit,
  withSessionBusyRetry,
} from "./attachFiles";
import { nextMessageId, type ChatMessage } from "./chatMessages";
import { useChatSession } from "./ChatSessionContext";
import { ChatComposer } from "./ChatComposer";
import { ChatTranscript } from "./ChatTranscript";
import { PromptOverlays } from "./PromptOverlays";
import { useMessageQueue } from "./useMessageQueue";
import { useMessageStream } from "./useMessageStream";
import { useI18n } from "@/i18n";

export function ChatRichView({ isActive: _isActive = true }: { isActive?: boolean }) {
  const {
    gw,
    connectionState,
    sessionId,
    sessionIdRef,
    sessionInfo: gatewayInfo,
    error: gatewayError,
    sessionEnded,
    request,
    startNewChat,
    registerOnHydrated,
    forkFromMessages,
  } = useChatSession();

  const { t } = useI18n();
  const { showToast } = useToast();
  const [forkingMessageId, setForkingMessageId] = useState<string | null>(null);

  const resetRef = useRef<(msgs: Parameters<typeof resetMessages>[0]) => void>(
    () => {},
  );
  const pendingImmediateRef = useRef<SubmitPayload | null>(null);
  const drainingRef = useRef(false);

  const messageQueue = useMessageQueue();

  const {
    messages,
    sessionInfo,
    overlay,
    thinkingStatus,
    addUserMessage,
    addSystemMessage,
    resetMessages,
    clearOverlay,
  } = useMessageStream({ gw, sessionId, sessionIdRef });

  resetRef.current = resetMessages;

  useEffect(() => {
    if (!registerOnHydrated) return;
    return registerOnHydrated((next) => {
      messageQueue.clear();
      pendingImmediateRef.current = null;
      resetRef.current(next);
    });
  }, [registerOnHydrated, messageQueue]);

  const mergedInfo = { ...gatewayInfo, ...sessionInfo };

  const runFork = useCallback(
    async (
      upToMessageId: string | undefined,
      title?: string,
      notify: "toast" | "sys" = "toast",
    ) => {
      if (!forkFromMessages) {
        throw new Error("branch unavailable");
      }
      const seed = buildBranchSeedMessages(messages, upToMessageId);
      const branchTitle = title?.trim() || "Branch";
      const notice = `branched → ${branchTitle}`;
      const display: ChatMessage[] = sliceBranchDisplayMessages(
        messages,
        upToMessageId,
      );
      if (notify === "sys") {
        display.push({
          id: nextMessageId("sys"),
          role: "system",
          content: notice,
        });
      }
      await forkFromMessages(seed, {
        title: branchTitle,
        displayMessages: display,
      });
      if (notify === "toast") {
        showToast(t.chatSession.branched, "success");
      }
    },
    [forkFromMessages, messages, showToast, t.chatSession],
  );

  const handleForkMessage = useCallback(
    (messageId: string) => {
      setForkingMessageId(messageId);
      void runFork(messageId, undefined, "toast")
        .catch((err) => {
          showToast(
            err instanceof Error ? err.message : t.chatSession.branchFailed,
            "error",
          );
        })
        .finally(() => setForkingMessageId(null));
    },
    [runFork, showToast, t.chatSession.branchFailed],
  );

  const handleBranchCommand = useCallback(
    async ({ name }: { name: string }) => {
      await runFork(undefined, name || undefined, "sys");
    },
    [runFork],
  );

  const submitMessage = useCallback(
    async (payload: SubmitPayload) => {
      if (!sessionId || !gw) return;

      const synced = await syncAttachmentsForSubmit(payload.attachments, {
        request: (method, params) => request(method, params),
        sessionId,
      });

      const promptText = buildSubmitText(payload.text, synced);
      const displayContent = buildUserDisplayContent(payload.text, synced);
      const displayAttachments = synced.map((a) => ({
        kind: a.kind,
        label: a.label,
        previewUrl: a.kind === "image" ? a.dataUrl : undefined,
        refText: a.refText,
      }));

      addUserMessage(displayContent, { attachments: displayAttachments });
      await withSessionBusyRetry(() =>
        request("prompt.submit", { session_id: sessionId, text: promptText }),
      );
    },
    [sessionId, gw, addUserMessage, request],
  );

  const handleSubmit = useCallback(
    async (payload: SubmitPayload) => {
      if (!sessionId) return;
      await submitMessage(payload);
    },
    [sessionId, submitMessage],
  );

  const handleEnqueue = useCallback(
    (payload: SubmitPayload) => {
      messageQueue.enqueue(payload.text, payload.attachments);
    },
    [messageQueue],
  );

  const handleQueueSendNow = useCallback(
    async (id: string) => {
      const item = messageQueue.take(id);
      if (!item || !sessionId || !gw) return;

      const payload: SubmitPayload = {
        text: item.text,
        attachments: restoreAttachmentsFromSnapshot(item.attachments),
      };
      pendingImmediateRef.current = payload;

      if (mergedInfo.running) {
        try {
          await gw.request("session.interrupt", { session_id: sessionId });
        } catch {
          messageQueue.enqueue(payload.text, payload.attachments);
          pendingImmediateRef.current = null;
        }
      }
    },
    [messageQueue, sessionId, gw, mergedInfo.running],
  );

  const handleQueueEdit = useCallback(
    (id: string, _text: string) => {
      messageQueue.remove(id);
    },
    [messageQueue],
  );

  const connecting =
    connectionState === "connecting" || connectionState === "idle";

  useEffect(() => {
    if (mergedInfo.running || connecting || overlay || drainingRef.current) {
      return;
    }

    const immediate = pendingImmediateRef.current;
    if (immediate) {
      pendingImmediateRef.current = null;
      drainingRef.current = true;
      void submitMessage(immediate).finally(() => {
        drainingRef.current = false;
      });
      return;
    }

    const head = messageQueue.peek();
    if (!head) return;

    messageQueue.dequeue();
    drainingRef.current = true;
    void submitMessage({
      text: head.text,
      attachments: restoreAttachmentsFromSnapshot(head.attachments),
    }).finally(() => {
      drainingRef.current = false;
    });
  }, [mergedInfo.running, connecting, overlay, messageQueue.queue, submitMessage]);

  useEffect(() => {
    messageQueue.clear();
    pendingImmediateRef.current = null;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reset only when session changes
  }, [sessionId]);

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden">
      <PluginSlot name="chat:top" />

      {(gatewayError || sessionEnded) && (
        <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning overscroll-none">
          <span>{gatewayError ?? "Session ended"}</span>
          {sessionEnded && (
            <Button size="sm" outlined onClick={startNewChat}>
              New chat
            </Button>
          )}
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden overscroll-none">
        <ChatTranscript
          messages={messages}
          thinkingStatus={thinkingStatus}
          className="flex-1"
          holdEmptyPlaceholder={!!sessionId && connecting}
          onForkMessage={forkFromMessages ? handleForkMessage : undefined}
          forkingMessageId={forkingMessageId}
        />

        {overlay && (
          <PromptOverlays
            overlay={overlay}
            gw={gw}
            sessionId={sessionId}
            onClear={clearOverlay}
          />
        )}

        <ChatComposer
          gw={gw}
          sessionId={sessionId}
          model={mergedInfo.model}
          provider={mergedInfo.provider}
          running={mergedInfo.running}
          disabled={connecting || !!overlay}
          queue={messageQueue.queue}
          onSubmit={handleSubmit}
          onEnqueue={handleEnqueue}
          onQueueSendNow={(id) => void handleQueueSendNow(id)}
          onQueueEdit={handleQueueEdit}
          onQueueDelete={messageQueue.remove}
          onSystem={addSystemMessage}
          onBranch={forkFromMessages ? handleBranchCommand : undefined}
        />
      </div>

      <PluginSlot name="chat:bottom" />
    </div>
  );
}
