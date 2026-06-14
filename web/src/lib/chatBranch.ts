import type { ChatMessage } from "@/chat/chatMessages";

export type BranchSeedMessage = {
  role: "user" | "assistant";
  content: string;
};

/** Text carried into a branched session (visible transcript only). */
export function chatMessageBranchText(msg: ChatMessage): string {
  return msg.content.trim();
}

/**
 * Build seed messages for `session.create` — conversation through `upToMessageId`
 * (inclusive). When omitted, includes the full visible transcript.
 */
export function buildBranchSeedMessages(
  messages: readonly ChatMessage[],
  upToMessageId?: string,
): BranchSeedMessage[] {
  let end = messages.length;
  if (upToMessageId) {
    const idx = messages.findIndex((m) => m.id === upToMessageId);
    if (idx < 0) return [];
    end = idx + 1;
  }

  return messages
    .slice(0, end)
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map((m) => ({
      role: m.role as "user" | "assistant",
      content: chatMessageBranchText(m),
    }))
    .filter((m) => m.content.length > 0);
}

/** Visible transcript rows carried into the branched chat UI. */
export function sliceBranchDisplayMessages(
  messages: readonly ChatMessage[],
  upToMessageId?: string,
): ChatMessage[] {
  let end = messages.length;
  if (upToMessageId) {
    const idx = messages.findIndex((m) => m.id === upToMessageId);
    if (idx < 0) return [];
    end = idx + 1;
  }
  return messages
    .slice(0, end)
    .filter((m) => m.role === "user" || m.role === "assistant");
}
