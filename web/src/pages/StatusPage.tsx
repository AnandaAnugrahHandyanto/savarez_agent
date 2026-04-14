import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Clock,
  Cpu,
  Database,
  Radio,
  Wifi,
  WifiOff,
} from "lucide-react";
import { api } from "@/lib/api";
import type { PlatformStatus, SessionInfo, StatusResponse } from "@/lib/api";
import { timeAgo, isoTimeAgo } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const PLATFORM_STATE_BADGE: Record<string, { variant: "success" | "warning" | "destructive"; label: string }> = {
  connected: { variant: "success", label: "已連線" },
  disconnected: { variant: "warning", label: "未連線" },
  fatal: { variant: "destructive", label: "錯誤" },
};

const GATEWAY_STATE_DISPLAY: Record<string, { badge: "success" | "warning" | "destructive" | "outline"; label: string }> = {
  running: { badge: "success", label: "運行中" },
  starting: { badge: "warning", label: "啟動中" },
  startup_failed: { badge: "destructive", label: "失敗" },
  stopped: { badge: "outline", label: "已停止" },
};

function gatewayValue(status: StatusResponse): string {
  if (status.gateway_running) return `PID ${status.gateway_pid}`;
  if (status.gateway_state === "startup_failed") return "啟動失敗";
  return "未運行";
}

function gatewayBadge(status: StatusResponse) {
  const info = status.gateway_state ? GATEWAY_STATE_DISPLAY[status.gateway_state] : null;
  if (info) return info;
  return status.gateway_running
    ? { badge: "success" as const, label: "Running" }
    : { badge: "outline" as const, label: "Off" };
}

export default function StatusPage() {
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);

  useEffect(() => {
    const load = () => {
      api.getStatus().then(setStatus).catch(() => {});
      api.getSessions(50).then((resp) => setSessions(resp.sessions)).catch(() => {});
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  if (!status) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const gwBadge = gatewayBadge(status);

  const items = [
    {
      icon: Cpu,
      label: "Agent",
      value: `v${status.version}`,
      badgeText: "即時",
      badgeVariant: "success" as const,
    },
    {
      icon: Radio,
      label: "Gateway",
      value: gatewayValue(status),
      badgeText: gwBadge.label,
      badgeVariant: gwBadge.badge,
    },
    {
      icon: Activity,
      label: "進行中會話",
      value: status.active_sessions > 0 ? `${status.active_sessions} 個運行中` : "無",
      badgeText: status.active_sessions > 0 ? "即時" : "關閉",
      badgeVariant: (status.active_sessions > 0 ? "success" : "outline") as "success" | "outline",
    },
  ];

  const platforms = Object.entries(status.gateway_platforms ?? {});
  const activeSessions = sessions.filter((s) => s.is_active);
  const recentSessions = sessions.filter((s) => !s.is_active).slice(0, 5);

  // Collect alerts that need attention
  const alerts: { message: string; detail?: string }[] = [];
  if (status.gateway_state === "startup_failed") {
    alerts.push({
      message: "Gateway 啟動失敗",
      detail: status.gateway_exit_reason ?? undefined,
    });
  }
  const failedPlatforms = platforms.filter(([, info]) => info.state === "fatal" || info.state === "disconnected");
  for (const [name, info] of failedPlatforms) {
    alerts.push({
      message: `${name.charAt(0).toUpperCase() + name.slice(1)} ${info.state === "fatal" ? "錯誤" : "未連線"}`,
      detail: info.error_message ?? undefined,
    });
  }


  return (
    <div className="flex flex-col gap-6">
      {/* Alert banner — breaks grid monotony for critical states */}
      {alerts.length > 0 && (
        <div className="border border-destructive/30 bg-destructive/[0.06] p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
            <div className="flex flex-col gap-2 min-w-0">
              {alerts.map((alert, i) => (
                <div key={i}>
                  <p className="text-sm font-medium text-destructive">{alert.message}</p>
                  {alert.detail && (
                    <p className="text-xs text-destructive/70 mt-0.5">{alert.detail}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        {items.map(({ icon: Icon, label, value, badgeText, badgeVariant }) => (
          <Card key={label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">{label}</CardTitle>
              <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>

            <CardContent>
              <div className="text-2xl font-bold font-display">{value}</div>

              {badgeText && (
                <Badge variant={badgeVariant} className="mt-2">
                  {badgeVariant === "success" && (
                    <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
                  )}
                  {badgeText}
                </Badge>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {platforms.length > 0 && (
        <PlatformsCard platforms={platforms} />
      )}

      {activeSessions.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-success" />
              <CardTitle className="text-base">進行中會話</CardTitle>
            </div>
          </CardHeader>

          <CardContent className="grid gap-3">
            {activeSessions.map((s) => (
              <div
                key={s.id}
                className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border border-border p-3 w-full"
              >
                <div className="flex flex-col gap-1 min-w-0 w-full">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate">{s.title ?? "未命名"}</span>

                    <Badge variant="success" className="text-[10px] shrink-0">
                      <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
                      即時
                    </Badge>
                  </div>

                  <span className="text-xs text-muted-foreground truncate">
                    <span className="font-mono-ui">{(s.model ?? "unknown").split("/").pop()}</span> · {s.message_count} 則訊息 · {timeAgo(s.last_active)}
                  </span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {recentSessions.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Clock className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-base">最近會話</CardTitle>
            </div>
          </CardHeader>

          <CardContent className="grid gap-3">
            {recentSessions.map((s) => (
              <div
                key={s.id}
                className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border border-border p-3 w-full"
              >
                <div className="flex flex-col gap-1 min-w-0 w-full">
                  <span className="font-medium text-sm truncate">{s.title ?? "未命名"}</span>

                  <span className="text-xs text-muted-foreground truncate">
                    <span className="font-mono-ui">{(s.model ?? "unknown").split("/").pop()}</span> · {s.message_count} 則訊息 · {timeAgo(s.last_active)}
                  </span>

                  {s.preview && (
                    <span className="text-xs text-muted-foreground/70 truncate">
                      {s.preview}
                    </span>
                  )}
                </div>

                <Badge variant="outline" className="text-[10px] shrink-0 self-start sm:self-center">
                  <Database className="mr-1 h-3 w-3" />
                  {s.source ?? "local"}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function PlatformsCard({ platforms }: PlatformsCardProps) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Radio className="h-5 w-5 text-muted-foreground" />
          <CardTitle className="text-base">已連線平台</CardTitle>
        </div>
      </CardHeader>

      <CardContent className="grid gap-3">
        {platforms.map(([name, info]) => {
          const display = PLATFORM_STATE_BADGE[info.state] ?? {
            variant: "outline" as const,
            label: info.state,
          };
          const IconComponent = info.state === "connected" ? Wifi : info.state === "fatal" ? AlertTriangle : WifiOff;

          return (
            <div
              key={name}
              className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border border-border p-3 w-full"
            >
              <div className="flex items-center gap-3 min-w-0 w-full">
                <IconComponent className={`h-4 w-4 shrink-0 ${
                  info.state === "connected"
                    ? "text-success"
                    : info.state === "fatal"
                      ? "text-destructive"
                      : "text-warning"
                }`} />

                <div className="flex flex-col gap-0.5 min-w-0">
                  <span className="text-sm font-medium capitalize truncate">{name}</span>

                  {info.error_message && (
                    <span className="text-xs text-destructive">{info.error_message}</span>
                  )}

                  {info.updated_at && (
                    <span className="text-xs text-muted-foreground">
                      最後更新：{isoTimeAgo(info.updated_at)}
                    </span>
                  )}
                </div>
              </div>

              <Badge variant={display.variant} className="shrink-0 self-start sm:self-center">
                {display.variant === "success" && (
                  <span className="mr-1 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
                )}
                {display.label}
              </Badge>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

interface PlatformsCardProps {
  platforms: [string, PlatformStatus][];
}
