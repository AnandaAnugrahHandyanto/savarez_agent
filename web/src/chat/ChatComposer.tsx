import type { GatewayClient } from "@/lib/gatewayClient";
import { Button } from "@nous-research/ui/ui/components/button";
import { useToast } from "@nous-research/ui/hooks/use-toast";
import { cn } from "@/lib/utils";
import { Loader2, Plus, Send, Square } from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type DragEvent,
} from "react";

import {
  SlashPopover,
  type SlashPopoverHandle,
} from "@/components/SlashPopover";
import { executeSlash } from "@/lib/slashExec";

import type { SubmitPayload } from "./attachmentTypes";
import { ComposerAttachmentList } from "./ComposerAttachmentList";
import { ModelMenuPopover } from "./ModelMenuPopover";
import { modelShortName } from "./modelPickerCore";
import { QueuedMessageItem } from "./QueuedMessageItem";
import { useComposerAttachments } from "./useComposerAttachments";
import type { QueuedMessage } from "./useMessageQueue";

const TEXTAREA_MAX_HEIGHT_PX = 160;

/** Shared toolbar control height — model switcher is the reference size. */
const COMPOSER_CONTROL_HEIGHT = "h-7";
const COMPOSER_ICON_CONTROL = cn(
  COMPOSER_CONTROL_HEIGHT,
  "w-7 shrink-0 rounded-md p-0 grid-cols-1 place-items-center [&>svg]:size-3.5",
);
const COMPOSER_GHOST_ICON_CONTROL = cn(
  COMPOSER_ICON_CONTROL,
  "border border-border/40",
);
const COMPOSER_MODEL_CONTROL = cn(
  COMPOSER_CONTROL_HEIGHT,
  "shrink-0 rounded-md border border-border/40 px-2.5 py-0 text-xs font-mono",
);

interface Props {
  gw: GatewayClient | null;
  sessionId: string | null;
  model?: string;
  provider?: string;
  running?: boolean;
  disabled?: boolean;
  queue: QueuedMessage[];
  onSubmit(payload: SubmitPayload): Promise<void>;
  onEnqueue(payload: SubmitPayload): void;
  onQueueSendNow(id: string): void;
  onQueueEdit(id: string, text: string): void;
  onQueueDelete(id: string): void;
  onSystem(text: string): void;
  onBranch?: (opts: { name: string }) => Promise<void>;
}

export function ChatComposer({
  gw,
  sessionId,
  model,
  provider,
  running,
  disabled,
  queue,
  onSubmit,
  onEnqueue,
  onQueueSendNow,
  onQueueEdit,
  onQueueDelete,
  onSystem,
  onBranch,
}: Props) {
  const { showToast } = useToast();
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [modelOpen, setModelOpen] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const slashRef = useRef<SlashPopoverHandle>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragDepthRef = useRef(0);

  const { attachments, addFiles, remove, clear } = useComposerAttachments({
    gw,
    sessionId,
    onError: (message) => showToast(message, "error"),
  });

  const canType = !!gw && !!sessionId && !disabled;
  const isRunning = !!running || busy;
  const hasInput = !!input.trim();
  const hasAttachments = attachments.length > 0;
  const canSend = hasInput || hasAttachments;
  const hasUploading = attachments.some((a) => a.uploadState === "uploading");

  const resizeTextarea = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, TEXTAREA_MAX_HEIGHT_PX)}px`;
  }, []);

  useEffect(() => {
    resizeTextarea();
  }, [input, resizeTextarea]);

  const clearInput = useCallback(() => {
    setInput("");
    requestAnimationFrame(resizeTextarea);
  }, [resizeTextarea]);

  const currentPayload = useCallback(
    (): SubmitPayload => ({
      text: input.trim(),
      attachments: [...attachments],
    }),
    [input, attachments],
  );

  const deliverPayload = useCallback(
    async (payload: SubmitPayload, opts?: { forceSend?: boolean }) => {
      if (!canType || busy) return;
      const text = payload.text.trim();
      const atts = payload.attachments;

      if (!text && atts.length === 0) return;

      if (atts.some((a) => a.uploadState === "error")) {
        showToast("Remove failed attachments before sending", "error");
        return;
      }
      if (atts.some((a) => a.uploadState === "uploading")) {
        showToast("Wait for attachments to finish uploading", "error");
        return;
      }

      if (text.startsWith("/")) {
        setBusy(true);
        try {
          await executeSlash({
            command: text,
            sessionId: sessionId!,
            gw: gw!,
            callbacks: {
              sys: onSystem,
              send: (t) => onSubmit({ text: t, attachments: [] }),
              branch: onBranch,
            },
          });
          clearInput();
          clear();
        } finally {
          setBusy(false);
          textareaRef.current?.focus();
        }
        return;
      }

      if (running && !opts?.forceSend) {
        onEnqueue({ text, attachments: atts });
        clearInput();
        clear();
        textareaRef.current?.focus();
        return;
      }

      setBusy(true);
      try {
        await onSubmit({ text, attachments: atts });
        clearInput();
        clear();
      } finally {
        setBusy(false);
        textareaRef.current?.focus();
      }
    },
    [
      canType,
      busy,
      running,
      sessionId,
      gw,
      onSystem,
      onSubmit,
      onEnqueue,
      onBranch,
      clearInput,
      clear,
    ],
  );

  const handleSubmit = useCallback(
    (overrideText?: string) => {
      const text = (overrideText ?? input).trim();
      if (!text && !hasAttachments) return;
      void deliverPayload({ text, attachments: [...attachments] });
    },
    [input, hasAttachments, attachments, deliverPayload],
  );

  const handleStop = useCallback(async () => {
    if (!gw || !sessionId) return;
    setBusy(true);
    try {
      await gw.request("session.interrupt", { session_id: sessionId });
    } finally {
      setBusy(false);
    }
  }, [gw, sessionId]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (slashRef.current?.handleKey(e)) return;

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileInput = (files: FileList | null) => {
    if (!files?.length) return;
    void addFiles(files);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const resetDrag = () => {
    dragDepthRef.current = 0;
    setDragActive(false);
  };

  const handleDragEnter = (e: DragEvent) => {
    if (!canType || !e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    dragDepthRef.current += 1;
    setDragActive(true);
  };

  const handleDragLeave = (e: DragEvent) => {
    if (!e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) setDragActive(false);
  };

  const handleDragOver = (e: DragEvent) => {
    if (!canType || !e.dataTransfer.types.includes("Files")) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  };

  const handleDrop = (e: DragEvent) => {
    if (!canType) return;
    e.preventDefault();
    resetDrag();
    if (e.dataTransfer.files.length > 0) {
      void addFiles(e.dataTransfer.files);
    }
  };

  return (
    <div className="shrink-0 overscroll-none border-t border-border/40 bg-background-base/80 px-3 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-4 backdrop-blur-sm">
      <div className="relative mx-auto max-w-3xl">
        <SlashPopover
          ref={slashRef}
          input={input}
          gw={gw}
          onApply={setInput}
          onSubmit={(text) => handleSubmit(text)}
        />

        {queue.length > 0 && (
          <div className="mb-2 max-h-[25vh] overflow-y-auto rounded-lg border border-border/40 bg-muted/10">
            <p className="px-2.5 pt-2 text-xs font-medium text-text-tertiary">
              Queued ({queue.length})
            </p>
            {queue.map((item) => (
              <QueuedMessageItem
                key={item.id}
                text={item.text}
                attachmentCount={item.attachments.length}
                onSendNow={() => onQueueSendNow(item.id)}
                onEdit={() => {
                  onQueueEdit(item.id, item.text);
                  setInput(item.text);
                  textareaRef.current?.focus();
                }}
                onDelete={() => onQueueDelete(item.id)}
              />
            ))}
          </div>
        )}

        <div
          className={cn(
            "rounded-lg border bg-muted/10 p-2 transition-colors",
            dragActive
              ? "border-primary/50 bg-primary/5"
              : "border-border/50",
          )}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <ComposerAttachmentList
            attachments={attachments}
            onRemove={(id) => void remove(id)}
          />

          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            placeholder={
              running
                ? "Queue a message… (/ for commands)"
                : "Message Hermes… (/ for commands)"
            }
            disabled={!canType}
            className={cn(
              "w-full min-h-[2.25rem] max-h-40 resize-none bg-transparent",
              // 16px on mobile prevents iOS Safari from zooming on focus (theme base is 15px).
              "text-[16px] sm:text-sm outline-none placeholder:text-text-tertiary touch-manipulation",
            )}
          />

          <div className="mt-2 flex items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/*,*"
              className="hidden"
              onChange={(e) => handleFileInput(e.target.files)}
            />

            <Button
              type="button"
              ghost
              size="icon"
              disabled={!canType}
              onClick={() => fileInputRef.current?.click()}
              className={COMPOSER_GHOST_ICON_CONTROL}
              aria-label="Attach files"
              title="Attach files"
            >
              <Plus />
            </Button>

            <Button
              type="button"
              ghost
              size="sm"
              disabled={!sessionId}
              onClick={() => setModelOpen(true)}
              className={COMPOSER_MODEL_CONTROL}
            >
              {modelShortName(model, provider)}
            </Button>

            <div className="flex-1" />

            {isRunning && (
              <Button
                type="button"
                size="icon"
                destructive
                onClick={() => void handleStop()}
                disabled={!sessionId || busy}
                className={COMPOSER_ICON_CONTROL}
                aria-label="Stop"
              >
                <Square />
              </Button>
            )}

            {canSend && (
              <Button
                type="button"
                size="icon"
                onClick={() => void deliverPayload(currentPayload())}
                disabled={!canType || busy || hasUploading}
                className={COMPOSER_ICON_CONTROL}
                aria-label={running ? "Queue message" : "Send"}
              >
                {busy ? <Loader2 className="animate-spin" /> : <Send />}
              </Button>
            )}
          </div>
        </div>
      </div>

      {modelOpen && gw && sessionId && (
        <ModelMenuPopover
          gw={gw}
          sessionId={sessionId}
          onClose={() => setModelOpen(false)}
        />
      )}
    </div>
  );
}
