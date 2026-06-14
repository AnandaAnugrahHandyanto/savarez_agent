import { api } from "@/lib/api";
import { Input } from "@nous-research/ui/ui/components/input";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { cn } from "@/lib/utils";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@nous-research/ui/ui/components/dialog";
import { useI18n } from "@/i18n";
import { useProfileScope } from "@/contexts/useProfileScope";

import { sessionDisplayTitle } from "./sessionListCore";
import { useChatSession } from "./ChatSessionContext";

/** FTS5 snippets wrap matches in >>> and <<< delimiters. */
function SearchSnippetHighlight({ snippet }: { snippet: string }) {
  const parts: React.ReactNode[] = [];
  const regex = />>>(.*?)<<</g;
  let last = 0;
  let match: RegExpExecArray | null;
  let i = 0;
  while ((match = regex.exec(snippet)) !== null) {
    if (match.index > last) {
      parts.push(snippet.slice(last, match.index));
    }
    parts.push(
      <mark key={i++} className="bg-warning/30 px-0.5 text-warning">
        {match[1]}
      </mark>,
    );
    last = regex.lastIndex;
  }
  if (last < snippet.length) {
    parts.push(snippet.slice(last));
  }
  return (
    <span className="truncate text-xs text-text-tertiary">{parts}</span>
  );
}

interface Props {
  open: boolean;
  onClose: () => void;
}

export function SessionCommandPalette({ open, onClose }: Props) {
  const { t } = useI18n();
  const { profile } = useProfileScope();
  const { resumeStoredSession, sessionList } = useChatSession();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<
    { session_id: string; snippet: string; title?: string | null }[]
  >([]);
  const [loading, setLoading] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!open) {
      setQuery("");
      setResults([]);
      setSelectedIdx(0);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);

    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    debounceRef.current = setTimeout(() => {
      api
        .searchSessions(trimmed, profile)
        .then((resp) => {
          setResults(resp.results ?? []);
          setSelectedIdx(0);
        })
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 300);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, open, profile]);

  const resolveSessionTitle = useCallback(
    (sessionId: string, title?: string | null) => {
      const direct = (title ?? "").trim();
      if (direct) return direct;
      const fromHistory = sessionList.history.find((s) => s.id === sessionId);
      if (fromHistory?.title?.trim()) return fromHistory.title.trim();
      const fromLive = sessionList.live.find(
        (s) => s.id === sessionId || s.session_key === sessionId,
      );
      return (fromLive?.title ?? "").trim() || undefined;
    },
    [sessionList.history, sessionList.live],
  );

  const resumeSession = useCallback(
    (id: string) => {
      if (resumeStoredSession) {
        void resumeStoredSession(id);
      }
      onClose();
    },
    [onClose, resumeStoredSession],
  );

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIdx((i) => Math.min(i + 1, Math.max(0, results.length - 1)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && results[selectedIdx]) {
      e.preventDefault();
      resumeSession(results[selectedIdx].session_id);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="gap-0 p-0 sm:max-w-lg">
        <DialogHeader className="border-b border-border/30 px-4 py-3">
          <DialogTitle className="text-sm">
            {t.chatSession.searchSessions}
          </DialogTitle>
        </DialogHeader>

        <div className="border-b border-border/20 px-4 py-2">
          <Input
            autoFocus={open}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={t.chatSession.searchPlaceholder}
            className="border-0 bg-transparent px-0 shadow-none focus-visible:ring-0"
          />
        </div>

        <div className="max-h-72 overflow-y-auto p-2">
          {loading && (
            <div className="flex justify-center py-6">
              <Spinner />
            </div>
          )}

          {!loading && query.trim() && results.length === 0 && (
            <p className="py-6 text-center text-sm text-text-tertiary">
              {t.chatSession.noMatch}
            </p>
          )}

          {!loading &&
            results.map((row, idx) => (
              <button
                key={row.session_id}
                type="button"
                className={cn(
                  "flex w-full flex-col gap-0.5 rounded-md px-3 py-2 text-left text-sm",
                  idx === selectedIdx
                    ? "bg-primary/10"
                    : "hover:bg-muted/30",
                )}
                onMouseEnter={() => setSelectedIdx(idx)}
                onClick={() => resumeSession(row.session_id)}
              >
                <span className="truncate font-medium">
                  {sessionDisplayTitle(
                    resolveSessionTitle(row.session_id, row.title),
                    undefined,
                    t.chatSession.untitledSession,
                  )}
                </span>
                {row.snippet?.trim() && (
                  <SearchSnippetHighlight snippet={row.snippet} />
                )}
              </button>
            ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
