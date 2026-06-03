import { useEffect, useState } from "react";
import { Activity, WifiOff } from "lucide-react";
import { api } from "@/lib/api";
import type { V210AdaptersHealthResponse } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { useI18n } from "@/i18n";

const ENTRYPOINT_LABELS: Record<string, string> = {
  feishu: "飞书",
  discord: "Discord",
  web: "Web 控制台",
  cli: "CLI",
  mac_app: "Mac App",
};

type BadgeTone = "default" | "destructive" | "outline" | "secondary" | "success" | "warning";

function statusTone(status: string): BadgeTone {
  switch (status) {
    case "connected":
      return "success";
    case "disconnected":
    case "error":
      return "destructive";
    case "unknown":
      return "secondary";
    case "unregistered":
      return "outline";
    default:
      return "secondary";
  }
}

export function AdapterHealthCard() {
  const { t } = useI18n();
  const [health, setHealth] = useState<V210AdaptersHealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetch = async () => {
      try {
        const data = await api.v210AdaptersHealth();
        if (!cancelled) {
          setHealth(data);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      }
    };
    fetch();
    const interval = setInterval(fetch, 30000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (error) {
    return (
      <Card className="border-destructive/40">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <WifiOff className="h-4 w-4 text-destructive" />
            {t.v210?.adapterHealthTitle ?? "Adapter Health"}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-destructive">
          {t.v210?.loadError ?? "Failed to load adapter health: "}{error}
        </CardContent>
      </Card>
    );
  }

  if (!health) {
    return null;
  }

  const isLegacy = health.mode === "cli_legacy";
  const statusLabels: Record<string, string> = {
    connected: t.v210?.statusConnected ?? "Connected",
    disconnected: t.v210?.statusDisconnected ?? "Disconnected",
    unknown: t.v210?.statusUnknown ?? "Unknown",
    unregistered: t.v210?.statusUnregistered ?? "Unregistered",
    error: t.v210?.statusError ?? "Error",
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Activity className="h-4 w-4 text-muted-foreground" />
          {t.v210?.adapterHealthTitle ?? "Adapter Health"}
          <Badge tone={isLegacy ? "secondary" : "success"}>
            {isLegacy ? t.v210?.modeCliLegacy ?? "CLI Legacy" : t.v210?.modeMultiEntry ?? "Multi-Entry"}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLegacy ? (
          <p className="text-sm text-muted-foreground">
            {t.v210?.modeCliLegacyDesc ?? "No external adapters registered."}
          </p>
        ) : (
          <div className="space-y-2">
            {health.registered_entrypoints.map((ep) => {
              const adapter = health.adapters[ep];
              const status = adapter?.status ?? "unknown";
              return (
                <div key={ep} className="flex items-center justify-between text-sm">
                  <span className="font-medium">{ENTRYPOINT_LABELS[ep] ?? ep}</span>
                  <Badge tone={statusTone(status)}>
                    {statusLabels[status] ?? status}
                  </Badge>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
