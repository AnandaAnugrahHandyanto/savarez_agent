import { DEFAULT_OSC_PATHS } from "../osc/types.js";
import type { ChatBoxConfig } from "./config.js";

export interface ChatBoxOscClient {
  send(address: string, args: (string | number | boolean | null)[]): void;
}

export interface ChatBoxSendOptions {
  text: string;
  submit?: boolean;
  notify?: boolean;
}

export interface ChatBoxSendResult {
  success: boolean;
  text?: string;
  trimmed?: boolean;
  error?: "chatbox-disabled" | "empty" | "rate-limited";
  retryAfterMs?: number;
}

export interface ChatBoxTypingResult {
  success: boolean;
  error?: "chatbox-disabled";
}

export class VRChatChatBoxSender {
  private lastSendAt = Number.NEGATIVE_INFINITY;
  private readonly nowMs: () => number;

  constructor(
    private readonly config: ChatBoxConfig,
    private readonly client: ChatBoxOscClient,
    nowMs?: () => number,
  ) {
    this.nowMs = nowMs ?? Date.now;
  }

  send(options: ChatBoxSendOptions): ChatBoxSendResult {
    if (!this.config.enabled) {
      return { success: false, error: "chatbox-disabled" };
    }
    const normalized = normalizeChatBoxText(options.text, {
      maxChars: this.config.maxChars,
      maxLines: this.config.maxLines,
    });
    if (!normalized.text.trim()) {
      return { success: false, error: "empty" };
    }
    const now = this.nowMs();
    const retryAfterMs = this.lastSendAt + this.config.minIntervalMs - now;
    if (retryAfterMs > 0) {
      return { success: false, error: "rate-limited", retryAfterMs };
    }
    this.client.send(DEFAULT_OSC_PATHS.chatbox, [
      normalized.text,
      options.submit ?? this.config.submit,
      options.notify ?? this.config.notify,
    ]);
    this.lastSendAt = now;
    return {
      success: true,
      text: normalized.text,
      trimmed: normalized.trimmed,
    };
  }

  setTyping(typing: boolean): ChatBoxTypingResult {
    if (!this.config.enabled) {
      return { success: false, error: "chatbox-disabled" };
    }
    this.client.send(DEFAULT_OSC_PATHS.chatboxTyping, [typing]);
    return { success: true };
  }
}

export function normalizeChatBoxText(
  text: string,
  limits: { maxChars: number; maxLines: number },
): { text: string; trimmed: boolean } {
  const nfcText = text.normalize("NFC").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const maxLines = Math.max(1, Math.min(9, limits.maxLines));
  const maxChars = Math.max(1, Math.min(144, limits.maxChars));
  const limitedLines = nfcText.split("\n").slice(0, maxLines).join("\n");
  const limitedText =
    limitedLines.length > maxChars ? limitedLines.slice(0, maxChars) : limitedLines;
  return {
    text: limitedText,
    trimmed: limitedText !== nfcText,
  };
}
