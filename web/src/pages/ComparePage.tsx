import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, GitCompare, Wrench, XCircle } from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { SessionInfo } from "@/lib/api";
import { usePageHeader } from "@/contexts/usePageHeader";
import { compactId, formatDuration, formatTokens, getSessionStatus, statusTone } from "./replayHelpers";

function SessionPicker({
  label,
  value,
  sessions,
  onChange,
}: {
  label: string;
  value: string;
  sessions: SessionInfo[];
  onChange: (id: string) => void;
}) {
  return (
    <label className="flex flex-col gap-2 text-sm">
      <span className="text-xs uppercase tracking-[0.14em] text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="border border-border bg-background px-3 py-2 text-sm text-foreground"
      >
        <option value="">Choose a session</option>
        {sessions.map((session) => (
          <option key={session.id} value={session.id}>
            {(session.title && session.title !== "Untitled" ? session.title : session.preview) ?? compactId(session.id)}
          </option>
        ))}
      </select>
    </label>
  );
}

function CompareMetric({
  label,
  left,
  right,
}: {
  label: string;
  left: string | number;
  right: string | number;
}) {
  const same = String(left) === String(right);
  return (
    <tr className="border-b border-border last:border-0">
      <td className="px-3 py-3 text-xs uppercase tracking-[0.12em] text-muted-foreground">{label}</td>
      <td className="px-3 py-3">{left}</td>
      <td className="px-3 py-3">{right}</td>
      <td className="px-3 py-3">
        {same ? (
          <Badge tone="outline" className="text-[10px]">same</Badge>
        ) : (
          <Badge tone="warning" className="text-[10px]">diff</Badge>
        )}
      </td>
    </tr>
  );
}

function SessionCard({ title, session }: { title: string; session: SessionInfo | null }) {
  const navigate = useNavigate();
  if (!session) {
    return (
      <Card>
        <CardContent className="p-6 text-sm text-muted-foreground">Select {title.toLowerCase()}.</CardContent>
      </Card>
    );
  }
  const status = getSessionStatus(session);
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-3 text-base">
          <span>{title}</span>
          <Badge tone={statusTone(status)} className="capitalize text-[10px]">{status}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div>
          <p className="font-medium">{session.title ?? "Untitled session"}</p>
          <p className="font-mono-ui text-xs text-muted-foreground">{compactId(session.id)}</p>
        </div>
        <p className="line-clamp-3 text-sm text-muted-foreground">{session.preview ?? "No preview captured."}</p>
        <Button outlined size="sm" onClick={() => navigate(`/replay/${encodeURIComponent(session.id)}`)}>
          Open replay
          <ArrowRight className="h-3.5 w-3.5" />
        </Button>
      </CardContent>
    </Card>
  );
}

export default function ComparePage() {
  const [params, setParams] = useSearchParams();
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const { setAfterTitle, setEnd } = usePageHeader();
  const leftId = params.get("left") ?? "";
  const rightId = params.get("right") ?? "";

  useEffect(() => {
    api
      .getSessions(200)
      .then((response) => setSessions(response.sessions))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useLayoutEffect(() => {
    setAfterTitle(<Badge tone="secondary" className="text-xs">Power workflow</Badge>);
    setEnd(null);
    return () => {
      setAfterTitle(null);
      setEnd(null);
    };
  }, [setAfterTitle, setEnd]);

  const left = useMemo(() => sessions.find((session) => session.id === leftId) ?? null, [leftId, sessions]);
  const right = useMemo(() => sessions.find((session) => session.id === rightId) ?? null, [rightId, sessions]);

  const updateParam = (key: "left" | "right", value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="text-2xl text-primary" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-xl">
            <GitCompare className="h-5 w-5 text-primary" />
            Compare sessions
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-sm text-muted-foreground">
            Use this advanced workflow to compare successful and failed runs, spot regressions, and identify the action that diverged.
          </p>
          <div className="grid gap-4 md:grid-cols-[1fr_auto_1fr] md:items-end">
            <SessionPicker label="Left replay" value={leftId} sessions={sessions} onChange={(value) => updateParam("left", value)} />
            <div className="hidden pb-2 text-muted-foreground md:block">vs</div>
            <SessionPicker label="Right replay" value={rightId} sessions={sessions} onChange={(value) => updateParam("right", value)} />
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <SessionCard title="Left replay" session={left} />
        <SessionCard title="Right replay" session={right} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Diff summary</CardTitle>
        </CardHeader>
        <CardContent>
          {!left || !right ? (
            <p className="text-sm text-muted-foreground">Pick two sessions to generate a comparison.</p>
          ) : (
            <div className="overflow-x-auto border border-border">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="border-b border-border bg-secondary/40 text-xs text-muted-foreground">
                  <tr>
                    <th className="px-3 py-3">Metric</th>
                    <th className="px-3 py-3">Left</th>
                    <th className="px-3 py-3">Right</th>
                    <th className="px-3 py-3">Signal</th>
                  </tr>
                </thead>
                <tbody>
                  <CompareMetric label="Outcome" left={getSessionStatus(left)} right={getSessionStatus(right)} />
                  <CompareMetric label="Model" left={left.model ?? "unknown"} right={right.model ?? "unknown"} />
                  <CompareMetric label="Duration" left={formatDuration(left)} right={formatDuration(right)} />
                  <CompareMetric label="Messages" left={left.message_count} right={right.message_count} />
                  <CompareMetric label="Tool calls" left={left.tool_call_count} right={right.tool_call_count} />
                  <CompareMetric label="Tokens" left={formatTokens(left)} right={formatTokens(right)} />
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="flex items-start gap-3 p-4">
            <CheckCircle2 className="mt-1 h-4 w-4 text-success" />
            <div>
              <p className="font-medium">Best use</p>
              <p className="text-sm text-muted-foreground">Compare a green run against a failed replay.</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-start gap-3 p-4">
            <Wrench className="mt-1 h-4 w-4 text-warning" />
            <div>
              <p className="font-medium">Action signal</p>
              <p className="text-sm text-muted-foreground">Large tool-call deltas usually identify the divergence.</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-start gap-3 p-4">
            <XCircle className="mt-1 h-4 w-4 text-destructive" />
            <div>
              <p className="font-medium">Failure signal</p>
              <p className="text-sm text-muted-foreground">Open the failed replay to inspect its incident summary first.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
