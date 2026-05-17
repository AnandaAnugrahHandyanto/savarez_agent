import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { MessageSquare, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  ChatClient,
  createSession,
  loadStoredSession,
  clearStoredSession,
  getMessages,
  type ChatEvent,
} from "@/lib/chat";
import { MessageItem, type ChatItem } from "@/components/chat/Message";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { ApprovalDialog } from "@/components/chat/ApprovalDialog";

/* ------------------------------------------------------------------ */
/*  Reducer: SSE events → ChatItem[] state                              */
/* ------------------------------------------------------------------ */

type Action =
  | { type: "push-user"; text: string }
  | { type: "push-user-slash"; text: string }  // user typed /something; no assistant placeholder
  | { type: "event"; e: ChatEvent }
  | { type: "reset" }
  | { type: "set"; items: ChatItem[] };

function itemsReducer(items: ChatItem[], action: Action): ChatItem[] {
  switch (action.type) {
    case "reset":
      return [];
    case "set":
      return action.items;
    case "push-user":
      // Push a pending assistant placeholder right after the user message
      // so the user sees "thinking…" immediately.
      return [
        ...items,
        { id: id(), kind: "user", text: action.text },
        { id: id(), kind: "assistant", text: "", pending: true },
      ];
    case "push-user-slash":
      // Slash commands don't trigger an agent turn — no assistant placeholder.
      return [
        ...items,
        { id: id(), kind: "user", text: action.text },
      ];
    case "event": {
      const e = action.e;
      switch (e.type) {
        case "turn-start":
          return items;  // already pushed a placeholder
        case "text-delta": {
          // Append delta to the most recent pending assistant message,
          // OR start a new assistant message if the last item is a tool.
          const last = items[items.length - 1];
          if (last && last.kind === "assistant") {
            const updated = { ...last, text: last.text + e.delta, pending: false };
            return [...items.slice(0, -1), updated];
          }
          return [...items, { id: id(), kind: "assistant", text: e.delta }];
        }
        case "tool-call-start": {
          // End any pending assistant placeholder.
          const next = items.map((it) =>
            it.kind === "assistant" && it.pending ? { ...it, pending: false } : it,
          );
          return [
            ...next,
            {
              id: id(),
              kind: "tool",
              callId: e.call_id || id(),
              tool: e.tool,
              args: e.args_summary || "",
              status: "running",
            },
          ];
        }
        case "tool-call-result": {
          return items.map((it) => {
            if (it.kind === "tool" && it.callId === e.call_id) {
              return { ...it, status: e.ok ? "ok" : "failed", summary: e.summary } as ChatItem;
            }
            return it;
          });
        }
        case "turn-end": {
          // If no text-delta fired (non-streaming providers / errors), the
          // assistant message might still be empty — fill it from final_text.
          const out: ChatItem[] = [];
          let filled = false;
          for (let i = items.length - 1; i >= 0; i--) {
            const it = items[i];
            if (!filled && it.kind === "assistant" && (it.pending || !it.text)) {
              out.unshift({ ...it, text: e.final_text || it.text, pending: false });
              filled = true;
            } else {
              out.unshift(it);
            }
          }
          if (!filled && e.final_text) {
            out.push({ id: id(), kind: "assistant", text: e.final_text });
          }
          return out;
        }
        case "error":
          return [
            ...items.map((it) =>
              it.kind === "assistant" && it.pending ? { ...it, pending: false } : it,
            ),
            { id: id(), kind: "error", detail: e.detail },
          ];
        case "system-message":
          return [...items, { id: id(), kind: "system", detail: e.detail }];
        default:
          return items;
      }
    }
  }
}

let _idc = 0;
function id() { return `it-${Date.now()}-${_idc++}`; }

/* ------------------------------------------------------------------ */
/*  Page                                                                */
/* ------------------------------------------------------------------ */

interface PendingApproval {
  callId: string;
  command: string;
  description: string;
  allowPermanent: boolean;
}

export default function ChatPage() {
  const [items, dispatch] = useReducer(itemsReducer, []);
  const [draft, setDraft] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [connError, setConnError] = useState<string | null>(null);
  const [approval, setApproval] = useState<PendingApproval | null>(null);
  const clientRef = useRef<ChatClient | null>(null);
  const scrollerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new items.
  useEffect(() => {
    const el = scrollerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [items]);

  // Bootstrap: reattach or create a session.
  useEffect(() => {
    let cancelled = false;
    async function init() {
      let sid = loadStoredSession();
      if (sid) {
        // Reattach — try to load persisted history first.
        try {
          await getMessages(sid);  // 404 → fall through to fresh
        } catch {
          sid = null;
        }
      }
      if (!sid) {
        try {
          sid = await createSession();
        } catch (err) {
          if (!cancelled) setConnError(err instanceof Error ? err.message : String(err));
          return;
        }
      }
      if (cancelled) return;
      setSessionId(sid);
      const client = new ChatClient(sid);
      clientRef.current = client;
      const off = client.on(handleEvent);
      client.connect().catch((e) => {
        if (!cancelled) setConnError(e instanceof Error ? e.message : String(e));
      });
      return () => off();
    }
    init();
    return () => {
      cancelled = true;
      clientRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleEvent = useCallback((e: ChatEvent) => {
    if (e.type === "status" && e.kind === "connected") {
      setConnError(null);
      return;
    }
    if (e.type === "turn-start") {
      setBusy(true);
    }
    if (e.type === "turn-end" || e.type === "error") {
      setBusy(false);
    }
    if (e.type === "approval-request") {
      setApproval({
        callId: e.call_id || "",
        command: e.command,
        description: e.description,
        allowPermanent: e.allow_permanent !== false,
      });
      // Don't dispatch this as a chat item — it shows as a modal instead.
      return;
    }
    dispatch({ type: "event", e });
  }, []);

  const handleApprovalDecision = useCallback(
    async (decision: "once" | "session" | "always" | "deny") => {
      const pending = approval;
      setApproval(null);
      if (!pending || !clientRef.current) return;
      try {
        await clientRef.current.approve(pending.callId, decision);
      } catch (err) {
        dispatch({
          type: "event",
          e: { type: "error", detail: err instanceof Error ? err.message : String(err) },
        });
      }
    },
    [approval],
  );

  const handleSend = async () => {
    const text = draft.trim();
    if (!text || !clientRef.current || busy) return;
    const isSlash = text.startsWith("/");
    setDraft("");
    if (isSlash) {
      // Slash commands are handled server-side without an agent turn,
      // so we don't enter busy mode and we don't push an assistant placeholder.
      dispatch({ type: "push-user-slash", text });
    } else {
      dispatch({ type: "push-user", text });
      setBusy(true);
    }
    try {
      await clientRef.current.send(text);
    } catch (err) {
      if (!isSlash) setBusy(false);
      dispatch({
        type: "event",
        e: { type: "error", detail: err instanceof Error ? err.message : String(err) },
      });
    }
  };

  const handleCancel = async () => {
    try {
      await clientRef.current?.cancel();
    } catch (err) {
      console.warn("[chat] cancel failed", err);
    }
  };

  const handleNew = async () => {
    clientRef.current?.close();
    clientRef.current = null;
    clearStoredSession();
    dispatch({ type: "reset" });
    setSessionId(null);
    setBusy(false);
    try {
      const sid = await createSession();
      setSessionId(sid);
      const client = new ChatClient(sid);
      clientRef.current = client;
      client.on(handleEvent);
      client.connect().catch((e) => setConnError(e instanceof Error ? e.message : String(e)));
    } catch (err) {
      setConnError(err instanceof Error ? err.message : String(err));
    }
  };

  const sessionLabel = useMemo(
    () => (sessionId ? sessionId.slice(0, 8) : "—"),
    [sessionId],
  );

  return (
    <div className="flex flex-col h-full min-h-[calc(100vh-9rem)] max-h-[calc(100vh-7rem)]">
      <div className="flex items-center justify-between gap-2 pb-2 border-b border-border mb-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <MessageSquare className="h-4 w-4" />
          <span>Chat</span>
          <code className="text-xs bg-muted/50 px-1.5 py-0.5 rounded">{sessionLabel}</code>
        </div>
        <Button variant="ghost" size="sm" onClick={handleNew} title="New chat" aria-label="New chat">
          <Plus className="h-3.5 w-3.5 mr-1.5" />
          New
        </Button>
      </div>

      {connError && (
        <div className="mb-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          Connection error: {connError}
        </div>
      )}

      <div ref={scrollerRef} className="flex-1 overflow-y-auto flex flex-col gap-3 py-2 pr-1">
        {items.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground gap-2">
            <MessageSquare className="h-8 w-8 opacity-40" />
            <span className="text-sm">Send a message to start chatting with Hermes.</span>
          </div>
        ) : (
          items.map((it) => <MessageItem key={it.id} item={it} />)
        )}
      </div>

      <div className="pt-3 mt-auto">
        <ChatComposer
          value={draft}
          onChange={setDraft}
          onSend={handleSend}
          onCancel={handleCancel}
          busy={busy}
          disabled={!sessionId || approval !== null}
        />
      </div>

      {approval && (
        <ApprovalDialog
          callId={approval.callId}
          command={approval.command}
          description={approval.description}
          allowPermanent={approval.allowPermanent}
          onDecide={handleApprovalDecision}
        />
      )}
    </div>
  );
}
