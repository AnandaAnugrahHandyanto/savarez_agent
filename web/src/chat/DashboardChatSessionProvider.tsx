import { api } from "@/lib/api";
import { GatewayClient } from "@/lib/gatewayClient";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useSearchParams } from "react-router-dom";

import { stripResumeParam, withResumeSession } from "@/lib/chatResumeUrl";
import { useProfileScope } from "@/contexts/useProfileScope";

import {
  ChatSessionProvider,
  type ChatSessionContextValue,
} from "./ChatSessionContext";
import type { ChatMessage } from "./chatMessages";
import { SessionCommandPalette } from "./SessionCommandPalette";
import { useChatGateway } from "./useChatGateway";
import { useSessionList } from "./useSessionList";

export type DashboardChatSurface = "rich" | "terminal";

const SurfaceContext = createContext<DashboardChatSurface | null>(null);

export function useDashboardChatSurface(): DashboardChatSurface | null {
  return useContext(SurfaceContext);
}

interface Props {
  isActive: boolean;
  children: ReactNode;
}

function useMgmtGateway(enabled: boolean) {
  const [version, setVersion] = useState(0);
  const gw = useMemo(
    () => new GatewayClient(),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [version],
  );

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;

    const connect = async () => {
      try {
        if (gw.state !== "open") await gw.connect();
      } catch {
        if (!cancelled) setVersion((v) => v + 1);
      }
    };

    void connect();

    return () => {
      cancelled = true;
      gw.close();
    };
  }, [enabled, gw, version]);

  return gw;
}

function useGlobalPaletteShortcut(isActive: boolean, toggle: () => void) {
  useEffect(() => {
    if (!isActive) return;

    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        toggle();
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isActive, toggle]);
}

function RichSessionProvider({
  isActive,
  paletteOpen,
  onPaletteOpenChange,
  children,
}: {
  isActive: boolean;
  paletteOpen: boolean;
  onPaletteOpenChange: (open: boolean) => void;
  children: ReactNode;
}) {
  const { profile } = useProfileScope();
  const [searchParams] = useSearchParams();
  const resumeSessionId = searchParams.get("resume");
  const hydrateListenersRef = useRef(new Set<(messages: ChatMessage[]) => void>());

  const registerOnHydrated = useCallback(
    (fn: (messages: ChatMessage[]) => void) => {
      hydrateListenersRef.current.add(fn);
      return () => {
        hydrateListenersRef.current.delete(fn);
      };
    },
    [],
  );

  const gateway = useChatGateway({
    profile,
    isActive,
    onHydrated: (messages) => {
      for (const fn of hydrateListenersRef.current) {
        fn(messages);
      }
    },
  });

  const mgmtGw = useMgmtGateway(isActive);

  const sessionList = useSessionList({
    gw: mgmtGw,
    sessionId: gateway.sessionId,
    enabled: isActive,
  });

  const openSessionPalette = useCallback(
    () => onPaletteOpenChange(true),
    [onPaletteOpenChange],
  );

  const contextValue: ChatSessionContextValue = {
    gw: gateway.gw,
    sessionId: gateway.sessionId,
    sessionIdRef: gateway.sessionIdRef,
    storedSessionId: gateway.storedSessionId,
    resumeSessionId,
    sessionInfo: gateway.sessionInfo,
    connectionState: gateway.connectionState,
    error: gateway.error,
    sessionEnded: gateway.sessionEnded,
    request: gateway.request,
    startNewChat: gateway.startNewChat,
    activateLiveSession: gateway.activateLiveSession,
    resumeStoredSession: gateway.resumeStoredSession,
    forkFromMessages: gateway.forkFromMessages,
    surface: "rich",
    sessionList,
    registerOnHydrated,
    openSessionPalette,
    chatTitle:
      gateway.sessionInfo.title ??
      sessionList.history.find((s) => s.id === resumeSessionId)?.title,
  };

  return (
    <ChatSessionProvider value={contextValue}>
      {children}
      <SessionCommandPalette
        open={paletteOpen}
        onClose={() => onPaletteOpenChange(false)}
      />
    </ChatSessionProvider>
  );
}

function TerminalSessionProvider({
  isActive,
  paletteOpen,
  onPaletteOpenChange,
  children,
}: {
  isActive: boolean;
  paletteOpen: boolean;
  onPaletteOpenChange: (open: boolean) => void;
  children: ReactNode;
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const resumeSessionId = searchParams.get("resume");

  const mgmtGw = useMgmtGateway(isActive);

  const sessionList = useSessionList({
    gw: mgmtGw,
    sessionId: null,
    enabled: isActive,
  });

  const resumeStoredSession = useCallback(
    (storedId: string) => {
      setSearchParams((prev) => withResumeSession(prev, storedId), {
        replace: true,
      });
    },
    [setSearchParams],
  );

  const startNewChat = useCallback(() => {
    setSearchParams((prev) => stripResumeParam(prev), {
      replace: true,
    });
  }, [setSearchParams]);

  const request = useCallback(
    <T,>(method: string, params: Record<string, unknown> = {}) =>
      mgmtGw.request<T>(method, params),
    [mgmtGw],
  );

  const openSessionPalette = useCallback(
    () => onPaletteOpenChange(true),
    [onPaletteOpenChange],
  );

  const contextValue: ChatSessionContextValue = {
    gw: mgmtGw,
    sessionId: null,
    storedSessionId: resumeSessionId,
    resumeSessionId,
    sessionInfo: {},
    connectionState: mgmtGw.state,
    error: null,
    sessionEnded: false,
    request,
    startNewChat,
    resumeStoredSession,
    surface: "terminal",
    sessionList,
    openSessionPalette,
    chatTitle:
      sessionList.history.find((s) => s.id === resumeSessionId)?.title ??
      sessionList.live.find(
        (s) => s.id === resumeSessionId || s.session_key === resumeSessionId,
      )?.title,
  };

  return (
    <ChatSessionProvider value={contextValue}>
      {children}
      <SessionCommandPalette
        open={paletteOpen}
        onClose={() => onPaletteOpenChange(false)}
      />
    </ChatSessionProvider>
  );
}

export function DashboardChatSessionProvider({ isActive, children }: Props) {
  const [surface, setSurface] = useState<DashboardChatSurface | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getConfig()
      .then((cfg) => {
        if (cancelled) return;
        const raw = (cfg.display as { dashboard_chat_surface?: string } | undefined)
          ?.dashboard_chat_surface;
        setSurface(raw === "rich" ? "rich" : "terminal");
      })
      .catch(() => {
        if (!cancelled) setSurface("terminal");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onPaletteOpenChange = useCallback((open: boolean) => {
    setPaletteOpen(open);
  }, []);

  const togglePalette = useCallback(() => {
    setPaletteOpen((open) => !open);
  }, []);

  useGlobalPaletteShortcut(isActive, togglePalette);

  if (!surface) {
    return (
      <SurfaceContext.Provider value={null}>{children}</SurfaceContext.Provider>
    );
  }

  const inner =
    surface === "terminal" ? (
      <TerminalSessionProvider
        isActive={isActive}
        paletteOpen={paletteOpen}
        onPaletteOpenChange={onPaletteOpenChange}
      >
        {children}
      </TerminalSessionProvider>
    ) : (
      <RichSessionProvider
        isActive={isActive}
        paletteOpen={paletteOpen}
        onPaletteOpenChange={onPaletteOpenChange}
      >
        {children}
      </RichSessionProvider>
    );

  return (
    <SurfaceContext.Provider value={surface}>{inner}</SurfaceContext.Provider>
  );
}

export function DashboardChatSurfaceGate({
  children,
  fallback,
}: {
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const surface = useDashboardChatSurface();
  if (!surface) {
    return (
      fallback ?? (
        <div className="flex flex-1 items-center justify-center p-8">
          <Spinner />
        </div>
      )
    );
  }
  return children;
}
