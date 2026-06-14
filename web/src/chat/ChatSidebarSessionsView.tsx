import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { cn } from "@/lib/utils";
import { ChevronLeft, Plus, Search } from "lucide-react";

import { useI18n } from "@/i18n";

import { useOptionalChatSession } from "./ChatSessionContext";
import { useDashboardChatSurface } from "./DashboardChatSessionProvider";
import { SessionListPanel } from "./SessionListPanel";

interface Props {
  className?: string;
  onBack: () => void;
  closeMobile: () => void;
}

export function ChatSidebarSessionsView({
  className,
  onBack,
  closeMobile,
}: Props) {
  const { t } = useI18n();
  const surface = useDashboardChatSurface();
  const session = useOptionalChatSession();

  const chatLabel =
    (t.app.nav as Record<string, string>).chat ?? "Chat";

  const handleBack = () => {
    onBack();
  };

  if (!surface || !session) {
    return (
      <div
        className={cn(
          "flex min-h-0 flex-1 items-center justify-center py-8",
          className,
        )}
        aria-busy="true"
      >
        <Spinner className="h-4 w-4" />
      </div>
    );
  }

  return (
    <div
      className={cn("flex min-h-0 flex-1 flex-col overflow-hidden", className)}
    >
      <div className="flex shrink-0 items-center gap-3 border-b border-current/10 px-5 py-2.5">
        <Button
          type="button"
          ghost
          size="icon"
          onClick={handleBack}
          aria-label={t.chatSession.backToNav}
          className="-ml-2 shrink-0 text-text-secondary hover:text-midground"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </Button>

        <span className="min-w-0 flex-1 truncate font-mondwest text-display uppercase text-sm tracking-[0.12em] text-midground">
          {chatLabel}
        </span>

        <div className="-mr-2 flex shrink-0 items-center">
          <Button
            type="button"
            ghost
            size="icon"
            onClick={() => session.openSessionPalette?.()}
            aria-label={t.chatSession.searchSessions}
            title={`${t.chatSession.searchSessions} (⌘K)`}
            className="text-text-secondary hover:text-midground"
          >
            <Search className="h-3.5 w-3.5" />
          </Button>

          <Button
            type="button"
            ghost
            size="icon"
            onClick={() => {
              session.startNewChat();
              handleBack();
            }}
            aria-label={t.chatSession.newChat}
            className="text-text-secondary hover:text-midground"
          >
            <Plus className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <SessionListPanel
        className="min-h-0 flex-1"
        showNewChat={false}
        showTitle={false}
        onSessionSelect={closeMobile}
      />
    </div>
  );
}
