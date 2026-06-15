import { api } from "@/lib/api";
import { GatewayClient, type ConnectionState } from "@/lib/gatewayClient";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import {
  appendInflightToMessages,
  toChatMessagesFromGateway,
  toChatMessagesFromRest,
  type ChatMessage,
  type SessionInflightTurn,
} from "./chatMessages";
import { stripResumeParam, withResumeSession } from "@/lib/chatResumeUrl";
import type { BranchSeedMessage } from "@/lib/chatBranch";
import type { SessionInfo } from "./useMessageStream";
import { useResolvedResumeParam } from "./useResolvedResumeParam";

interface SessionResumeResponse {
  session_id: string;
  stored_session_id?: string;
  resumed?: string;
  running?: boolean;
  info?: SessionInfo;
  messages?: unknown[];
  inflight?: SessionInflightTurn | null;
}

interface SessionActivateResponse {
  session_id: string;
  session_key?: string;
  running?: boolean;
  status?: string;
  info?: SessionInfo;
  messages?: unknown[];
  inflight?: SessionInflightTurn | null;
}

interface SessionCreateResponse {
  session_id: string;
  stored_session_id?: string;
  messages?: unknown[];
  info?: SessionInfo;
}

/** How the gateway should attach on this bind pass. */
type BindIntent =
  | { type: "create" }
  | { type: "resume"; storedId: string }
  | { type: "reattach"; runtimeId: string };

const MAX_RECONNECT_ATTEMPTS = 8;

function reconnectDelayMs(attempt: number): number {
  return Math.min(15_000, 1_000 * 2 ** Math.min(attempt, 4));
}

export interface UseChatGatewayOptions {
  profile: string;
  /** When false, defer session.create/resume until the user opens /chat. */
  isActive?: boolean;
  onHydrated?: (messages: ChatMessage[]) => void;
  onSessionInfo?: (info: SessionInfo) => void;
}

function hydrateSessionMessages(
  restMessages: ChatMessage[] | null | undefined,
  gatewayMessages: unknown[] | null | undefined,
  inflight?: SessionInflightTurn | null,
): ChatMessage[] {
  let base: ChatMessage[] = [];
  if (restMessages && restMessages.length > 0) {
    base = restMessages;
  } else if (Array.isArray(gatewayMessages) && gatewayMessages.length > 0) {
    base = toChatMessagesFromGateway(gatewayMessages);
  }
  return appendInflightToMessages(base, inflight);
}

export function useChatGateway({
  profile,
  isActive = true,
  onHydrated,
  onSessionInfo,
}: UseChatGatewayOptions) {
  const [, setSearchParams] = useSearchParams();
  const { resumeParam, targetId, ready: resumeReady } = useResolvedResumeParam(
    profile,
  );

  const [version, setVersion] = useState(0);
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [storedSessionId, setStoredSessionId] = useState<string | null>(null);
  const [sessionInfo, setSessionInfo] = useState<SessionInfo>({});
  const [error, setError] = useState<string | null>(null);
  const [sessionEnded, setSessionEnded] = useState(false);

  const reconnectAttemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wantReconnectRef = useRef(true);
  const bootingRef = useRef(false);
  const storedIdRef = useRef<string | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  /** Set before URL ?resume= sync so the gateway effect skips teardown/rebind. */
  const persistUrlSyncRef = useRef(false);
  /**
   * Set by startNewChat while ?resume= is being cleared. The session-bind
   * effect must not re-resume the old id if the gateway client resets first.
   */
  const suppressResumeBindRef = useRef(false);
  /** Sidebar / session-list pick in flight — bind effect must not compete. */
  const pickInFlightRef = useRef<string | null>(null);
  const resumeParamRef = useRef(resumeParam);
  const onHydratedRef = useRef(onHydrated);
  const onSessionInfoRef = useRef(onSessionInfo);
  const bindSessionRef = useRef<(intent: BindIntent) => Promise<boolean>>(
    () => Promise.resolve(false),
  );

  onHydratedRef.current = onHydrated;
  onSessionInfoRef.current = onSessionInfo;
  sessionIdRef.current = sessionId;
  resumeParamRef.current = resumeParam;

  const sessionInfoRef = useRef(sessionInfo);
  sessionInfoRef.current = sessionInfo;

  /** Only for explicit user actions (session list pick, live activate). */
  const syncResumeUrl = useCallback(
    (storedId: string) => {
      persistUrlSyncRef.current = true;
      setSearchParams((prev) => withResumeSession(prev, storedId), {
        replace: true,
      });
    },
    [setSearchParams],
  );

  const applyActivated = useCallback(
    async (
      activated: SessionActivateResponse,
      opts?: { syncUrl?: boolean },
    ) => {
      const runtime = activated.session_id;
      const stored = activated.session_key ?? storedIdRef.current ?? runtime;
      const running = Boolean(
        activated.running ||
          activated.status === "working" ||
          activated.status === "waiting",
      );

      storedIdRef.current = stored;
      sessionIdRef.current = runtime;
      setSessionId(runtime);
      setStoredSessionId(stored);

      const info = { ...(activated.info ?? {}), running };
      setSessionInfo(info);
      onSessionInfoRef.current?.(info);

      const prefetch = await api
        .getSessionMessages(stored, profile)
        .catch(() => null);

      const restMessages = prefetch?.messages?.length
        ? toChatMessagesFromRest(prefetch.messages)
        : null;
      onHydratedRef.current?.(
        hydrateSessionMessages(
          restMessages,
          activated.messages,
          activated.inflight,
        ),
      );

      if (opts?.syncUrl) {
        syncResumeUrl(stored);
      }
    },
    [profile, syncResumeUrl],
  );

  const gw = useMemo(
    () =>
      new GatewayClient({
        onDisconnect: () => {
          if (!wantReconnectRef.current) return;
          const runtimeId = sessionIdRef.current;
          if (!runtimeId) return;
          if (reconnectAttemptRef.current >= MAX_RECONNECT_ATTEMPTS) {
            setSessionEnded(true);
            setError("Connection lost — session may have ended.");
            return;
          }
          if (reconnectTimerRef.current) return;
          const delay = reconnectDelayMs(reconnectAttemptRef.current);
          reconnectAttemptRef.current += 1;
          reconnectTimerRef.current = setTimeout(() => {
            reconnectTimerRef.current = null;
            void bindSessionRef.current({
              type: "reattach",
              runtimeId,
            });
          }, delay);
        },
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [version],
  );

  const adoptCreatedSession = useCallback(
    (created: SessionCreateResponse, fallbackMessages: ChatMessage[]) => {
      const runtimeId = created.session_id;
      const stored = created.stored_session_id ?? runtimeId;
      storedIdRef.current = stored;
      sessionIdRef.current = runtimeId;
      setSessionId(runtimeId);
      setStoredSessionId(stored);
      setSessionEnded(false);
      setError(null);

      const hydrated =
        Array.isArray(created.messages) && created.messages.length > 0
          ? toChatMessagesFromGateway(created.messages)
          : fallbackMessages;

      onHydratedRef.current?.(hydrated);

      if (created.info) {
        setSessionInfo(created.info);
        onSessionInfoRef.current?.(created.info);
      } else {
        setSessionInfo((prev) => ({ ...prev, running: false }));
      }
    },
    [],
  );

  const forkFromMessages = useCallback(
    async (
      seedMessages: BranchSeedMessage[],
      opts?: { title?: string; displayMessages?: ChatMessage[] },
    ) => {
      if (seedMessages.length === 0) {
        throw new Error("nothing to branch — send a message first");
      }

      if (gw.state !== "open") {
        await gw.connect();
      }

      const cwd = sessionInfoRef.current.cwd?.trim();
      const created = await gw.request<SessionCreateResponse>("session.create", {
        cols: 80,
        messages: seedMessages,
        title: opts?.title?.trim() || "Branch",
        ...(profile ? { profile } : {}),
        ...(cwd ? { cwd } : {}),
      });

      adoptCreatedSession(created, opts?.displayMessages ?? []);
      return created;
    },
    [adoptCreatedSession, gw, profile],
  );

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const bindSession = useCallback(
    async (intent: BindIntent): Promise<boolean> => {
      if (bootingRef.current) return false;
      bootingRef.current = true;
      setError(null);
      setSessionEnded(false);

      try {
        if (gw.state !== "open") {
          await gw.connect();
        }

        reconnectAttemptRef.current = 0;

        if (intent.type === "reattach") {
          const activated = await gw.request<SessionActivateResponse>(
            "session.activate",
            { session_id: intent.runtimeId },
          );
          await applyActivated(activated);
          return true;
        }

        if (intent.type === "resume") {
          const prefetch = api
            .getSessionMessages(intent.storedId, profile)
            .catch(() => null);
          const resumePromise = gw.request<SessionResumeResponse>(
            "session.resume",
            {
              session_id: intent.storedId,
              cols: 80,
              ...(profile ? { profile } : {}),
            },
          );

          const [prefetchResult, resumed] = await Promise.all([
            prefetch,
            resumePromise,
          ]);

          const runtimeId = resumed.session_id;
          const stored = resumed.stored_session_id ?? resumed.resumed ?? intent.storedId;
          storedIdRef.current = stored;
          sessionIdRef.current = runtimeId;
          setStoredSessionId(stored);
          setSessionId(runtimeId);

          const restMessages = prefetchResult?.messages?.length
            ? toChatMessagesFromRest(prefetchResult.messages)
            : null;
          onHydratedRef.current?.(
            hydrateSessionMessages(
              restMessages,
              resumed.messages,
              resumed.inflight,
            ),
          );

          if (resumed.info) {
            setSessionInfo(resumed.info);
            onSessionInfoRef.current?.(resumed.info);
          }

          if (resumed.running) {
            setSessionInfo((prev) => ({ ...prev, running: true }));
          }
          return true;
        }

        const created = await gw.request<SessionCreateResponse>(
          "session.create",
          {
            ...(profile ? { profile } : {}),
          },
        );
        const runtimeId = created.session_id;
        const stored = created.stored_session_id ?? null;
        setSessionId(runtimeId);
        setStoredSessionId(stored);
        storedIdRef.current = stored;
        sessionIdRef.current = runtimeId;
        onHydratedRef.current?.([]);
        return true;
      } catch (e) {
        if (intent.type === "reattach") {
          bootingRef.current = false;
          return bindSessionRef.current({ type: "create" });
        }
        const message = e instanceof Error ? e.message : String(e);
        setError(message);
        return false;
      } finally {
        bootingRef.current = false;
      }
    },
    [gw, profile, applyActivated],
  );

  bindSessionRef.current = bindSession;

  // WebSocket lifecycle — only reconnect when the client instance changes.
  useEffect(() => {
    wantReconnectRef.current = true;
    clearReconnectTimer();

    const offState = gw.onState(setConnectionState);
    const offInfo = gw.on<SessionInfo>("session.info", (ev) => {
      if (ev.payload) {
        setSessionInfo((prev) => ({ ...prev, ...ev.payload }));
        onSessionInfoRef.current?.(ev.payload!);
      }
      if (ev.session_id) {
        sessionIdRef.current = ev.session_id;
        setSessionId(ev.session_id);
      }
    });

    return () => {
      wantReconnectRef.current = false;
      clearReconnectTimer();
      offState();
      offInfo();
      if (persistUrlSyncRef.current) {
        persistUrlSyncRef.current = false;
        return;
      }
      gw.close();
    };
  }, [gw, clearReconnectTimer]);

  // Session bind — URL deep-links and cold resumes; must not close the socket.
  // Deferred until /chat is active so sidebar navigation (which keeps ChatPage
  // mounted but hidden) actually creates a session on first open — matching a
  // full reload at /chat.
  useEffect(() => {
    if (!isActive) return;
    if (!resumeReady) return;

    if (suppressResumeBindRef.current) {
      if (resumeParam) {
        return;
      }
      suppressResumeBindRef.current = false;
      void bindSession({ type: "create" });
      return;
    }

    if (pickInFlightRef.current) {
      return;
    }

    // Validated deep-link (`?resume=` confirmed in session store).
    if (targetId) {
      const alreadyOnThisSession =
        storedIdRef.current === targetId &&
        !!sessionIdRef.current &&
        gw.state === "open";

      if (!alreadyOnThisSession && !bootingRef.current) {
        void bindSession({ type: "resume", storedId: targetId });
      } else if (alreadyOnThisSession) {
        setError(null);
      }
      return;
    }

    // Tab switch back: keep the in-memory live session (no DB resume).
    if (sessionIdRef.current) {
      if (gw.state === "open") {
        return;
      }
      if (bootingRef.current) {
        return;
      }
      void bindSession({
        type: "reattach",
        runtimeId: sessionIdRef.current,
      });
      return;
    }

    if (!bootingRef.current) {
      void bindSession({ type: "create" });
    }
  }, [gw, targetId, resumeReady, resumeParam, profile, bindSession, isActive]);

  const request = useCallback(
    <T,>(method: string, params: Record<string, unknown> = {}) =>
      gw.request<T>(method, params),
    [gw],
  );

  const interrupt = useCallback(async () => {
    if (!sessionId) return;
    await gw.request("session.interrupt", { session_id: sessionId });
    setSessionInfo((prev) => ({ ...prev, running: false }));
  }, [gw, sessionId]);

  const activateLiveSession = useCallback(
    async (runtimeId: string) => {
      if (bootingRef.current) return;
      bootingRef.current = true;
      setError(null);
      setSessionEnded(false);

      try {
        if (gw.state !== "open") {
          await gw.connect();
        }

        const activated = await gw.request<SessionActivateResponse>(
          "session.activate",
          { session_id: runtimeId },
        );

        await applyActivated(activated, { syncUrl: true });
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        setError(message);
      } finally {
        bootingRef.current = false;
      }
    },
    [gw, applyActivated],
  );

  const resumeStoredSession = useCallback(
    async (storedId: string) => {
      const alreadyOnThisSession =
        storedIdRef.current === storedId &&
        !!sessionIdRef.current &&
        gw.state === "open";

      if (alreadyOnThisSession) {
        syncResumeUrl(storedId);
        return;
      }

      pickInFlightRef.current = storedId;
      persistUrlSyncRef.current = true;
      syncResumeUrl(storedId);

      try {
        await bindSession({ type: "resume", storedId });
      } finally {
        pickInFlightRef.current = null;
      }
    },
    [bindSession, gw.state, syncResumeUrl],
  );

  const startNewChat = useCallback(() => {
    suppressResumeBindRef.current = true;
    wantReconnectRef.current = false;
    clearReconnectTimer();
    bootingRef.current = false;
    persistUrlSyncRef.current = false;
    storedIdRef.current = null;
    sessionIdRef.current = null;
    resumeParamRef.current = null;
    reconnectAttemptRef.current = 0;
    setSessionId(null);
    setStoredSessionId(null);
    setSessionInfo({});
    setSessionEnded(false);
    setError(null);
    onHydratedRef.current?.([]);
    setSearchParams((prev) => stripResumeParam(prev), {
      replace: true,
    });
    setVersion((v) => v + 1);
  }, [clearReconnectTimer, setSearchParams]);

  return {
    gw,
    connectionState,
    sessionId,
    sessionIdRef,
    storedSessionId,
    sessionInfo,
    error,
    sessionEnded,
    request,
    interrupt,
    activateLiveSession,
    resumeStoredSession,
    startNewChat,
    forkFromMessages,
  };
}
