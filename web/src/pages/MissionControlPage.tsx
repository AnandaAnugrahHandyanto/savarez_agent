import { useCallback, useEffect, useLayoutEffect, useMemo, useState, type ComponentType } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity,
  Bot,
  CalendarClock,
  FolderKanban,
  MessageSquare,
  Package,
  RefreshCw,
  Sparkles,
  WalletCards,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  MissionControlOverviewResponse,
  MissionControlProject,
  SessionInfo,
} from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import { usePageHeader } from "@/contexts/usePageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";

function formatTokens(value?: number): string {
  const n = value ?? 0;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatCost(value?: number): string {
  const n = value ?? 0;
  if (n === 0) return "$0.00";
  if (n < 0.01) return `$${n.toFixed(4)}`;
  return `$${n.toFixed(2)}`;
}

function formatTimestamp(ts?: number | null): string {
  if (!ts) return "Never";
  return timeAgo(ts);
}

function StatCard({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-wide text-muted-foreground">{label}</div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">{value}</div>
            <div className="mt-1 text-xs text-muted-foreground">{detail}</div>
          </div>
          <div className="rounded-lg border border-border bg-muted/30 p-2">
            <Icon className="h-4 w-4 text-muted-foreground" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function ProjectBucket({
  title,
  projects,
}: {
  title: string;
  projects: MissionControlProject[];
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm">{title}</CardTitle>
          <Badge tone="secondary" className="text-xs tabular-nums">{projects.length}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {projects.length === 0 ? (
          <div className="text-sm text-muted-foreground">No projects tracked.</div>
        ) : (
          projects.slice(0, 6).map((project) => (
            <div key={`${project.bucket}-${project.id}`} className="rounded-lg border border-border bg-background/60 p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0 truncate text-sm font-medium">{project.name}</div>
                {project.priority ? <Badge tone="secondary" className="text-[10px]">{project.priority}</Badge> : null}
              </div>
              <div className="mt-1 truncate text-xs text-muted-foreground">{project.brief || project.brief_path || "No brief linked"}</div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function SessionRow({ session }: { session: SessionInfo }) {
  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium">{session.title || session.preview || session.id}</div>
          <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
            <span>{session.source || "unknown"}</span>
            <span>•</span>
            <span>{session.model || "no model"}</span>
            <span>•</span>
            <span>{formatTokens((session.input_tokens || 0) + (session.output_tokens || 0))} tokens</span>
          </div>
        </div>
        <Badge tone={session.is_active ? "success" : "secondary"} className="shrink-0 text-xs">
          {session.is_active ? "Live" : formatTimestamp(session.last_active)}
        </Badge>
      </div>
    </div>
  );
}

export default function MissionControlPage() {
  const [overview, setOverview] = useState<MissionControlOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { setAfterTitle, setEnd } = usePageHeader();
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getMissionControlOverview();
      setOverview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Mission Control");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useLayoutEffect(() => {
    setAfterTitle(
      <Badge tone={overview?.status.gateway_running ? "success" : "secondary"} className="text-xs">
        Gateway {overview?.status.gateway_running ? "online" : "offline"}
      </Badge>,
    );
    setEnd(
      <Button outlined size="sm" onClick={load} disabled={loading}>
        <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        Refresh
      </Button>,
    );
    return () => {
      setAfterTitle(null);
      setEnd(null);
    };
  }, [load, loading, overview?.status.gateway_running, setAfterTitle, setEnd]);

  const projectBuckets = overview?.projects.buckets ?? {};
  const today = overview?.usage.today ?? {};
  const period = overview?.usage.period ?? {};
  const nextCron = overview?.cron.upcoming?.[0];

  const topModel = useMemo(() => overview?.usage.by_model?.[0], [overview]);

  if (loading && !overview) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (error && !overview) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-destructive">{error}</CardContent>
      </Card>
    );
  }

  if (!overview) return null;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={WalletCards}
          label="Today cost"
          value={formatCost(today.actual_cost || today.estimated_cost)}
          detail={`${formatTokens(today.total_tokens)} tokens · ${today.sessions ?? 0} sessions`}
        />
        <StatCard
          icon={Activity}
          label={`${overview.usage.period_days}d usage`}
          value={formatTokens(period.total_tokens)}
          detail={`${formatCost(period.actual_cost || period.estimated_cost)} · ${period.api_calls ?? 0} API calls`}
        />
        <StatCard
          icon={Bot}
          label="Active agents"
          value={String(overview.agents.active_processes + overview.agents.active_sessions)}
          detail={`${overview.agents.active_processes} processes · ${overview.agents.active_sessions} live sessions`}
        />
        <StatCard
          icon={FolderKanban}
          label="Tracked projects"
          value={String(overview.projects.total)}
          detail={`${overview.projects.counts.current ?? 0} current · ${overview.projects.counts.planning ?? 0} planning`}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <div>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Sparkles className="h-5 w-5 text-muted-foreground" />
                  Command Center
                </CardTitle>
                <div className="mt-1 text-sm text-muted-foreground">
                  Read-only mission snapshot generated {formatTimestamp(overview.generated_at)}.
                </div>
              </div>
              <Button outlined size="sm" onClick={() => navigate("/chat")}>Open Chat</Button>
            </div>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-3">
            <div className="rounded-lg border border-border bg-background/60 p-3">
              <div className="text-xs uppercase tracking-wide text-muted-foreground">Gateway</div>
              <div className="mt-2 text-sm font-medium">{overview.status.gateway_state || (overview.status.gateway_running ? "running" : "stopped")}</div>
              <div className="mt-1 text-xs text-muted-foreground">PID {overview.status.gateway_pid ?? "—"}</div>
            </div>
            <div className="rounded-lg border border-border bg-background/60 p-3">
              <div className="text-xs uppercase tracking-wide text-muted-foreground">Top model</div>
              <div className="mt-2 truncate text-sm font-medium">{topModel?.model || "No model usage yet"}</div>
              <div className="mt-1 text-xs text-muted-foreground">{formatTokens((topModel?.input_tokens || 0) + (topModel?.output_tokens || 0))} tokens</div>
            </div>
            <div className="rounded-lg border border-border bg-background/60 p-3">
              <div className="text-xs uppercase tracking-wide text-muted-foreground">Next scheduled job</div>
              <div className="mt-2 truncate text-sm font-medium">{nextCron?.name || nextCron?.id || "None"}</div>
              <div className="mt-1 text-xs text-muted-foreground">{nextCron?.next_run_at || "No upcoming run"}</div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Package className="h-5 w-5 text-muted-foreground" />
              Skills
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg border border-border p-2"><div className="text-lg font-semibold">{overview.skills.total}</div><div className="text-[11px] text-muted-foreground">total</div></div>
              <div className="rounded-lg border border-border p-2"><div className="text-lg font-semibold">{overview.skills.enabled}</div><div className="text-[11px] text-muted-foreground">enabled</div></div>
              <div className="rounded-lg border border-border p-2"><div className="text-lg font-semibold">{overview.skills.disabled}</div><div className="text-[11px] text-muted-foreground">disabled</div></div>
            </div>
            <div className="space-y-1.5">
              {overview.skills.top_categories.slice(0, 5).map((cat) => (
                <div key={cat.category} className="flex items-center justify-between text-sm">
                  <span className="truncate text-muted-foreground">{cat.category}</span>
                  <Badge tone="secondary" className="text-xs">{cat.count}</Badge>
                </div>
              ))}
            </div>
            <Button outlined size="sm" className="w-full" onClick={() => navigate("/skills")}>Manage skills</Button>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-4">
        <ProjectBucket title="Current" projects={projectBuckets.current ?? []} />
        <ProjectBucket title="Planning" projects={projectBuckets.planning ?? []} />
        <ProjectBucket title="Future" projects={projectBuckets.future ?? []} />
        <ProjectBucket title="Archive" projects={projectBuckets.archive ?? []} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Bot className="h-5 w-5 text-muted-foreground" />
              Agent activity
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {overview.agents.processes.length === 0 ? (
              <div className="text-sm text-muted-foreground">No agent-like background processes detected.</div>
            ) : overview.agents.processes.map((agent) => (
              <div key={agent.pid} className="rounded-lg border border-border bg-background/60 p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium">{agent.label}</div>
                  <Badge tone="success" className="text-xs">PID {agent.pid}</Badge>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">Running for {agent.elapsed}</div>
                <div className="mt-2 truncate font-mono text-[11px] text-muted-foreground">{agent.current_work}</div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <MessageSquare className="h-5 w-5 text-muted-foreground" />
                Recent sessions
              </CardTitle>
              <Button ghost size="sm" onClick={() => navigate("/sessions")}>View all</Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {overview.sessions.recent.slice(0, 5).map((session) => <SessionRow key={session.id} session={session} />)}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <CalendarClock className="h-5 w-5 text-muted-foreground" />
              Scheduled jobs
            </CardTitle>
            <Button ghost size="sm" onClick={() => navigate("/cron")}>Open Cron</Button>
          </div>
        </CardHeader>
        <CardContent className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {overview.cron.upcoming.length === 0 ? (
            <div className="text-sm text-muted-foreground">No scheduled jobs configured.</div>
          ) : overview.cron.upcoming.slice(0, 8).map((job) => (
            <div key={job.id} className="rounded-lg border border-border bg-background/60 p-3">
              <div className="truncate text-sm font-medium">{job.name || job.id}</div>
              <div className="mt-1 truncate text-xs text-muted-foreground">{job.schedule_display || job.schedule?.display || "No schedule"}</div>
              <div className="mt-2 flex items-center justify-between gap-2">
                <Badge tone={job.enabled ? "success" : "secondary"} className="text-xs">{job.enabled ? "enabled" : "paused"}</Badge>
                <span className="truncate text-xs text-muted-foreground">{job.next_run_at || "—"}</span>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
