import type { GatewayClient } from "@/lib/gatewayClient";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  resumableHistory,
  type SessionActiveItem,
  type SessionActiveListResponse,
  type SessionListItem,
  type SessionListResponse,
} from "./sessionListCore";
import type { UseSessionListResult } from "./useSessionListTypes";

const POLL_MS = 5_000;

export interface UseSessionListOptions {
  gw: GatewayClient | null;
  sessionId: string | null;
  enabled?: boolean;
}

export function useSessionList({
  gw,
  sessionId,
  enabled = true,
}: UseSessionListOptions): UseSessionListResult {
  const [live, setLive] = useState<SessionActiveItem[]>([]);
  const [history, setHistory] = useState<SessionListItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rawHistoryRef = useRef<SessionListItem[]>([]);

  const refresh = useCallback(async () => {
    if (!gw || gw.state !== "open" || !enabled) return;

    setLoading((prev) => (live.length === 0 && history.length === 0 ? true : prev));
    setError(null);

    try {
      const [liveRes, histRes] = await Promise.allSettled([
        gw.request<SessionActiveListResponse>("session.active_list", {
          current_session_id: sessionId ?? "",
        }),
        gw.request<SessionListResponse>("session.list", { limit: 200 }),
      ]);

      let nextLive: SessionActiveItem[] = [];
      if (liveRes.status === "fulfilled") {
        nextLive = liveRes.value.sessions ?? [];
        setLive(nextLive);
      }

      if (histRes.status === "fulfilled") {
        rawHistoryRef.current = histRes.value.sessions ?? [];
      } else if (rawHistoryRef.current.length === 0) {
        setError("Could not load session history");
      }

      setHistory(resumableHistory(rawHistoryRef.current, nextLive));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [gw, sessionId, enabled, live.length, history.length]);

  useEffect(() => {
    if (!gw || !enabled) return;

    let cancelled = false;

    const tryRefresh = () => {
      if (cancelled || gw.state !== "open") return;
      void refresh();
    };

    tryRefresh();

    const offState = gw.onState((state) => {
      if (state === "open") tryRefresh();
    });

    const offComplete = gw.on("message.complete", () => {
      void refresh();
    });

    const timer = window.setInterval(() => {
      void refresh();
    }, POLL_MS);

    return () => {
      cancelled = true;
      offState();
      offComplete();
      window.clearInterval(timer);
    };
  }, [gw, enabled, refresh]);

  return { live, history, loading, error, refresh };
}
