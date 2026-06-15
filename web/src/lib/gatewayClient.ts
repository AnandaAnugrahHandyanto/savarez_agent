/**
 * Browser WebSocket client for the tui_gateway JSON-RPC protocol.
 *
 * Speaks the exact same newline-delimited JSON-RPC dialect that the Ink TUI
 * drives over stdio. The server-side transport abstraction
 * (tui_gateway/transport.py + ws.py) routes the same dispatcher's writes
 * onto either stdout or a WebSocket depending on how the client connected.
 */

import { HERMES_BASE_PATH, getWsTicket } from "@/lib/api";

export type GatewayEventName =
  | "gateway.ready"
  | "session.info"
  | "message.start"
  | "message.delta"
  | "message.complete"
  | "thinking.delta"
  | "reasoning.delta"
  | "reasoning.available"
  | "status.update"
  | "tool.start"
  | "tool.progress"
  | "tool.complete"
  | "tool.generating"
  | "clarify.request"
  | "approval.request"
  | "sudo.request"
  | "secret.request"
  | "background.complete"
  | "error"
  | "skin.changed"
  | (string & {});

export interface GatewayEvent<P = unknown> {
  type: GatewayEventName;
  session_id?: string;
  payload?: P;
}

export type ConnectionState =
  | "idle"
  | "connecting"
  | "open"
  | "closed"
  | "error";

interface Pending {
  resolve: (v: unknown) => void;
  reject: (e: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

export interface GatewayClientOptions {
  connectTimeoutMs?: number;
  requestTimeoutMs?: number;
  /** Called when the socket closes unexpectedly (not via close()). */
  onDisconnect?: () => void;
}

const DEFAULT_REQUEST_TIMEOUT_MS = 120_000;
const DEFAULT_CONNECT_TIMEOUT_MS = 15_000;

/** Wildcard listener key: subscribe to every event regardless of type. */
const ANY = "*";

async function buildWsUrl(token?: string): Promise<string> {
  let authParamName: string;
  let authParamValue: string;
  if (token) {
    authParamName = "token";
    authParamValue = token;
  } else if (window.__HERMES_AUTH_REQUIRED__) {
    const { ticket } = await getWsTicket();
    authParamName = "ticket";
    authParamValue = ticket;
  } else {
    authParamName = "token";
    authParamValue = window.__HERMES_SESSION_TOKEN__ ?? "";
    if (!authParamValue) {
      throw new Error(
        "Session token not available — page must be served by the Hermes dashboard",
      );
    }
  }

  const scheme = location.protocol === "https:" ? "wss:" : "ws:";
  return `${scheme}//${location.host}${HERMES_BASE_PATH}/api/ws?${authParamName}=${encodeURIComponent(authParamValue)}`;
}

export class GatewayClient {
  private ws: WebSocket | null = null;
  private reqId = 0;
  private pending = new Map<string, Pending>();
  private listeners = new Map<string, Set<(ev: GatewayEvent) => void>>();
  private _state: ConnectionState = "idle";
  private stateListeners = new Set<(s: ConnectionState) => void>();
  private readonly connectTimeoutMs: number;
  private readonly requestTimeoutMs: number;
  private readonly onDisconnect?: () => void;
  private intentionalClose = false;
  /** Shared in-flight connect — concurrent callers must await the same attempt. */
  private connectPromise: Promise<void> | null = null;

  constructor(options: GatewayClientOptions = {}) {
    this.connectTimeoutMs =
      options.connectTimeoutMs ?? DEFAULT_CONNECT_TIMEOUT_MS;
    this.requestTimeoutMs =
      options.requestTimeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS;
    this.onDisconnect = options.onDisconnect;
  }

  get state(): ConnectionState {
    return this._state;
  }

  private setState(s: ConnectionState) {
    if (this._state === s) return;
    this._state = s;
    for (const cb of this.stateListeners) cb(s);
  }

  onState(cb: (s: ConnectionState) => void): () => void {
    this.stateListeners.add(cb);
    cb(this._state);
    return () => this.stateListeners.delete(cb);
  }

  /** Subscribe to a specific event type. Returns an unsubscribe function. */
  on<P = unknown>(
    type: GatewayEventName,
    cb: (ev: GatewayEvent<P>) => void,
  ): () => void {
    let set = this.listeners.get(type);
    if (!set) {
      set = new Set();
      this.listeners.set(type, set);
    }
    set.add(cb as (ev: GatewayEvent) => void);
    return () => set!.delete(cb as (ev: GatewayEvent) => void);
  }

  /** Subscribe to every event (fires after type-specific listeners). */
  onAny(cb: (ev: GatewayEvent) => void): () => void {
    return this.on(ANY as GatewayEventName, cb);
  }

  async connect(token?: string): Promise<void> {
    if (this._state === "open") return;
    if (this.connectPromise) return this.connectPromise;

    this.intentionalClose = false;
    this.connectPromise = this.openConnection(token).finally(() => {
      this.connectPromise = null;
    });
    return this.connectPromise;
  }

  private async openConnection(token?: string): Promise<void> {
    this.setState("connecting");

    const url = await buildWsUrl(token);
    const ws = new WebSocket(url);
    this.ws = ws;

    ws.addEventListener("message", (ev) => {
      if (this.ws !== ws) return;
      try {
        this.dispatch(JSON.parse(ev.data));
      } catch {
        /* malformed frame — ignore */
      }
    });

    ws.addEventListener("close", () => {
      if (this.ws !== ws) return;
      this.ws = null;
      this.setState("closed");
      this.rejectAllPending(new Error("WebSocket closed"));
      if (!this.intentionalClose) {
        this.onDisconnect?.();
      }
    });

    await new Promise<void>((resolve, reject) => {
      let settled = false;
      let timer: ReturnType<typeof setTimeout> | undefined;

      const cleanup = () => {
        if (timer !== undefined) clearTimeout(timer);
        ws.removeEventListener("open", onOpen);
        ws.removeEventListener("error", onError);
      };

      const onOpen = () => {
        if (settled || this.ws !== ws) return;
        settled = true;
        cleanup();
        this.setState("open");
        resolve();
      };

      const onError = () => {
        if (settled || this.ws !== ws) return;
        settled = true;
        cleanup();
        if (this.ws === ws) {
          try {
            ws.close();
          } catch {
            /* ignore */
          }
          this.ws = null;
        }
        this.setState("error");
        reject(new Error("WebSocket connection failed"));
      };

      ws.addEventListener("open", onOpen, { once: true });
      ws.addEventListener("error", onError, { once: true });

      if (this.connectTimeoutMs > 0) {
        timer = setTimeout(() => {
          if (settled) return;
          settled = true;
          cleanup();
          if (this.ws === ws) {
            try {
              ws.close();
            } catch {
              /* ignore */
            }
            this.ws = null;
          }
          this.setState("error");
          reject(new Error("WebSocket connection failed"));
        }, this.connectTimeoutMs);
      }
    });
  }

  close() {
    this.intentionalClose = true;
    this.ws?.close();
    this.ws = null;
    this.setState("closed");
  }

  private dispatch(msg: Record<string, unknown>) {
    const id = msg.id as string | undefined;

    if (id !== undefined && this.pending.has(id)) {
      const p = this.pending.get(id)!;
      this.pending.delete(id);
      clearTimeout(p.timer);

      const err = msg.error as { message?: string } | undefined;
      if (err) p.reject(new Error(err.message ?? "request failed"));
      else p.resolve(msg.result);
      return;
    }

    if (msg.method !== "event") return;

    const params = (msg.params ?? {}) as GatewayEvent;
    if (typeof params.type !== "string") return;

    for (const cb of this.listeners.get(params.type) ?? []) cb(params);
    for (const cb of this.listeners.get(ANY) ?? []) cb(params);
  }

  private rejectAllPending(err: Error) {
    for (const p of this.pending.values()) {
      clearTimeout(p.timer);
      p.reject(err);
    }
    this.pending.clear();
  }

  /** Send a JSON-RPC request. Rejects on error response or timeout. */
  request<T = unknown>(
    method: string,
    params: Record<string, unknown> = {},
    timeoutMs = this.requestTimeoutMs,
  ): Promise<T> {
    if (!this.ws || this._state !== "open") {
      return Promise.reject(
        new Error(`gateway not connected (state=${this._state})`),
      );
    }

    const id = `w${++this.reqId}`;

    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        if (this.pending.delete(id)) {
          reject(new Error(`request timed out: ${method}`));
        }
      }, timeoutMs);

      this.pending.set(id, {
        resolve: (v) => resolve(v as T),
        reject,
        timer,
      });

      try {
        this.ws!.send(JSON.stringify({ jsonrpc: "2.0", id, method, params }));
      } catch (e) {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(e instanceof Error ? e : new Error(String(e)));
      }
    });
  }
}

declare global {
  interface Window {
    __HERMES_SESSION_TOKEN__?: string;
    __HERMES_AUTH_REQUIRED__?: boolean;
  }
}
