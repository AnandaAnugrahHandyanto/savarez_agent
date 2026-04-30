import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Cpu,
  Database,
  HardDrive,
  Layers,
  MemoryStick,
  Package,
  RefreshCw,
  Settings,
} from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import type { AnalyticsResponse, DashboardState, ModelInfoResponse, SessionInfo } from "@/lib/api";
import { useDashboardStream } from "@/hooks/useDashboardStream";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { buttonVariants } from "@/components/ui/button";
import { timeAgo } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { PluginSlot } from "@/plugins";

function formatBytes(n?: number | null): string {
  if (!n || n <= 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

function formatUptime(seconds?: number): string {
  if (!seconds || seconds < 0) return "—";
  const s = Math.floor(seconds);
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function GatewayBadge({ state }: { state: DashboardState["status"]["gateway_state"] }) {
  const variant =
    state === "running"
      ? "success"
      : state === "starting"
        ? "warning"
        : state === "startup_failed"
          ? "destructive"
          : "outline";
  return (
    <Badge variant={variant} className="text-[10px]">
      {state ?? "unknown"}
    </Badge>
  );
}

export default function DashboardPage() {
  const { state } = useDashboardStream();
  const [modelInfo, setModelInfo] = useState<ModelInfoResponse | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loadingExtras, setLoadingExtras] = useState(true);
  const { t } = useI18n();
  const { setEnd } = usePageHeader();

  const loadExtras = () => {
    setLoadingExtras(true);
    Promise.all([api.getModelInfo(), api.getAnalytics(7), api.getSessions(10, 0)])
      .then(([mi, an, s]) => {
        setModelInfo(mi);
        setAnalytics(an);
        setSessions(s.sessions);
      })
      .catch(() => {})
      .finally(() => setLoadingExtras(false));
  };

  useEffect(() => {
    loadExtras();
    const id = window.setInterval(loadExtras, 30_000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    setEnd(
      <Button
        type="button"
        size="sm"
        variant="outline"
        onClick={loadExtras}
        disabled={loadingExtras}
        className="h-7 text-xs"
      >
        <RefreshCw className="mr-1 h-3 w-3" />
        {t.common.refresh}
      </Button>,
    );
    return () => setEnd(null);
  }, [loadingExtras, setEnd, t.common.refresh]);

  const topSessions = useMemo(() => sessions.slice(0, 5), [sessions]);

  if (!state) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const memUsed =
    state.system.mem_total_bytes && state.system.mem_available_bytes
      ? state.system.mem_total_bytes - state.system.mem_available_bytes
      : null;

  const diskUsed = state.system.disk ? state.system.disk.used : null;
  const diskTotal = state.system.disk ? state.system.disk.total : null;

  const tokenTotal =
    analytics?.totals.total_input && analytics?.totals.total_output
      ? analytics.totals.total_input + analytics.totals.total_output
      : null;

  return (
    <div className="flex flex-col gap-6">
      <PluginSlot name="dashboard:top" />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{t.status.gateway}</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <GatewayBadge state={state.status.gateway_state} />
              <span className="text-xs text-muted-foreground">
                {state.status.gateway_pid ? `pid ${state.status.gateway_pid}` : ""}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {t.status.activeSessions}:{" "}
              <span className="tabular-nums">{state.status.active_sessions}</span>
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{t.app.webUi}</CardTitle>
            <Cpu className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tabular-nums">
              {formatUptime(state.system.uptime_seconds)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              load:{" "}
              <span className="tabular-nums">
                {state.system.load_avg_1?.toFixed(2) ?? "—"} / {state.system.load_avg_5?.toFixed(2) ?? "—"}
              </span>
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Memory</CardTitle>
            <MemoryStick className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tabular-nums">
              {formatBytes(memUsed)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {formatBytes(state.system.mem_total_bytes)} total · {formatBytes(state.system.process_rss_bytes)} RSS
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Disk</CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold tabular-nums">
              {diskUsed && diskTotal ? `${Math.round((diskUsed / diskTotal) * 100)}%` : "—"}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {formatBytes(diskUsed)} / {formatBytes(diskTotal)}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Layers className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-base">Agent</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="grid gap-3">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <Badge variant="secondary" className="text-[10px]">
                {state.status.version}
              </Badge>
              <Badge variant="outline" className="text-[10px]">
                config v{state.status.config_version}
              </Badge>
              <Badge variant="outline" className="text-[10px]">
                skills {state.skills.enabled}/{state.skills.total}
              </Badge>
              <Badge variant="outline" className="text-[10px]">
                connectors {state.connectors.enabled}/{state.connectors.total}
              </Badge>
            </div>

            <div className="grid gap-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Model</span>
                <span className="font-mono-ui">{modelInfo?.model ? modelInfo.model.split("/").pop() : "—"}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Context</span>
                <span className="tabular-nums">
                  {modelInfo?.effective_context_length ? modelInfo.effective_context_length.toLocaleString() : "—"}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">Capabilities</span>
                <span className="text-muted-foreground/80">
                  {modelInfo?.capabilities
                    ? [
                        modelInfo.capabilities.supports_tools ? "tools" : null,
                        modelInfo.capabilities.supports_vision ? "vision" : null,
                        modelInfo.capabilities.supports_reasoning ? "reasoning" : null,
                      ]
                        .filter(Boolean)
                        .join(", ") || "—"
                    : "—"}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Link
                to="/skills"
                className={buttonVariants({ variant: "outline", size: "sm" }) + " h-8 text-xs"}
              >
                <Package className="h-3.5 w-3.5" />
                {t.app.nav.skills}
              </Link>
              <Link
                to="/connectors"
                className={buttonVariants({ variant: "outline", size: "sm" }) + " h-8 text-xs"}
              >
                <Database className="h-3.5 w-3.5" />
                {t.connectors.title}
              </Link>
              <Link
                to="/config"
                className={buttonVariants({ variant: "outline", size: "sm" }) + " h-8 text-xs"}
              >
                <Settings className="h-3.5 w-3.5" />
                {t.app.nav.config}
              </Link>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Database className="h-5 w-5 text-muted-foreground" />
                <CardTitle className="text-base">{t.status.recentSessions}</CardTitle>
              </div>
              <Link to="/sessions" className={buttonVariants({ variant: "ghost", size: "sm" }) + " h-7 text-xs"}>
                {t.app.nav.sessions}
              </Link>
            </div>
          </CardHeader>
          <CardContent className="grid gap-2">
            {topSessions.length === 0 && (
              <p className="text-xs text-muted-foreground">{t.sessions.noSessions}</p>
            )}
            {topSessions.map((s) => (
              <div key={s.id} className="border border-border p-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium truncate">
                    {s.title && s.title !== "Untitled" ? s.title : s.preview ?? t.common.untitled}
                  </span>
                  <Badge variant="outline" className="text-[10px] shrink-0">
                    {s.source ?? "local"}
                  </Badge>
                </div>
                <div className="flex items-center justify-between text-[10px] text-muted-foreground mt-1">
                  <span className="truncate font-mono-ui">{(s.model ?? t.common.unknown).split("/").pop()}</span>
                  <span className="tabular-nums">{timeAgo(s.last_active)}</span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">{t.app.nav.analytics}</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="grid gap-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">7d sessions</span>
            <span className="tabular-nums">{analytics?.totals.total_sessions ?? "—"}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">7d API calls</span>
            <span className="tabular-nums">{analytics?.totals.total_api_calls ?? "—"}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">7d tokens</span>
            <span className="tabular-nums">{tokenTotal ? tokenTotal.toLocaleString() : "—"}</span>
          </div>
        </CardContent>
      </Card>

      <PluginSlot name="dashboard:bottom" />
    </div>
  );
}
