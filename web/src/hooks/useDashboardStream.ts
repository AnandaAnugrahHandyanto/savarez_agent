import { useEffect, useRef, useState } from "react";
import type { DashboardState } from "@/lib/api";

export function useDashboardStream() {
  const [state, setState] = useState<DashboardState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const retryRef = useRef<number | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const connect = () => {
      if (retryRef.current) {
        window.clearTimeout(retryRef.current);
        retryRef.current = null;
      }
      setError(null);
      const es = new EventSource("/api/dashboard/stream");
      esRef.current = es;

      es.onmessage = (evt) => {
        try {
          const parsed = JSON.parse(evt.data) as DashboardState;
          setState(parsed);
        } catch (e) {
          setError(String(e));
        }
      };

      es.onerror = () => {
        es.close();
        esRef.current = null;
        if (!retryRef.current) {
          retryRef.current = window.setTimeout(connect, 1500);
        }
      };
    };

    connect();
    return () => {
      if (retryRef.current) window.clearTimeout(retryRef.current);
      retryRef.current = null;
      esRef.current?.close();
      esRef.current = null;
    };
  }, []);

  return { state, error };
}

