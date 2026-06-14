import { ChatRichView } from "@/chat/ChatRichView";
import { ChatShell } from "@/chat/ChatShell";
import { ChatTerminalView } from "@/chat/ChatTerminalView";
import {
  DashboardChatSurfaceGate,
  useDashboardChatSurface,
} from "@/chat/DashboardChatSessionProvider";

export type { DashboardChatSurface } from "@/chat/DashboardChatSessionProvider";

export default function ChatPage({ isActive = true }: { isActive?: boolean }) {
  const surface = useDashboardChatSurface();

  return (
    <DashboardChatSurfaceGate>
      <ChatShell>
        {surface === "terminal" ? (
          <ChatTerminalView isActive={isActive} />
        ) : (
          <ChatRichView isActive={isActive} />
        )}
      </ChatShell>
    </DashboardChatSurfaceGate>
  );
}
