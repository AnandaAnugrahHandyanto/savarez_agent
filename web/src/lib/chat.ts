// SSE client for the Hermes chat API.
// We use fetch + ReadableStream (not EventSource) so we can send the
// bearer Authorization header.  The wire format is plain SSE:
//   event: <name>\ndata: <json>\n\n

const STORAGE_KEY = "hermes.chat.session_id";

export interface BaseEvent { call_id?: string }

export interface StatusEvent extends BaseEvent {
  type: "status";
  kind: string;
  session_id?: string;
}
export interface TextDeltaEvent extends BaseEvent {
  type: "text-delta";
  delta: string;
}
export interface TurnStartEvent extends BaseEvent { type: "turn-start" }
export interface TurnEndEvent extends BaseEvent {
  type: "turn-end";
  final_text: string;
}
export interface ToolCallStartEvent extends BaseEvent {
  type: "tool-call-start";
  tool: string;
  args_summary: string;
}
export interface ToolCallResultEvent extends BaseEvent {
  type: "tool-call-result";
  tool: string;
  ok: boolean;
  summary: string;
}
export interface ApprovalRequestEvent extends BaseEvent {
  type: "approval-request";
  command: string;
  description: string;
  allow_permanent?: boolean;
}
export interface ClarifyRequestEvent extends BaseEvent {
  type: "clarify-request";
  question: string;
  choices: string[];
}
export interface ErrorEvent extends BaseEvent {
  type: "error";
  detail: string;
}

export type ChatEvent =
  | StatusEvent
  | TextDeltaEvent
  | TurnStartEvent
  | TurnEndEvent
  | ToolCallStartEvent
  | ToolCallResultEvent
  | ApprovalRequestEvent
  | ClarifyRequestEvent
  | ErrorEvent;

type Listener = (e: ChatEvent) => void;

function authHeaders(): Record<string, string> {
  const token = window.__HERMES_SESSION_TOKEN__;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Create a new session and store its id in localStorage. */
export async function createSession(): Promise<string> {
  const res = await fetch("/api/chat/sessions", {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`createSession: ${res.status}`);
  const { session_id } = (await res.json()) as { session_id: string };
  localStorage.setItem(STORAGE_KEY, session_id);
  return session_id;
}

/** Return the persisted session id, or null. */
export function loadStoredSession(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function clearStoredSession(): void {
  localStorage.removeItem(STORAGE_KEY);
}

/** Fetch persisted messages for resume (history replay). */
export async function getMessages(sessionId: string): Promise<unknown[]> {
  const res = await fetch(`/api/chat/sessions/${encodeURIComponent(sessionId)}/messages`, {
    headers: authHeaders(),
  });
  if (res.status === 404) return [];
  if (!res.ok) throw new Error(`getMessages: ${res.status}`);
  const data = (await res.json()) as { messages?: unknown[] };
  return data.messages ?? [];
}

export class ChatClient {
  readonly sessionId: string;
  private listeners = new Set<Listener>();
  private abort: AbortController | null = null;
  private closed = false;

  constructor(sessionId: string) {
    this.sessionId = sessionId;
  }

  on(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private emit(e: ChatEvent) {
    for (const cb of this.listeners) {
      try { cb(e); } catch (err) { console.error("[chat] listener", err); }
    }
  }

  /** Start streaming events.  Runs until close() or the connection drops. */
  async connect(): Promise<void> {
    if (this.abort) throw new Error("already connected");
    this.abort = new AbortController();
    try {
      const res = await fetch(
        `/api/chat/sessions/${encodeURIComponent(this.sessionId)}/stream`,
        { headers: { ...authHeaders(), Accept: "text/event-stream" }, signal: this.abort.signal },
      );
      if (res.status === 404) {
        this.emit({ type: "error", detail: "Session not found" });
        return;
      }
      if (!res.ok || !res.body) {
        throw new Error(`stream: ${res.status}`);
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      while (!this.closed) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        // SSE frames are separated by a blank line.
        let idx: number;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
          const frame = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          const ev = parseFrame(frame);
          if (ev) this.emit(ev);
        }
      }
    } catch (err) {
      if (!this.closed) {
        this.emit({ type: "error", detail: err instanceof Error ? err.message : String(err) });
      }
    } finally {
      this.abort = null;
    }
  }

  close(): void {
    this.closed = true;
    if (this.abort) {
      this.abort.abort();
      this.abort = null;
    }
  }

  async send(text: string): Promise<void> {
    const res = await fetch(`/api/chat/sessions/${encodeURIComponent(this.sessionId)}/send`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => res.statusText);
      throw new Error(`send: ${res.status} ${detail}`);
    }
  }

  async approve(callId: string, decision: "once" | "session" | "always" | "deny"): Promise<void> {
    const res = await fetch(`/api/chat/sessions/${encodeURIComponent(this.sessionId)}/approve`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ call_id: callId, decision }),
    });
    if (!res.ok) throw new Error(`approve: ${res.status}`);
  }

  async clarify(callId: string, answer: string): Promise<void> {
    const res = await fetch(`/api/chat/sessions/${encodeURIComponent(this.sessionId)}/clarify`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ call_id: callId, answer }),
    });
    if (!res.ok) throw new Error(`clarify: ${res.status}`);
  }

  async cancel(): Promise<void> {
    const res = await fetch(`/api/chat/sessions/${encodeURIComponent(this.sessionId)}/cancel`, {
      method: "POST",
      headers: authHeaders(),
    });
    if (!res.ok) throw new Error(`cancel: ${res.status}`);
  }
}

function parseFrame(frame: string): ChatEvent | null {
  let event = "message";
  let data = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith(":")) continue; // comment / keepalive
    const colon = line.indexOf(":");
    if (colon < 0) continue;
    const field = line.slice(0, colon);
    const val = line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") event = val;
    else if (field === "data") data = data ? data + "\n" + val : val;
  }
  if (!data) return null;
  let payload: Record<string, unknown> = {};
  try { payload = JSON.parse(data); } catch { return null; }
  return { type: event, ...payload } as unknown as ChatEvent;
}
