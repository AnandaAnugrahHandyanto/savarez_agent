import { api } from "@/lib/api";
import { Button } from "@nous-research/ui/ui/components/button";
import { Input } from "@nous-research/ui/ui/components/input";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { cn } from "@/lib/utils";
import {
  Check,
  ExternalLink,
  Globe,
  MessageCircle,
  MessageSquare,
  Pencil,
  Terminal,
  Trash2,
  X,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useI18n } from "@/i18n";
import { useProfileScope } from "@/contexts/useProfileScope";

import { useChatSession } from "./ChatSessionContext";
import {
  relativeSessionAge,
  sessionDisplayTitle,
  type SessionActiveItem,
  type SessionListItem,
} from "./sessionListCore";

const SOURCE_ICONS: Record<string, LucideIcon> = {
  cli: Terminal,
  telegram: MessageCircle,
  discord: MessageSquare,
};

interface Props {
  className?: string;
  /** When false, omit the inline “New chat” row (use header + instead). */
  showNewChat?: boolean;
  /** When false, omit the “Sessions” section title row. */
  showTitle?: boolean;
  /** Called after picking a session (e.g. close mobile drawer). */
  onSessionSelect?: () => void;
}

function SourceIcon({ source }: { source?: string }) {
  const Icon = (source && SOURCE_ICONS[source]) || Globe;
  return <Icon className="h-3.5 w-3.5 shrink-0 opacity-70" />;
}

function SessionRowButton({
  active,
  onClick,
  children,
}: {
  active?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
        active
          ? "bg-primary/10 text-foreground"
          : "hover:bg-muted/30 text-text-secondary hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

function LiveRow({
  item,
  active,
  onResume,
}: {
  item: SessionActiveItem;
  active: boolean;
  onResume: (id: string) => void;
}) {
  const { t } = useI18n();
  const title = sessionDisplayTitle(
    item.title,
    item.preview,
    t.chatSession.untitledSession,
  );
  const running = item.status === "working" || item.status === "starting";

  return (
    <SessionRowButton active={active} onClick={() => onResume(item.id)}>
      <span
        className={cn(
          "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
          running ? "animate-pulse bg-primary" : "bg-muted-foreground/50",
        )}
      />
      <span className="min-w-0 flex-1">
        <span className="block truncate font-medium">{title}</span>
        <span className="block truncate text-[11px] text-text-tertiary">
          {item.status} · {relativeSessionAge(item.last_active ?? item.started_at)}
        </span>
      </span>
    </SessionRowButton>
  );
}

function HistoryRow({
  item,
  active,
  onResume,
  onRename,
  onDelete,
}: {
  item: SessionListItem;
  active: boolean;
  onResume: (id: string) => void;
  onRename: (id: string, title: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const { t } = useI18n();
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(item.title ?? "");
  const [busy, setBusy] = useState(false);

  const title = sessionDisplayTitle(
    item.title,
    item.preview,
    t.chatSession.untitledSession,
  );

  const submitRename = async () => {
    const next = renameValue.trim();
    if (!next || next === item.title) {
      setRenaming(false);
      return;
    }
    setBusy(true);
    try {
      await onRename(item.id, next);
      setRenaming(false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="group relative">
      {renaming ? (
        <div
          className="flex items-center gap-1 px-2 py-1"
          onClick={(e) => e.stopPropagation()}
        >
          <Input
            autoFocus
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void submitRename();
              if (e.key === "Escape") setRenaming(false);
            }}
            className="h-7 flex-1 py-0 text-xs"
            disabled={busy}
          />
          <Button
            ghost
            size="icon"
            className="h-7 w-7"
            disabled={busy}
            onClick={() => void submitRename()}
          >
            <Check className="h-3.5 w-3.5" />
          </Button>
          <Button
            ghost
            size="icon"
            className="h-7 w-7"
            disabled={busy}
            onClick={() => setRenaming(false)}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      ) : (
        <>
          <SessionRowButton active={active} onClick={() => onResume(item.id)}>
            <SourceIcon source={item.source} />
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{title}</span>
              <span className="block truncate text-[11px] text-text-tertiary">
                {item.source ?? "local"} ·{" "}
                {relativeSessionAge(item.started_at)}
              </span>
            </span>
          </SessionRowButton>
          <div
            className={cn(
              "absolute inset-y-0 right-1 flex items-center gap-0.5 pl-4",
              "bg-gradient-to-l from-background via-background/95 to-transparent",
              "pointer-events-none opacity-0 transition-opacity group-hover:pointer-events-auto group-hover:opacity-100",
            )}
          >
            <Button
              type="button"
              ghost
              size="icon"
              className="h-6 w-6"
              aria-label={t.chatSession.renameSession}
              onClick={(e) => {
                e.stopPropagation();
                setRenameValue(item.title ?? "");
                setRenaming(true);
              }}
            >
              <Pencil className="h-3 w-3" />
            </Button>
            <Button
              type="button"
              ghost
              destructive
              size="icon"
              className="h-6 w-6"
              aria-label={t.chatSession.deleteSession}
              onClick={(e) => {
                e.stopPropagation();
                void onDelete(item.id);
              }}
            >
              <Trash2 className="h-3 w-3" />
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

export function SessionListPanel({
  className,
  showNewChat = true,
  showTitle = true,
  onSessionSelect,
}: Props) {
  const { t } = useI18n();
  const [searchParams] = useSearchParams();
  const { profile } = useProfileScope();
  const {
    gw,
    startNewChat,
    activateLiveSession,
    resumeStoredSession,
    sessionList,
  } = useChatSession();
  const resumeId = searchParams.get("resume");
  const { live, history, loading, error, refresh } = sessionList;

  const pickStoredSession = useCallback(
    (storedId: string) => {
      if (resumeStoredSession) {
        void resumeStoredSession(storedId);
      }
      onSessionSelect?.();
    },
    [onSessionSelect, resumeStoredSession],
  );

  const pickLiveSession = useCallback(
    (runtimeId: string) => {
      if (activateLiveSession) {
        void activateLiveSession(runtimeId);
      }
      onSessionSelect?.();
    },
    [activateLiveSession, onSessionSelect],
  );

  const handleRename = useCallback(
    async (id: string, title: string) => {
      await api.renameSession(id, title, profile);
      await refresh();
    },
    [profile, refresh],
  );

  const handleDelete = useCallback(
    async (id: string) => {
      if (!gw) return;
      await gw.request("session.delete", { session_id: id });
      if (resumeId === id) {
        startNewChat();
      }
      await refresh();
    },
    [gw, refresh, resumeId, startNewChat],
  );

  return (
    <section
      aria-label={t.chatSession.sessions}
      className={cn("flex min-h-0 flex-col", className)}
    >
      {showTitle && (
        <div className="flex items-center justify-between px-3 py-2">
          <span className="text-xs font-medium uppercase tracking-wide text-text-tertiary">
            {t.chatSession.sessions}
          </span>
          {loading && <Spinner className="h-3.5 w-3.5" />}
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto px-2 pb-2">
        {!showTitle && loading && (
          <div className="flex justify-end px-1 py-1">
            <Spinner className="h-3.5 w-3.5" />
          </div>
        )}

        {showNewChat && (
          <SessionRowButton onClick={startNewChat}>
            <span className="font-medium">{t.chatSession.newChat}</span>
          </SessionRowButton>
        )}

        {error && (
          <p className="px-2 py-1 text-xs text-destructive">{error}</p>
        )}

        {live.length > 0 && (
          <div className="mt-2">
            <p className="mb-1 px-2 text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
              {t.chatSession.openSessions}
            </p>
            {live.map((item) => (
              <LiveRow
                key={item.id}
                item={item}
                active={resumeId === item.id || resumeId === item.session_key}
                onResume={pickLiveSession}
              />
            ))}
          </div>
        )}

        {history.length > 0 && (
          <div className="mt-2">
            <p className="mb-1 px-2 text-[10px] font-medium uppercase tracking-wide text-text-tertiary">
              {t.chatSession.recentSessions}
            </p>
            {history.map((item) => (
              <HistoryRow
                key={item.id}
                item={item}
                active={resumeId === item.id}
                onResume={pickStoredSession}
                onRename={handleRename}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}

        {!loading && live.length === 0 && history.length === 0 && !error && (
          <p className="px-2 py-4 text-center text-xs text-text-tertiary">
            {t.chatSession.noSessions}
          </p>
        )}
      </div>

      <div className="shrink-0 border-t border-current/10 px-2 py-2">
        <Link
          to="/sessions"
          className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-text-secondary transition-colors hover:bg-muted/30 hover:text-foreground"
        >
          <ExternalLink className="h-3.5 w-3.5 shrink-0 opacity-70" />
          <span>{t.chatSession.allSessions}</span>
        </Link>
      </div>
    </section>
  );
}
