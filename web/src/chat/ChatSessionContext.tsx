import type { GatewayClient, ConnectionState } from "@/lib/gatewayClient";
import type { BranchSeedMessage } from "@/lib/chatBranch";
import {
  createContext,
  useContext,
  type MutableRefObject,
  type ReactNode,
} from "react";

import type { ChatMessage } from "./chatMessages";
import type { SessionInfo } from "./useMessageStream";
import type { UseSessionListResult } from "./useSessionListTypes";

export interface ChatSessionContextValue {
  gw: GatewayClient | null;
  sessionId: string | null;
  /** Runtime session id — updated synchronously before transcript hydration. */
  sessionIdRef?: MutableRefObject<string | null>;
  storedSessionId: string | null;
  resumeSessionId: string | null;
  sessionInfo: SessionInfo;
  connectionState: ConnectionState;
  error: string | null;
  sessionEnded: boolean;
  request: <T>(
    method: string,
    params?: Record<string, unknown>,
  ) => Promise<T>;
  startNewChat: () => void;
  /** Switch focus to an in-memory session (runtime id from session.active_list). */
  activateLiveSession?: (runtimeId: string) => void;
  /** Resume a stored session row (DB id from session.list). */
  resumeStoredSession?: (storedId: string) => void;
  surface: "rich" | "terminal";
  sessionList: UseSessionListResult;
  registerOnHydrated?: (fn: (messages: ChatMessage[]) => void) => () => void;
  openSessionPalette?: () => void;
  chatTitle?: string;
  forkFromMessages?: (
    seedMessages: BranchSeedMessage[],
    opts?: { title?: string; displayMessages?: ChatMessage[] },
  ) => Promise<unknown>;
}

const ChatSessionContext = createContext<ChatSessionContextValue | null>(null);

export function ChatSessionProvider({
  value,
  children,
}: {
  value: ChatSessionContextValue;
  children: ReactNode;
}) {
  return (
    <ChatSessionContext.Provider value={value}>
      {children}
    </ChatSessionContext.Provider>
  );
}

export function useChatSession(): ChatSessionContextValue {
  const ctx = useContext(ChatSessionContext);
  if (!ctx) {
    throw new Error("useChatSession must be used within ChatSessionProvider");
  }
  return ctx;
}

export function useOptionalChatSession(): ChatSessionContextValue | null {
  return useContext(ChatSessionContext);
}
