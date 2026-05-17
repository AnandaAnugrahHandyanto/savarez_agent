import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  Copy,
  Database,
  ExternalLink,
  GitCompare,
  KeyRound,
  Link2,
  Search,
  Share2,
  Sparkles,
  Terminal,
  UploadCloud,
  X,
} from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PlatformsCard } from "@/components/PlatformsCard";
import { PluginSlot } from "@/plugins";
import { Toast } from "@/components/Toast";
import { api } from "@/lib/api";
import type { SessionInfo, SessionSearchResult, StatusResponse } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { useToast } from "@/hooks/useToast";
import {
  compactId,
  formatDuration,
  formatTokens,
  getSessionStatus,
  statusTone,
} from "./replayHelpers";

const PAGE_SIZE = 20;
const MONTHLY_PLAN_LIMIT = 100_000;

function CopyButton({ value, label }: { value: string; label: string }) {
  const { showToast } = useToast();
  return (
    <Button
      ghost
      size="xs"
      onClick={async () => {
        await navigator.clipboard.writeText(value);
        showToast(`${label} copied`, "success");
      }}
    >
      <Copy className="h-3 w-3" />
      {label}
    </Button>
  );
}

function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: typeof Database;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              {label}
            </p>
            <p className="mt-2 text-2xl font-mondwest tracking-[0.08em]">
              {value}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
          </div>
          <div className="border border-border bg-secondary/30 p-2 text-primary">
            <Icon className="h-4 w-4" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SessionStatusBadge({ session }: { session: SessionInfo }) {
  const status = getSessionStatus(session);
  return (
    <Badge tone={statusTone(status)} className="capitalize text-[10px]">
      {status}
    </Badge>
  );
}

function RecentSessionsTable({ sessions }: { sessions: SessionInfo[] }) {
  const navigate = useNavigate();

  if (sessions.length === 0) {
    return (
      <div className="border border-dashed border-border p-10 text-center text-sm text-muted-foreground">
        No sessions recorded yet. Upload a replay or start a chat to populate this dashboard.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto border border-border">
      <table className="w-full min-w-[980px] text-left text-sm">
        <thead className="border-b border-border bg-secondary/40 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
          <tr>
            <th className="px-3 py-3 font-medium">Session title / ID</th>
            <th className="px-3 py-3 font-medium">Status</th>
            <th className="px-3 py-3 font-medium">Agent / model</th>
            <th className="px-3 py-3 font-medium">Duration</th>
            <th className="px-3 py-3 font-medium">Tool calls</th>
            <th className="px-3 py-3 font-medium">Cost / tokens</th>
            <th className="px-3 py-3 font-medium">Created</th>
            <th className="px-3 py-3 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {sessions.map((session) => {
            const replayPath = `/replay/${encodeURIComponent(session.id)}`;
            const shareUrl = `${window.location.origin}${replayPath}`;
            return (
              <tr key={session.id} className="bg-background hover:bg-secondary/20">
                <td className="px-3 py-3 align-top">
                  <div className="flex flex-col gap-1">
                    <button
                      type="button"
                      onClick={() => navigate(replayPath)}
                      className="max-w-[260px] truncate text-left font-medium hover:text-primary"
                    >
                      {session.title && session.title !== "Untitled"
                        ? session.title
                        : session.preview || "Untitled session"}
                    </button>
                    <span className="font-mono-ui text-[11px] text-muted-foreground">
                      {compactId(session.id)}
                    </span>
                  </div>
                </td>
                <td className="px-3 py-3 align-top">
                  <SessionStatusBadge session={session} />
                </td>
                <td className="px-3 py-3 align-top">
                  <div className="flex flex-col gap-1">
                    <span className="capitalize">{session.source ?? "local"}</span>
                    <span className="max-w-[180px] truncate font-mono-ui text-[11px] text-muted-foreground">
                      {(session.model ?? "unknown").split("/").pop()}
                    </span>
                  </div>
                </td>
                <td className="px-3 py-3 align-top text-muted-foreground">
                  {formatDuration(session)}
                </td>
                <td className="px-3 py-3 align-top tabular-nums">
                  {session.tool_call_count}
                </td>
                <td className="px-3 py-3 align-top text-muted-foreground">
                  {formatTokens(session)} tokens
                </td>
                <td className="px-3 py-3 align-top text-muted-foreground">
                  {timeAgo(session.started_at)}
                </td>
                <td className="px-3 py-3 align-top">
                  <div className="flex flex-wrap items-center gap-1">
                    <Button size="xs" onClick={() => navigate(replayPath)}>
                      <ExternalLink className="h-3 w-3" />
                      Open replay
                    </Button>
                    <CopyButton value={shareUrl} label="Share" />
                    <Button
                      ghost
                      size="xs"
                      onClick={() => navigate(`/compare?left=${encodeURIComponent(session.id)}`)}
                    >
                      <GitCompare className="h-3 w-3" />
                      Compare
                    </Button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function SidePanel({ sessions, alerts }: { sessions: SessionInfo[]; alerts: string[] }) {
  const used = sessions.reduce(
    (total, session) => total + session.input_tokens + session.output_tokens,
    0,
  );
  const usagePct = Math.min(100, Math.round((used / MONTHLY_PLAN_LIMIT) * 100));
  const recentShares = sessions.slice(0, 3);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <UploadCloud className="h-4 w-4 text-primary" />
            Upload / API key quickstart
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <div className="border border-border bg-secondary/30 p-3">
            <p className="font-medium text-foreground">1. Capture a session</p>
            <p>Run Hermes normally; replays appear here automatically.</p>
          </div>
          <div className="border border-border bg-secondary/30 p-3">
            <p className="font-medium text-foreground">2. Upload via API</p>
            <code className="mt-1 block truncate font-mono-ui text-xs">
              POST /api/sessions/import
            </code>
          </div>
          <Button outlined size="sm" className="w-full">
            <KeyRound className="h-3.5 w-3.5" />
            Manage API keys
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Plan / usage meter</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between text-sm">
            <span>{formatTokens({ input_tokens: used, output_tokens: 0 } as SessionInfo)} tokens</span>
            <span className="text-muted-foreground">{usagePct}%</span>
          </div>
          <div className="mt-2 h-2 bg-secondary">
            <div className="h-full bg-primary" style={{ width: `${usagePct}%` }} />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Local estimate against a {MONTHLY_PLAN_LIMIT.toLocaleString()} token monthly plan limit.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Link2 className="h-4 w-4 text-primary" />
            Recent shares
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {recentShares.map((session) => (
            <div key={session.id} className="flex items-center justify-between gap-2 border border-border p-2">
              <span className="truncate text-sm">{session.title ?? compactId(session.id)}</span>
              <Badge tone="outline" className="text-[10px]">
                replay
              </Badge>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <AlertTriangle className="h-4 w-4 text-warning" />
            Alerts
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {alerts.length === 0 ? (
            <p className="text-sm text-muted-foreground">No urgent replay alerts.</p>
          ) : (
            alerts.map((alert) => (
              <div key={alert} className="border border-warning/30 bg-warning/5 p-2 text-sm text-warning">
                {alert}
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function SessionsPage() {
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [searchResults, setSearchResults] = useState<SessionSearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const { toast } = useToast();
  const { t } = useI18n();
  const { setAfterTitle, setEnd } = usePageHeader();

  const loadSessions = useCallback((nextPage: number) => {
    setLoading(true);
    api
      .getSessions(PAGE_SIZE, nextPage * PAGE_SIZE)
      .then((response) => {
        setSessions(response.sessions);
        setTotal(response.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadSessions(page);
  }, [loadSessions, page]);

  useEffect(() => {
    api.getStatus().then(setStatus).catch(() => {});
  }, []);

  useLayoutEffect(() => {
    setAfterTitle(
      <Badge tone="secondary" className="text-xs tabular-nums">
        Dashboard
      </Badge>,
    );
    setEnd(
      <div className="relative w-full min-w-0 sm:max-w-xs">
        {searching ? (
          <Spinner className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[0.875rem] text-primary" />
        ) : (
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        )}
        <Input
          placeholder={t.sessions.searchPlaceholder}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          className="h-8 pr-7 pl-8 text-xs"
        />
        {search && (
          <Button
            ghost
            size="xs"
            className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => setSearch("")}
            aria-label={t.common.clear}
          >
            <X />
          </Button>
        )}
      </div>,
    );
    return () => {
      setAfterTitle(null);
      setEnd(null);
    };
  }, [search, searching, setAfterTitle, setEnd, t.common.clear, t.sessions.searchPlaceholder]);

  useEffect(() => {
    if (!search.trim()) {
      setSearchResults(null);
      setSearching(false);
      return;
    }
    setSearching(true);
    const timeout = window.setTimeout(() => {
      api
        .searchSessions(search.trim())
        .then((response) => setSearchResults(response.results))
        .catch(() => setSearchResults(null))
        .finally(() => setSearching(false));
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [search]);

  const filtered = useMemo(() => {
    if (!searchResults) return sessions;
    const ids = new Set(searchResults.map((result) => result.session_id));
    return sessions.filter((session) => ids.has(session.id));
  }, [searchResults, sessions]);

  const failedCount = sessions.filter((session) => getSessionStatus(session) === "failed").length;
  const usageThisMonth = sessions.reduce(
    (totalTokens, session) => totalTokens + session.input_tokens + session.output_tokens,
    0,
  );
  const sharedReplays = Math.min(8, sessions.length);
  const alerts = [
    ...(failedCount > 0 ? [`${failedCount} sessions failed on terminal command or tool execution`] : []),
    ...(status?.gateway_state === "startup_failed" ? ["Gateway failed to start"] : []),
  ];
  const platformEntries = status ? Object.entries(status.gateway_platforms ?? {}) : [];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="text-2xl text-primary" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <PluginSlot name="sessions:top" />
      <Toast toast={toast} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Sessions recorded" value={String(total)} detail="Across all agents" icon={Database} />
        <MetricCard label="Failed sessions" value={String(failedCount)} detail="Need investigation" icon={AlertTriangle} />
        <MetricCard label="Shared replays" value={String(sharedReplays)} detail="Ready for handoff" icon={Share2} />
        <MetricCard
          label="Usage this month"
          value={formatTokens({ input_tokens: usageThisMonth, output_tokens: 0 } as SessionInfo)}
          detail={`${MONTHLY_PLAN_LIMIT.toLocaleString()} token plan limit`}
          icon={Sparkles}
        />
      </div>

      {platformEntries.length > 0 && <PlatformsCard platforms={platformEntries} />}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-mondwest text-xl tracking-[0.12em]">Recent sessions</h2>
              <p className="text-sm text-muted-foreground">
                Manage runs by status, model, duration, tool usage, and next action.
              </p>
            </div>
            <Button outlined size="sm" onClick={() => setPage(0)}>
              <Terminal className="h-3.5 w-3.5" />
              Refresh
            </Button>
          </div>

          <RecentSessionsTable sessions={filtered} />

          {!searchResults && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2 text-xs text-muted-foreground">
              <span>
                {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
              </span>
              <div className="flex items-center gap-2">
                <Button outlined size="xs" disabled={page === 0} onClick={() => setPage((value) => value - 1)}>
                  Previous
                </Button>
                <Button
                  outlined
                  size="xs"
                  disabled={(page + 1) * PAGE_SIZE >= total}
                  onClick={() => setPage((value) => value + 1)}
                >
                  Next
                  <ArrowRight className="h-3 w-3" />
                </Button>
              </div>
            </div>
          )}
        </div>

        <SidePanel sessions={sessions} alerts={alerts} />
      </div>

      <PluginSlot name="sessions:bottom" />
    </div>
  );
}
