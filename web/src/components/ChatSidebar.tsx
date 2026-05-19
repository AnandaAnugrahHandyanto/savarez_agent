/**
 * ChatSidebar sits next to the embedded Hermes terminal.
 *
 * The main user-facing job is navigation: projects, ordinary chats, and
 * concrete sessions. Tool telemetry is intentionally hidden from the primary
 * layout so the sidebar can behave more like Codex's conversation rail.
 */

import { Button } from "@nous-research/ui/ui/components/button";
import { AlertCircle, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { ChatSessionNavigator } from "@/components/ChatSessionNavigator";
import type { EventsState } from "@/components/chat-events-status";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ChatSidebarProps {
  channel: string;
  activeSessionId?: string | null;
  className?: string;
  onEventsStateChange?: (state: EventsState) => void;
}

export function ChatSidebar({
  channel,
  activeSessionId = null,
  className,
  onEventsStateChange,
}: ChatSidebarProps) {
  const [version, setVersion] = useState(0);
  const [eventsState, setEventsState] = useState<EventsState>("connecting");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    onEventsStateChange?.(eventsState);
  }, [eventsState, onEventsStateChange]);

  useEffect(() => {
    const token = window.__HERMES_SESSION_TOKEN__;

    if (!token || !channel) {
      return;
    }

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const qs = new URLSearchParams({ token, channel });
    const ws = new WebSocket(
      `${proto}//${window.location.host}/api/events?${qs.toString()}`,
    );

    const DISCONNECTED = "events feed disconnected";
    let unmounting = false;
    const surface = (msg: string, nextState: EventsState = "error") => {
      if (unmounting) return;
      setEventsState(nextState);
      setError(msg);
    };

    ws.addEventListener("open", () => {
      if (unmounting) return;
      setEventsState("live");
      setError(null);
    });

    ws.addEventListener("error", () => surface(DISCONNECTED));

    ws.addEventListener("close", (ev) => {
      if (unmounting) return;
      if (ev.code === 4401 || ev.code === 4403) {
        surface(`events feed rejected (${ev.code}); reload the page`);
      } else if (ev.code !== 1000) {
        surface(DISCONNECTED);
      } else {
        setEventsState("closed");
      }
    });

    return () => {
      unmounting = true;
      ws.close();
    };
  }, [channel, version]);

  const reconnect = useCallback(() => {
    setError(null);
    setEventsState("connecting");
    setVersion((v) => v + 1);
  }, []);

  return (
    <aside
      className={cn(
        "flex h-full w-full min-w-0 shrink-0 flex-col gap-3 overflow-y-auto overflow-x-hidden pr-1 normal-case lg:w-[28rem] xl:w-[30rem]",
        className,
      )}
    >
      <ChatSessionNavigator
        activeSessionId={activeSessionId}
        className="min-h-0 flex-1"
      />

      {error && (
        <Card className="flex items-start gap-2 border-destructive/40 bg-destructive/5 px-3 py-2 text-xs">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />

          <div className="min-w-0 flex-1">
            <div className="wrap-break-word text-destructive">{error}</div>

            <Button
              size="sm"
              outlined
              className="mt-1"
              onClick={reconnect}
              prefix={<RefreshCw />}
            >
              reconnect
            </Button>
          </div>
        </Card>
      )}
    </aside>
  );
}
