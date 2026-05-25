import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  Eye,
  MessageSquare,
  Pause,
  Play,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Terminal,
  Zap,
} from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { api } from "@/lib/api";
import type { AgentAction, AgentsResponse, AgentStatus, AgentSummary } from "@/lib/api";
import { cn, timeAgo } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Typography } from "@/components/NouiTypography";
import { PluginSlot } from "@/plugins";

const STATUS_LABELS: Record<AgentStatus, string> = {
  working: "Working",
  needs_input: "Needs input",
  blocked: "Blocked",
  failed: "Failed",
  idle: "Idle",
  done: "Done",
  scheduled: "Scheduled",
};

const STATUS_STYLES: Record<AgentStatus, string> = {
  working: "border-success/30 bg-success/10 text-success",
  needs_input: "border-warning/40 bg-warning/10 text-warning",
  blocked: "border-destructive/50 bg-destructive/10 text-destructive",
  failed: "border-destructive/60 bg-destructive/15 text-destructive",
  idle: "border-muted-foreground/20 bg-muted/20 text-muted-foreground",
  done: "border-primary/30 bg-primary/10 text-primary",
  scheduled: "border-[oklch(0.7_0.14_300)]/40 bg-[oklch(0.7_0.14_300)]/10 text-[oklch(0.78_0.12_300)]",
};

const STATUS_ICONS: Record<AgentStatus, typeof Activity> = {
  working: Activity,
  needs_input: MessageSquare,
  blocked: ShieldAlert,
  failed: AlertTriangle,
  idle: Clock,
  done: CheckCircle2,
  scheduled: Clock,
};

const ACTION_ICONS: Record<AgentAction, typeof Eye> = {
  peek: Eye,
  open: Terminal,
  reply: MessageSquare,
  wake: Zap,
  dispatch: Sparkles,
  pause: Pause,
  resume: Play,
  stop: AlertTriangle,
};

const STATUS_ORDER: AgentStatus[] = [
  "working",
  "needs_input",
  "blocked",
  "idle",
  "done",
  "scheduled",
  "failed",
];

const SOURCE_FILTERS = [
  { value: "all", label: "All" },
  { value: "discord", label: "Discord" },
  { value: "cli", label: "CLI" },
  { value: "cron", label: "Cron" },
  { value: "kanban", label: "Kanban" },
  { value: "process", label: "Processes" },
  { value: "webhook", label: "Webhooks" },
];

const STATUS_FILTERS: Array<{ value: "all" | AgentStatus; label: string }> = [
  { value: "all", label: "All" },
  ...STATUS_ORDER.map((status) => ({ value: status, label: STATUS_LABELS[status] })),
];

function formatSignalTime(value: AgentSummary["last_signal_at"]): string {
  if (typeof value === "number") return timeAgo(value);
  if (typeof value === "string") {
    const parsed = Date.parse(value);
    if (Number.isFinite(parsed)) return timeAgo(parsed / 1000);
  }
  return "unknown";
}

function statusPill(status: AgentStatus) {
  const Icon = STATUS_ICONS[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 border px-2 py-1 text-[10px] font-bold uppercase tracking-[0.12em]",
        STATUS_STYLES[status],
      )}
    >
      <Icon className="h-3 w-3" />
      {STATUS_LABELS[status]}
    </span>
  );
}

function avatarGlyph(agent: AgentSummary): string {
  if (agent.avatar === "dog") return "🐶";
  if (agent.avatar === "codex") return "⌘";
  if (agent.avatar === "omx") return "◇";
  if (agent.avatar === "hermes") return "✦";
  if (agent.avatar === "clock") return "⏱";
  if (agent.avatar === "kanban") return "▦";
  if (agent.avatar === "terminal") return "▸";
  return "🤖";
}

function SummaryCard({ status, count }: { status: AgentStatus; count: number }) {
  const Icon = STATUS_ICONS[status];
  return (
    <Card className={cn("min-w-[10rem]", STATUS_STYLES[status])}>
      <CardContent className="flex items-center justify-between gap-3 p-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] opacity-80">
            {STATUS_LABELS[status]}
          </p>
          <p className="mt-1 text-3xl font-bold leading-none">{count}</p>
        </div>
        <Icon className="h-5 w-5 opacity-80" />
      </CardContent>
    </Card>
  );
}

function AgentCard({ agent, selected, onSelect }: { agent: AgentSummary; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full border bg-card/70 p-3 text-left transition hover:border-primary/50 hover:bg-card",
        selected ? "border-primary/70 ring-1 ring-primary/30" : "border-border",
      )}
    >
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center border border-current/20 bg-background-base text-xl">
          {avatarGlyph(agent)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-expanded text-sm font-bold uppercase tracking-[0.08em] text-midground">
              {agent.name}
            </span>
            {statusPill(agent.status)}
          </div>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {agent.title || agent.current_task || "No task title"}
          </p>
          <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
            <span>{agent.kind}</span>
            <span>·</span>
            <span>{agent.source}</span>
            <span>·</span>
            <span>{formatSignalTime(agent.last_signal_at)}</span>
          </div>
        </div>
      </div>
    </button>
  );
}

function FilterChip({ active, children, onClick }: { active: boolean; children: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.12em] transition",
        active
          ? "border-primary/70 bg-primary/15 text-primary"
          : "border-border bg-background-base/50 text-muted-foreground hover:border-primary/40 hover:text-midground",
      )}
    >
      {children}
    </button>
  );
}

function DetailDrawer({ agent }: { agent: AgentSummary | null }) {
  if (!agent) {
    return (
      <Card className="h-full">
        <CardContent className="flex min-h-72 flex-col items-center justify-center gap-3 text-center text-muted-foreground">
          <Bot className="h-10 w-10" />
          <p className="text-xs uppercase tracking-[0.14em]">Select an agent to inspect</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle>{agent.name}</CardTitle>
          {statusPill(agent.status)}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center border border-current/20 bg-background-base text-3xl">
            {avatarGlyph(agent)}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-midground">{agent.title}</p>
            <p className="mt-1 text-xs text-muted-foreground">{agent.kind} · {agent.source}</p>
          </div>
        </div>

        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Current task</p>
          <p className="mt-1 text-sm text-midground/90">{agent.current_task || "No current task signal"}</p>
        </div>

        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Last signal</p>
          <p className="mt-1 text-sm text-midground/90">{agent.last_signal || "No signal yet"}</p>
          <p className="mt-1 text-xs text-muted-foreground">{formatSignalTime(agent.last_signal_at)}</p>
        </div>

        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Next actions</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {agent.actions.map((action) => {
              const Icon = ACTION_ICONS[action];
              const enabled = action === "peek" || action === "open";
              return (
                <Button key={action} size="sm" ghost={!enabled} disabled={!enabled} title={enabled ? action : "Coming after safe action endpoints"}>
                  <Icon className="h-3 w-3" />
                  {action}
                </Button>
              );
            })}
          </div>
        </div>

        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Links</p>
          <div className="mt-2 space-y-1">
            {agent.links.map((link) => (
              <a key={`${link.label}:${link.href}`} href={link.href} className="block truncate text-xs text-primary hover:underline">
                {link.label}: {link.href}
              </a>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function AgentsPage() {
  const [data, setData] = useState<AgentsResponse | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<"all" | AgentStatus>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadAgents = useCallback(() => {
    setLoading(true);
    api
      .getAgents({ limit: 100, source: sourceFilter, status: statusFilter })
      .then((response) => {
        setData(response);
        setSelectedId((current) => {
          if (current && response.agents.some((agent) => agent.id === current)) return current;
          return response.agents[0]?.id ?? null;
        });
        setError(null);
      })
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, [sourceFilter, statusFilter]);

  useEffect(() => {
    loadAgents();
    const timer = window.setInterval(loadAgents, 15_000);
    return () => window.clearInterval(timer);
  }, [loadAgents]);

  const selectedAgent = useMemo(
    () => data?.agents.find((agent) => agent.id === selectedId) ?? data?.agents[0] ?? null,
    [data?.agents, selectedId],
  );

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="text-2xl text-primary" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PluginSlot name="agents:top" />

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Typography as="h1" expanded className="text-2xl font-bold uppercase tracking-[0.08em] text-midground">
            Agent Situation Board
          </Typography>
          <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
            댕댕이 · 멍멍이 · Codex/OMX workers를 한눈에 보는 관제판입니다. 지금은 read-only 신호를 모으고, 위험한 조작은 안전 endpoint가 생길 때까지 비활성화합니다.
          </p>
        </div>
        <Button size="sm" onClick={loadAgents} disabled={loading}>
          <RefreshCw className={cn("h-3 w-3", loading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {error && (
        <Card className="border-destructive/40 bg-destructive/10 text-destructive">
          <CardContent className="p-3 text-sm">Failed to load agents: {error}</CardContent>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        {STATUS_ORDER.map((status) => (
          <SummaryCard key={status} status={status} count={data?.summary[status] ?? 0} />
        ))}
      </div>

      <Card>
        <CardContent className="space-y-3 p-3">
          <div>
            <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Signal source</p>
            <div className="flex flex-wrap gap-2">
              {SOURCE_FILTERS.map((filter) => (
                <FilterChip
                  key={filter.value}
                  active={sourceFilter === filter.value}
                  onClick={() => setSourceFilter(filter.value)}
                >
                  {filter.label}
                </FilterChip>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.14em] text-muted-foreground">Status</p>
            <div className="flex flex-wrap gap-2">
              {STATUS_FILTERS.map((filter) => (
                <FilterChip
                  key={filter.value}
                  active={statusFilter === filter.value}
                  onClick={() => setStatusFilter(filter.value)}
                >
                  {filter.label}
                </FilterChip>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid min-h-0 gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="space-y-3">
          <Card>
            <CardHeader>
              <CardTitle>Roster</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {data?.agents.length ? (
                data.agents.map((agent) => (
                  <AgentCard
                    key={agent.id}
                    agent={agent}
                    selected={selectedAgent?.id === agent.id}
                    onSelect={() => setSelectedId(agent.id)}
                  />
                ))
              ) : (
                <div className="border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                  No agent signals yet. Recent Hermes sessions will appear here first.
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Event stream</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {data?.events.length ? (
                data.events.slice(0, 8).map((event) => (
                  <div key={`${event.agent_id}:${event.ts}`} className="flex items-center gap-3 border border-border bg-background-base/50 px-3 py-2 text-xs">
                    <span className={cn("h-2 w-2 rounded-full", event.level === "warning" ? "bg-warning" : event.level === "error" ? "bg-destructive" : "bg-primary")} />
                    <span className="truncate text-muted-foreground">{event.agent_id}</span>
                    <span className="min-w-0 flex-1 truncate text-midground">{event.message}</span>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">No events yet.</p>
              )}
            </CardContent>
          </Card>
        </div>

        <DetailDrawer agent={selectedAgent} />
      </div>
    </div>
  );
}
