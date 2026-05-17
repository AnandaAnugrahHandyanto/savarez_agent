import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Code2,
  Copy,
  Download,
  FileCode2,
  GitCompare,
  MessageSquare,
  Share2,
  Terminal,
  Wrench,
} from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Markdown } from "@/components/Markdown";
import { api } from "@/lib/api";
import type { SessionInfo, SessionMessage } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import { usePageHeader } from "@/contexts/usePageHeader";
import {
  compactId,
  countToolCalls,
  deriveIncidentSummary,
  fileChangeCalls,
  formatDateTime,
  formatDuration,
  formatTokens,
  messageText,
  statusTone,
  terminalCommands,
} from "./replayHelpers";

function SectionCard({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof MessageSquare;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="h-4 w-4 text-primary" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function MessagePanel({ messages }: { messages: SessionMessage[] }) {
  return (
    <div className="space-y-3">
      {messages.map((message, index) => (
        <div key={`${message.role}-${index}`} className="border border-border bg-secondary/20 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <Badge tone="outline" className="text-[10px] uppercase">
              {message.tool_name ? `tool: ${message.tool_name}` : message.role}
            </Badge>
            {message.timestamp && (
              <span className="text-xs text-muted-foreground">{timeAgo(message.timestamp)}</span>
            )}
          </div>
          {message.role === "assistant" || message.role === "user" ? (
            <Markdown content={messageText(message) || "—"} />
          ) : (
            <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words font-mono-ui text-xs text-muted-foreground">
              {messageText(message) || "—"}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}

function Timeline({ messages }: { messages: SessionMessage[] }) {
  return (
    <div className="space-y-3">
      {messages.map((message, index) => {
        const isTool = message.role === "tool" || Boolean(message.tool_calls?.length);
        const Icon = isTool ? Wrench : message.role === "assistant" ? MessageSquare : Clock;
        return (
          <div key={`${message.role}-${index}`} className="relative flex gap-3">
            <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center border border-border bg-background">
              <Icon className="h-3.5 w-3.5 text-primary" />
            </div>
            <div className="min-w-0 border-l border-border pl-3 pb-3">
              <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
                {message.tool_name ?? message.tool_calls?.[0]?.function.name ?? message.role}
              </p>
              <p className="mt-1 line-clamp-2 text-sm text-foreground/90">
                {messageText(message).slice(0, 120) || "No content"}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function ReplayPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [messages, setMessages] = useState<SessionMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { setAfterTitle, setEnd } = usePageHeader();

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([api.getSessions(200), api.getSessionMessages(id)])
      .then(([sessionResponse, messageResponse]) => {
        setSession(sessionResponse.sessions.find((candidate) => candidate.id === id) ?? null);
        setMessages(messageResponse.messages);
      })
      .catch((reason) => setError(String(reason)))
      .finally(() => setLoading(false));
  }, [id]);

  const incident = useMemo(
    () => deriveIncidentSummary(session, messages),
    [messages, session],
  );
  const tools = countToolCalls(messages);
  const terminals = terminalCommands(messages);
  const fileChanges = fileChangeCalls(messages);
  const shareUrl = typeof window === "undefined" ? "" : window.location.href;

  useLayoutEffect(() => {
    setAfterTitle(
      <Badge tone={statusTone(incident.outcome)} className="capitalize text-xs">
        {incident.outcome}
      </Badge>,
    );
    setEnd(
      <div className="flex items-center gap-2">
        <Button ghost size="xs" onClick={() => navigate("/sessions")}>
          <ArrowLeft className="h-3 w-3" />
          Dashboard
        </Button>
        <Button ghost size="xs" onClick={() => navigate(`/compare?left=${encodeURIComponent(id ?? "")}`)}>
          <GitCompare className="h-3 w-3" />
          Compare
        </Button>
      </div>,
    );
    return () => {
      setAfterTitle(null);
      setEnd(null);
    };
  }, [id, incident.outcome, navigate, setAfterTitle, setEnd]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="text-2xl text-primary" />
      </div>
    );
  }

  if (error || !id) {
    return <div className="border border-destructive/30 bg-destructive/5 p-4 text-destructive">{error ?? "Replay not found"}</div>;
  }

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="text-xl">Incident summary</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                Start here, then drill into raw messages, tools, terminal output, and file changes.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                outlined
                size="sm"
                onClick={() => navigator.clipboard.writeText(shareUrl)}
              >
                <Share2 className="h-3.5 w-3.5" />
                Share
              </Button>
              <Button outlined size="sm" onClick={() => navigator.clipboard.writeText(JSON.stringify({ session, messages }, null, 2))}>
                <Download className="h-3.5 w-3.5" />
                Export JSON
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <div className="border border-border bg-secondary/20 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Outcome</p>
              <Badge tone={statusTone(incident.outcome)} className="mt-2 capitalize">
                {incident.outcome}
              </Badge>
            </div>
            <div className="border border-border bg-secondary/20 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Failure point</p>
              <p className="mt-2 text-sm font-medium">{incident.failurePoint}</p>
            </div>
            <div className="border border-border bg-secondary/20 p-3">
              <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Last successful step</p>
              <p className="mt-2 text-sm font-medium">{incident.lastSuccessfulStep}</p>
            </div>
            <div className="border border-border bg-secondary/20 p-3 xl:col-span-2">
              <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground">Suggested next step</p>
              <p className="mt-2 text-sm font-medium">{incident.suggestedNextStep}</p>
            </div>
          </div>
          <div className="mt-3 border border-warning/30 bg-warning/5 p-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              <div>
                <p className="text-xs uppercase tracking-[0.14em] text-warning">Error</p>
                <p className="mt-1 text-sm text-foreground/90">{incident.error}</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)_320px]">
        <aside className="xl:sticky xl:top-4 xl:self-start">
          <SectionCard title="Timeline" icon={Clock}>
            <Timeline messages={messages} />
          </SectionCard>
        </aside>

        <main className="flex flex-col gap-4">
          <SectionCard title="Overview summary" icon={CheckCircle2}>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <div className="border border-border p-3">
                <p className="text-xs text-muted-foreground">Duration</p>
                <p className="text-lg font-medium">{session ? formatDuration(session) : "—"}</p>
              </div>
              <div className="border border-border p-3">
                <p className="text-xs text-muted-foreground">Messages</p>
                <p className="text-lg font-medium">{messages.length}</p>
              </div>
              <div className="border border-border p-3">
                <p className="text-xs text-muted-foreground">Tool calls</p>
                <p className="text-lg font-medium">{tools}</p>
              </div>
              <div className="border border-border p-3">
                <p className="text-xs text-muted-foreground">Tokens</p>
                <p className="text-lg font-medium">{session ? formatTokens(session) : "—"}</p>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Messages / prompts" icon={MessageSquare}>
            <MessagePanel messages={messages.filter((message) => message.role !== "tool")} />
          </SectionCard>

          <SectionCard title="Tool calls" icon={Wrench}>
            <MessagePanel messages={messages.filter((message) => message.role === "tool" || Boolean(message.tool_calls?.length))} />
          </SectionCard>

          <SectionCard title="Terminal commands / output" icon={Terminal}>
            {terminals.length === 0 ? (
              <p className="text-sm text-muted-foreground">No terminal commands captured.</p>
            ) : (
              <div className="space-y-2">
                {terminals.map((command, index) => (
                  <pre key={`${command}-${index}`} className="overflow-auto whitespace-pre-wrap border border-border bg-black/30 p-3 font-mono-ui text-xs">
                    {command}
                  </pre>
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard title="File changes" icon={FileCode2}>
            {fileChanges.length === 0 ? (
              <p className="text-sm text-muted-foreground">No file mutation tools captured.</p>
            ) : (
              <div className="space-y-2">
                {fileChanges.map((change, index) => (
                  <pre key={`${change}-${index}`} className="overflow-auto whitespace-pre-wrap border border-border bg-secondary/20 p-3 font-mono-ui text-xs">
                    {change}
                  </pre>
                ))}
              </div>
            )}
          </SectionCard>
        </main>

        <aside className="xl:sticky xl:top-4 xl:self-start">
          <SectionCard title="Metadata / debug" icon={Code2}>
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Replay ID</span>
                <span className="font-mono-ui">{compactId(id)}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Model</span>
                <span className="max-w-[160px] truncate font-mono-ui">{session?.model ?? "unknown"}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Agent</span>
                <span>{session?.source ?? "local"}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Created</span>
                <span>{session ? formatDateTime(session.started_at) : "—"}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">Last active</span>
                <span>{session ? formatDateTime(session.last_active) : "—"}</span>
              </div>
              <Button outlined size="sm" className="w-full" onClick={() => navigator.clipboard.writeText(id)}>
                <Copy className="h-3.5 w-3.5" />
                Copy replay ID
              </Button>
            </div>
          </SectionCard>
        </aside>
      </div>
    </div>
  );
}
