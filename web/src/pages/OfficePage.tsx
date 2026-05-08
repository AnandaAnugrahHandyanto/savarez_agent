import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, Bot, Building2, Clock, RefreshCw, ShieldCheck } from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api, type OfficeDataSource, type OfficeState } from "@/lib/api";

function fmt(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "number") return new Date(value * 1000).toLocaleString();
  if (typeof value !== "string") return String(value);
  if (/^\d{4}-\d{2}-\d{2}T/.test(value)) return new Date(value).toLocaleString();
  return value;
}

function textField(row: Record<string, unknown>, key: string): string {
  const value = row[key];
  return typeof value === "string" ? value : "—";
}

function numberField(row: Record<string, unknown>, key: string): number | null {
  const value = row[key];
  return typeof value === "number" ? value : null;
}

const SOURCE_TONE: Record<string, string> = {
  ok: "border-emerald-400/40 text-emerald-300",
  partial: "border-yellow-400/40 text-yellow-300",
  missing: "border-sky-400/40 text-sky-300",
  unavailable: "border-zinc-400/40 text-zinc-300",
  error: "border-red-400/40 text-red-300",
};

function SourceCard({ source }: { source: OfficeDataSource }) {
  return (
    <div className={`border bg-black/20 p-3 ${SOURCE_TONE[source.status] ?? SOURCE_TONE.missing}`}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-semibold">{source.id}</span>
        <span className="text-xs">{source.status}</span>
      </div>
      <div className="mt-2 text-xs text-midground/80">
        items {source.item_count ?? "—"} · warnings {source.warning_count ?? 0}
      </div>
      {source.error_summary ? (
        <div className="mt-2 text-xs text-red-300/90">{source.error_summary}</div>
      ) : null}
    </div>
  );
}

function EmptyLine({ label }: { label: string }) {
  return <div className="py-4 text-sm text-midground/60">No {label} in the redacted OfficeState DTO.</div>;
}

export default function OfficePage() {
  const [state, setState] = useState<OfficeState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await api.getOfficeState();
      setState(next);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .getOfficeState()
      .then((next) => {
        if (!cancelled) setState(next);
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const needsAttention = useMemo(() => {
    if (!state) return [];
    const blocked = state.work_items.map((item) => ({
      id: String(item.id),
      label: textField(item, "title"),
      detail: `work item · ${textField(item, "status")}`,
    })).filter((item) => item.detail.includes("blocked"));
    const failedAutomations = state.automations.filter(
      (job) => job.last_status === "error" || (Array.isArray(job.badges) && job.badges.includes("needs_attention")),
    ).map((job) => ({
      id: String(job.id),
      label: textField(job, "name"),
      detail: `automation · ${textField(job, "last_status")}`,
    }));
    return [...blocked, ...failedAutomations];
  }, [state]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="text-2xl text-primary" />
      </div>
    );
  }

  if (error || !state) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-red-300">
            <AlertTriangle className="h-4 w-4" /> Office unavailable
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-midground/80">{error ?? "No state returned"}</CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-6 normal-case">
      <div className="flex flex-col gap-3 border border-current/20 bg-black/20 p-5 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-emerald-300">
            <ShieldCheck className="h-4 w-4" /> Read-only MVP · localhost first
          </div>
          <h1 className="mt-2 text-3xl font-semibold uppercase tracking-wide text-foreground">
            Hermes AI Office
          </h1>
          <p className="mt-2 text-sm text-midground/80">
            Redacted operational map generated at {fmt(state.generated_at)}. Mutation controls are intentionally absent.
          </p>
        </div>
        <Button onClick={load} className="gap-2 self-start uppercase">
          <RefreshCw className="h-4 w-4" /> Refresh
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <Card>
          <CardHeader><CardTitle className="text-sm">Active work</CardTitle></CardHeader>
          <CardContent className="text-3xl text-foreground">{state.summary.active_work_count ?? 0}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Needs attention</CardTitle></CardHeader>
          <CardContent className="text-3xl text-yellow-300">{state.summary.needs_attention_count ?? 0}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Automations</CardTitle></CardHeader>
          <CardContent className="text-3xl text-foreground">{state.summary.automation_count ?? state.automations.length}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm">Redactions</CardTitle></CardHeader>
          <CardContent className="text-3xl text-foreground">{state.redactions.redacted_field_count}</CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Activity className="h-4 w-4" /> Source health</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-5">
          {state.data_sources.map((source) => <SourceCard key={source.id} source={source} />)}
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Building2 className="h-4 w-4" /> Rooms</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {state.rooms.length === 0 ? <EmptyLine label="rooms" /> : state.rooms.map((room) => (
              <div key={String(room.id)} className="border border-current/15 p-3 text-sm">
                <div className="font-semibold text-foreground">{textField(room, "display_name")}</div>
                <div className="mt-1 text-xs text-midground/70">{textField(room, "kind")} · {textField(room, "source")}</div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Bot className="h-4 w-4" /> Sessions / agents</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {state.agents.length === 0 ? <EmptyLine label="session metadata" /> : state.agents.map((agent) => (
              <div key={String(agent.id)} className="border border-current/15 p-3 text-sm">
                <div className="flex justify-between gap-3"><span className="font-semibold text-foreground">{textField(agent, "source_platform")}</span><span>{textField(agent, "status")}</span></div>
                <div className="mt-1 text-xs text-midground/70">messages {numberField(agent, "message_count") ?? 0} · title {textField(agent, "title_policy")}</div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-base">Work items</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {state.work_items.length === 0 ? <EmptyLine label="work items" /> : state.work_items.map((item) => (
              <div key={String(item.id)} className="border border-current/15 p-3 text-sm">
                <div className="flex justify-between gap-3"><span className="font-semibold text-foreground">{textField(item, "title")}</span><span>{textField(item, "status")}</span></div>
                <div className="mt-1 text-xs text-midground/70">assignee {textField(item, "assignee")} · priority {numberField(item, "priority") ?? 0}</div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Clock className="h-4 w-4" /> Automations</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {state.automations.length === 0 ? <EmptyLine label="automations" /> : state.automations.map((job) => (
              <div key={String(job.id)} className="border border-current/15 p-3 text-sm">
                <div className="flex justify-between gap-3"><span className="font-semibold text-foreground">{textField(job, "name")}</span><span>{textField(job, "state")}</span></div>
                <div className="mt-1 text-xs text-midground/70">last {fmt(job.last_status)} · next {fmt(job.next_run_at)}</div>
                {job.last_error_summary ? <div className="mt-2 text-xs text-red-300">{String(job.last_error_summary)}</div> : null}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">Recent safe events</CardTitle></CardHeader>
        <CardContent>
          {state.events.length === 0 ? <EmptyLine label="events" /> : (
            <div className="grid gap-2 md:grid-cols-2">
              {state.events.slice(-12).map((event) => (
                <div key={String(event.id)} className="border border-current/15 p-2 text-xs">
                  <div className="font-semibold text-foreground">{textField(event, "kind")}</div>
                  <div className="mt-1 text-midground/70">{textField(event, "source")} · {fmt(event.created_at)}</div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">Needs attention</CardTitle></CardHeader>
        <CardContent>
          {needsAttention.length === 0 ? <div className="text-sm text-emerald-300">No blocked work or failed automations in the redacted DTO.</div> : (
            <div className="space-y-2">{needsAttention.map((item) => <div key={item.id} className="border border-yellow-300/30 p-2 text-sm text-yellow-200"><span className="font-semibold">{item.label}</span><span className="ml-2 text-xs text-yellow-100/70">{item.detail}</span></div>)}</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
