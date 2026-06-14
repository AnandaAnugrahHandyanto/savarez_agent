import type { ToolEntry } from "@/components/ToolCall";
import type { SessionMessage } from "@/lib/api";

export type ChatMessageRole = "user" | "assistant" | "system";

export interface UserMessageAttachment {
  kind: "image" | "file";
  label: string;
  previewUrl?: string;
  refText?: string;
}

export interface ChatMessage {
  id: string;
  role: ChatMessageRole;
  content: string;
  attachments?: UserMessageAttachment[];
  streaming?: boolean;
  reasoning?: string;
  reasoningStreaming?: boolean;
  toolCalls?: ToolEntry[];
  error?: string;
  timestamp?: number;
}

export type PromptOverlay =
  | {
      kind: "approval";
      command?: string;
      description?: string;
      allowPermanent?: boolean;
    }
  | {
      kind: "clarify";
      requestId: string;
      question: string;
      choices?: string[] | null;
    }
  | { kind: "sudo"; requestId: string; command?: string }
  | {
      kind: "secret";
      requestId: string;
      envVar?: string;
      prompt?: string;
    };

export interface GatewayEventPayload {
  text?: string;
  rendered?: string;
  status?: string;
  message?: string;
  id?: string;
  name?: string;
  tool_id?: string;
  tool_call_id?: string;
  args?: unknown;
  arguments?: unknown;
  context?: string;
  input?: unknown;
  preview?: string;
  result?: unknown;
  summary?: string;
  error?: string | boolean;
  inline_diff?: string;
  duration_s?: number;
  request_id?: string;
  question?: string;
  choices?: string[] | null;
  command?: string;
  description?: string;
  allow_permanent?: boolean;
  env_var?: string;
  prompt?: string;
  model?: string;
  provider?: string;
  cwd?: string;
  running?: boolean;
  title?: string;
}

let messageCounter = 0;

export function nextMessageId(prefix = "msg"): string {
  messageCounter += 1;
  return `${prefix}:${messageCounter}`;
}

export function appendTextDelta(content: string, delta: string): string {
  return `${content}${delta}`;
}

export function appendReasoningDelta(
  reasoning: string | undefined,
  delta: string,
): string {
  return `${reasoning ?? ""}${delta}`;
}

function toolStableId(payload: GatewayEventPayload | undefined): string {
  return payload?.tool_id || payload?.tool_call_id || payload?.id || "";
}

let liveToolCounter = 0;

function nextLiveToolId(name: string): string {
  liveToolCounter += 1;
  return `live-tool:${name}:${liveToolCounter}`;
}

function payloadContext(payload: GatewayEventPayload | undefined): string {
  if (typeof payload?.context === "string") return payload.context;
  if (payload?.args && typeof payload.args === "object") {
    try {
      return JSON.stringify(payload.args);
    } catch {
      return "";
    }
  }
  if (typeof payload?.arguments === "string") return payload.arguments;
  return "";
}

function findToolIndex(
  tools: ToolEntry[],
  name: string,
  stableId: string,
  phase: "running" | "complete",
): number {
  if (stableId) {
    const idx = tools.findIndex((t) => t.tool_id === stableId || t.id === stableId);
    if (idx >= 0) return idx;
  }

  const pending = tools
    .map((t, i) => ({ t, i }))
    .filter(({ t }) => t.name === name && t.status === "running");

  if (pending.length === 0) return -1;
  if (phase === "complete") return pending[0].i;
  return pending.at(-1)?.i ?? -1;
}

export function upsertToolPart(
  tools: ToolEntry[],
  payload: GatewayEventPayload | undefined,
  phase: "running" | "complete",
): ToolEntry[] {
  const name = payload?.name || "tool";
  const stableId = toolStableId(payload);
  const next = [...tools];
  const index = findToolIndex(next, name, stableId, phase);
  const now = Date.now();

  const base: ToolEntry = {
    kind: "tool",
    id:
      stableId ||
      (index >= 0 ? next[index].id : nextLiveToolId(name)),
    tool_id: stableId || (index >= 0 ? next[index].tool_id : nextLiveToolId(name)),
    name,
    context: payloadContext(payload) || (index >= 0 ? next[index].context : undefined),
    preview:
      typeof payload?.preview === "string"
        ? payload.preview
        : index >= 0
          ? next[index].preview
          : undefined,
    summary:
      typeof payload?.summary === "string"
        ? payload.summary
        : index >= 0
          ? next[index].summary
          : undefined,
    error:
      payload?.error
        ? typeof payload.error === "string"
          ? payload.error
          : "error"
        : index >= 0
          ? next[index].error
          : undefined,
    inline_diff:
      typeof payload?.inline_diff === "string"
        ? payload.inline_diff
        : index >= 0
          ? next[index].inline_diff
          : undefined,
    status:
      phase === "complete"
        ? payload?.error
          ? "error"
          : "done"
        : "running",
    startedAt: index >= 0 ? next[index].startedAt : now,
    completedAt: phase === "complete" ? now : undefined,
  };

  if (index === -1) {
    return [...next, base];
  }

  next[index] = { ...next[index], ...base };
  return next;
}

export function toChatMessagesFromRest(messages: SessionMessage[]): ChatMessage[] {
  const out: ChatMessage[] = [];

  for (const msg of messages) {
    if (msg.role === "tool") continue;

    const content =
      typeof msg.content === "string"
        ? msg.content
        : msg.content == null
          ? ""
          : String(msg.content);

    if (msg.role === "user" || msg.role === "assistant" || msg.role === "system") {
      const chat: ChatMessage = {
        id: nextMessageId(msg.role),
        role: msg.role,
        content,
        timestamp: msg.timestamp,
      };

      if (msg.role === "assistant" && msg.tool_calls?.length) {
        chat.toolCalls = msg.tool_calls.map((tc) => ({
          kind: "tool",
          id: tc.id,
          tool_id: tc.id,
          name: tc.function?.name ?? "tool",
          context: tc.function?.arguments,
          status: "done",
          startedAt: msg.timestamp ?? 0,
          completedAt: msg.timestamp,
        }));
      }

      out.push(chat);
    }
  }

  return out;
}

interface GatewayTranscriptRow {
  role?: string;
  text?: string;
  name?: string;
  context?: string;
  reasoning?: string;
}

export interface SessionInflightTurn {
  user?: string;
  assistant?: string;
  streaming?: boolean;
}

export function inflightUserMessage(
  inflight?: SessionInflightTurn | null,
): ChatMessage | null {
  const user = (inflight?.user ?? "").trim();
  if (!user) return null;
  return { id: nextMessageId("user"), role: "user", content: user };
}

export function inflightAssistantMessage(
  inflight?: SessionInflightTurn | null,
): ChatMessage | null {
  const assistant = inflight?.assistant ?? "";
  const streaming = Boolean(inflight?.streaming);
  if (!assistant && !streaming) return null;
  return {
    id: nextMessageId("assistant"),
    role: "assistant",
    content: assistant,
    streaming,
  };
}

/** Append in-flight turn rows not yet committed to session history. */
export function appendInflightToMessages(
  base: readonly ChatMessage[],
  inflight?: SessionInflightTurn | null,
): ChatMessage[] {
  const next = [...base];
  const userMsg = inflightUserMessage(inflight);
  if (userMsg) {
    const lastUser = [...next].reverse().find((m) => m.role === "user");
    if (!lastUser || lastUser.content.trim() !== userMsg.content.trim()) {
      next.push(userMsg);
    }
  }
  const assistantMsg = inflightAssistantMessage(inflight);
  if (assistantMsg) {
    const last = next.at(-1);
    if (last?.role === "assistant" && (last.streaming || assistantMsg.streaming)) {
      next[next.length - 1] = {
        ...last,
        content: assistantMsg.content || last.content,
        streaming: assistantMsg.streaming ?? last.streaming,
      };
    } else {
      next.push(assistantMsg);
    }
  }
  return next;
}

/** Convert gateway RPC transcript rows (`session.activate` / `session.resume`). */
export function toChatMessagesFromGateway(rows: unknown): ChatMessage[] {
  if (!Array.isArray(rows)) return [];

  const out: ChatMessage[] = [];
  const pendingTools: ToolEntry[] = [];

  for (const row of rows) {
    if (!row || typeof row !== "object") continue;
    const item = row as GatewayTranscriptRow;
    const role = item.role;

    if (role === "tool") {
      const toolName = item.name ?? "tool";
      const toolId = nextMessageId("tool");
      pendingTools.push({
        kind: "tool",
        id: toolId,
        tool_id: toolId,
        name: toolName,
        context: item.context,
        status: "done",
        startedAt: Date.now(),
        completedAt: Date.now(),
      });
      continue;
    }

    if (role !== "user" && role !== "assistant" && role !== "system") {
      continue;
    }

    const content = typeof item.text === "string" ? item.text : "";
    if (!content.trim() && role !== "assistant") continue;

    const chat: ChatMessage = {
      id: nextMessageId(role),
      role,
      content,
      reasoning: item.reasoning,
    };

    if (role === "assistant" && pendingTools.length > 0) {
      chat.toolCalls = [...pendingTools];
      pendingTools.length = 0;
    }

    if (content.trim() || role === "assistant") {
      out.push(chat);
    }
  }

  return out;
}


export const STREAM_DELTA_FLUSH_MS = 33;
