import { useEffect, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Layers,
  MapPin,
  ShieldAlert,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  StatusResponse,
  V210Workspace,
  V210Session,
  V210AdaptersHealthResponse,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@nous-research/ui/ui/components/badge";

type FetchState = "loading" | "available" | "unavailable";

function ValueRow({
  label,
  value,
  detail,
  tone = "outline",
}: {
  label: string;
  value: string;
  detail?: string;
  tone?: "outline" | "secondary" | "success" | "warning" | "destructive";
}) {
  return (
    <div className="flex flex-col gap-1 border border-border p-2">
      <div className="flex items-start justify-between gap-3">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        <Badge tone={tone} className="shrink-0 text-[10px]">
          {value}
        </Badge>
      </div>
      {detail ? (
        <p className="text-xs leading-relaxed text-muted-foreground">{detail}</p>
      ) : null}
    </div>
  );
}

function ListRow({ children }: { children: ReactNode }) {
  return (
    <li className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
      <CheckCircle2 className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" />
      <span>{children}</span>
    </li>
  );
}

export function V210WorkspaceContext() {
  const [workspaces, setWorkspaces] = useState<V210Workspace[]>([]);
  const [sessions, setSessions] = useState<V210Session[]>([]);
  const [health, setHealth] = useState<V210AdaptersHealthResponse | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [workspaceState, setWorkspaceState] = useState<FetchState>("loading");
  const [sessionState, setSessionState] = useState<FetchState>("loading");
  const [healthState, setHealthState] = useState<FetchState>("loading");

  useEffect(() => {
    let cancelled = false;
    const fetch = async () => {
      try {
        const [ws, ss, h, appStatus] = await Promise.allSettled([
          api.v210ListWorkspaces(),
          api.v210ListSessions(),
          api.v210AdaptersHealth(),
          api.getStatus(),
        ]);
        if (!cancelled) {
          if (ws.status === "fulfilled") {
            setWorkspaces(ws.value.workspaces);
            setWorkspaceState("available");
          } else {
            setWorkspaceState("unavailable");
          }
          if (ss.status === "fulfilled") {
            setSessions(ss.value.sessions);
            setSessionState("available");
          } else {
            setSessionState("unavailable");
          }
          if (h.status === "fulfilled") {
            setHealth(h.value);
            setHealthState("available");
          } else {
            setHealthState("unavailable");
          }
          if (appStatus.status === "fulfilled") setStatus(appStatus.value);
        }
      } catch {
        // Silently swallow — this is supplementary context
      }
    };
    fetch();
    const interval = setInterval(fetch, 60000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const appVersion = status?.version ? `v${status.version}` : "unknown";
  const currentWorkspace =
    workspaceState === "unavailable"
      ? "unavailable"
      : workspaces[0]?.workspace_id ?? "unknown";
  const currentSession =
    sessionState === "unavailable"
      ? "unknown"
      : "none selected";
  const feishu = health?.adapters.feishu;
  const feishuConnection =
    healthState === "unavailable"
      ? "unavailable"
      : feishu?.status === "connected"
        ? "connected"
        : feishu?.status ?? "unknown";
  const feishuEntryAdapter =
    healthState === "unavailable"
      ? "unavailable"
      : health?.registered_entrypoints.includes("feishu")
        ? "available"
        : "unknown";
  const discordRegistered = health?.registered_entrypoints.includes("discord");
  const modeLabel =
    health?.mode === "multi_entry"
      ? "multi-entry"
      : health?.mode === "cli_legacy"
        ? "cli legacy"
        : "unknown";

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Layers className="h-4 w-4 text-muted-foreground" />
          Hermes v2.10 Session Binding Status
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="grid gap-2 md:grid-cols-2">
          <ValueRow
            label="Product release"
            value="v2.10-multi-entry-session-binding"
            detail="Release tag and App/UI version are different concepts."
            tone="success"
          />
          <ValueRow
            label="App/UI version"
            value={appVersion}
            detail="Displayed by the Web Console build/runtime status endpoint."
            tone={appVersion === "unknown" ? "warning" : "secondary"}
          />
          <ValueRow
            label="Workspace"
            value={currentWorkspace}
            detail={`${workspaces.length} workspace record(s) visible from the v2.10 local API.`}
            tone={
              currentWorkspace === "unavailable" || currentWorkspace === "unknown"
                ? "warning"
                : "outline"
            }
          />
          <ValueRow
            label="Session"
            value={currentSession}
            detail={`${sessions.length} bound session record(s) visible. Recent legacy sessions are listed below.`}
            tone="warning"
          />
          <ValueRow
            label="Binding mode"
            value={modeLabel}
            detail="Legacy, unknown, and unavailable binding states are intentionally shown."
            tone={modeLabel === "multi-entry" ? "success" : "warning"}
          />
          <ValueRow
            label="Feishu connection"
            value={feishuConnection}
            detail={`EntryAdapter: ${feishuEntryAdapter}. Connected only means adapter visibility, not full production task execution.`}
            tone={feishuConnection === "connected" ? "success" : "warning"}
          />
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <div className="border border-border p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium">
              <MapPin className="h-4 w-4 text-muted-foreground" />
              Entry Status
            </div>
            <ul className="space-y-1">
              <ListRow>Feishu ambiguity cards: disabled by default.</ListRow>
              <ListRow>Feishu production task enforcement: not enabled.</ListRow>
              <ListRow>
                Discord: dormant / fallback; not an active production entrypoint
                and not part of the current Feishu-first workflow
                {discordRegistered ? " (adapter registered)." : "."}
              </ListRow>
              <ListRow>Lark CLI: not implemented; deferred to v2.11 Feishu Operation Layer.</ListRow>
            </ul>
          </div>

          <div className="border border-border p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-medium">
              <ShieldAlert className="h-4 w-4 text-muted-foreground" />
              Safety Status
            </div>
            <ul className="space-y-1">
              <ListRow>Permission Gate: advisory only.</ListRow>
              <ListRow>Not fail-closed production enforcement.</ListRow>
              <ListRow>
                Do not interpret this panel as a complete production safety boundary.
              </ListRow>
              <li className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-warning" />
                <span>Unavailable states are not hidden or made to look healthy.</span>
              </li>
            </ul>
          </div>
        </div>

        {health && health.registered_entrypoints.length > 0 && (
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Registered adapters
            </span>
            <div className="flex gap-1">
              {health.registered_entrypoints.map((ep) => (
                <Badge key={ep} tone="outline" className="text-xs">
                  <MapPin className="mr-1 h-3 w-3" />
                  {ep}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
