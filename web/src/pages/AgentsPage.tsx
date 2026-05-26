import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ExternalLink,
  RefreshCw,
  Save,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  ManagedAgentEntry,
  ManagedAgentsResponse,
  ManagedModelEntry,
} from "@/lib/api";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Stats } from "@nous-research/ui/ui/components/stats";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { usePageHeader } from "@/contexts/usePageHeader";
import { timeAgo } from "@/lib/utils";

const PERIODS = [
  { label: "7d", days: 7 },
  { label: "30d", days: 30 },
  { label: "90d", days: 90 },
] as const;

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n || 0);
}

function formatCost(n: number): string {
  if (n >= 1) return `$${n.toFixed(2)}`;
  if (n > 0) return `$${n.toFixed(4)}`;
  return "$0";
}

function usageTotal(agent: ManagedAgentEntry): number {
  const u = agent.usage;
  return (
    (u.input_tokens || 0) +
    (u.output_tokens || 0) +
    (u.cache_read_tokens || 0) +
    (u.reasoning_tokens || 0)
  );
}

function statusTone(status: string): "success" | "warning" | "secondary" | "destructive" {
  const normalized = status.toLowerCase();
  if (normalized === "active") return "success";
  if (normalized === "experimental") return "warning";
  if (normalized === "deprecated") return "destructive";
  return "secondary";
}

function sourceTone(source: string): "success" | "warning" | "secondary" | "destructive" {
  if (source === "live") return "success";
  if (source === "cache" || source === "manual") return "warning";
  return "secondary";
}

function ModelLabel({ model }: { model?: ManagedModelEntry }) {
  if (!model) return <span className="text-muted-foreground">Unknown model</span>;
  return (
    <span className="min-w-0">
      <span className="block truncate font-medium">{model.model_ref}</span>
      <span className="block truncate text-[11px] text-muted-foreground">
        {model.provider} / {model.model}
      </span>
    </span>
  );
}

function SubscriptionCell({ model }: { model?: ManagedModelEntry }) {
  const sub = model?.subscription;
  if (!sub || sub.source === "unavailable") {
    return <span className="text-xs text-muted-foreground">No subscription data</span>;
  }
  return (
    <div className="min-w-[10rem] space-y-1 text-xs">
      <div className="flex items-center gap-1.5">
        <Badge tone={sourceTone(sub.source)}>{sub.source}</Badge>
        {sub.usage_percent !== null && sub.usage_percent !== undefined ? (
          <span>{sub.usage_percent.toFixed(1)}% used</span>
        ) : null}
      </div>
      <div className="text-muted-foreground">
        {sub.monthly_limit_usd ? `$${sub.monthly_limit_usd}/mo` : "limit n/a"}
        {sub.expires_at ? ` · expires ${sub.expires_at}` : ""}
      </div>
      {sub.reset_at ? (
        <div className="text-muted-foreground">resets {sub.reset_at}</div>
      ) : null}
      {sub.error ? (
        <div className="line-clamp-2 text-[11px] text-amber-600 dark:text-amber-400">
          {sub.error}
        </div>
      ) : null}
    </div>
  );
}

function AgentModelSelect({
  agent,
  models,
  modelByRef,
  onSaved,
}: {
  agent: ManagedAgentEntry;
  models: ManagedModelEntry[];
  modelByRef: Map<string, ManagedModelEntry>;
  onSaved: () => void;
}) {
  const [selected, setSelected] = useState(agent.model_ref);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = selected !== agent.model_ref;

  useEffect(() => {
    setSelected(agent.model_ref);
    setError(null);
  }, [agent.agent_id, agent.model_ref]);

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.setManagedAgentModel(agent.agent_id, { model_ref: selected });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!agent.editable) {
    return (
      <div className="min-w-[14rem] space-y-1">
        <div className="flex items-center gap-1.5 text-xs font-medium">
          <ExternalLink className="h-3.5 w-3.5" />
          External CLI default
        </div>
        <div className="text-[11px] text-muted-foreground">
          {agent.runtime || "external runtime"} controls this model.
        </div>
      </div>
    );
  }

  return (
    <div className="min-w-[17rem] space-y-1.5">
      <div className="flex gap-2">
        <select
          className="h-8 min-w-0 flex-1 border border-border bg-background px-2 text-xs"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          disabled={busy}
        >
          {models
            .filter((m) => m.status !== "deprecated" || m.model_ref === agent.model_ref)
            .map((m) => (
              <option key={m.model_ref} value={m.model_ref}>
                {m.model_ref} · {m.provider}/{m.model}
              </option>
            ))}
        </select>
        <Button
          size="sm"
          className="h-8 px-2"
          disabled={!dirty || busy}
          onClick={save}
          prefix={busy ? <Spinner /> : <Save className="h-3.5 w-3.5" />}
        >
          Save
        </Button>
      </div>
      <ModelLabel model={modelByRef.get(selected)} />
      {error ? <div className="text-[11px] text-destructive">{error}</div> : null}
    </div>
  );
}

export default function AgentsPage() {
  const { setTitle } = usePageHeader();
  const [period, setPeriod] = useState<(typeof PERIODS)[number]>(PERIODS[1]);
  const [data, setData] = useState<ManagedAgentsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.getManagedAgents(period.days));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [period.days]);

  useEffect(() => {
    setTitle("Agent Control");
    return () => setTitle(null);
  }, [setTitle]);

  useEffect(() => {
    load();
  }, [load]);

  const models = data?.models ?? [];
  const agents = data?.agents ?? [];
  const modelByRef = useMemo(
    () => new Map(models.map((m) => [m.model_ref, m])),
    [models],
  );
  const editableCount = agents.filter((a) => a.editable).length;
  const externalCount = agents.length - editableCount;
  const sortedAgents = useMemo(
    () => [...agents].sort((a, b) => usageTotal(b) - usageTotal(a)),
    [agents],
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {PERIODS.map((p) => (
            <Button
              key={p.label}
              size="sm"
              outlined={period.days !== p.days}
              onClick={() => setPeriod(p)}
            >
              {p.label}
            </Button>
          ))}
        </div>
        <Button
          size="sm"
          outlined
          onClick={load}
          disabled={loading}
          prefix={loading ? <Spinner /> : <RefreshCw className="h-4 w-4" />}
        >
          Refresh
        </Button>
      </div>

      {error ? (
        <Card className="border-destructive/40">
          <CardContent className="flex items-center gap-2 py-4 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4" />
            {error}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-3 md:grid-cols-4">
        <Card>
          <CardContent className="py-4">
            <Stats
              items={[
                { label: "Agents", value: String(agents.length) },
                { label: "Editable", value: String(editableCount) },
                { label: "External CLI", value: String(externalCount) },
                { label: "Est. Cost", value: formatCost(data?.totals.estimated_cost ?? 0) },
              ]}
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-base">Agent Model Assignments</CardTitle>
            <div className="text-xs text-muted-foreground">
              {formatTokens((data?.totals.input_tokens ?? 0) + (data?.totals.output_tokens ?? 0))} tokens ·{" "}
              {data?.totals.api_calls ?? 0} calls · attribution{" "}
              {data ? `${data.totals.agent_attributed_events}/${data.totals.agent_attributed_events + data.totals.agent_unknown_events}` : "0/0"}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading && !data ? (
            <div className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
              <Spinner /> Loading agents...
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1100px] text-left text-sm">
                <thead className="border-b border-border text-xs text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-4 font-medium">Agent</th>
                    <th className="py-2 pr-4 font-medium">Model</th>
                    <th className="py-2 pr-4 font-medium">Runtime</th>
                    <th className="py-2 pr-4 font-medium">Usage</th>
                    <th className="py-2 pr-4 font-medium">Subscription</th>
                    <th className="py-2 font-medium">Tools</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {sortedAgents.map((agent) => {
                    const model = modelByRef.get(agent.model_ref);
                    return (
                      <tr key={agent.agent_id} className="align-top">
                        <td className="py-3 pr-4">
                          <div className="max-w-[18rem] space-y-1">
                            <div className="font-medium">{agent.display_name}</div>
                            <div className="font-mono text-[11px] text-muted-foreground">{agent.agent_id}</div>
                            <div className="line-clamp-2 text-xs text-muted-foreground">
                              {agent.role_summary}
                            </div>
                          </div>
                        </td>
                        <td className="py-3 pr-4">
                          <AgentModelSelect
                            agent={agent}
                            models={models}
                            modelByRef={modelByRef}
                            onSaved={load}
                          />
                        </td>
                        <td className="py-3 pr-4">
                          <div className="space-y-1">
                            <Badge tone={agent.editable ? "success" : "secondary"}>
                              {agent.editable ? "managed" : "external"}
                            </Badge>
                            <div className="text-xs text-muted-foreground">
                              {agent.runtime || "native"}
                            </div>
                            {model ? (
                              <Badge tone={statusTone(model.status)}>{model.status}</Badge>
                            ) : null}
                          </div>
                        </td>
                        <td className="py-3 pr-4">
                          <div className="space-y-1 text-xs">
                            <div className="font-medium">{formatTokens(usageTotal(agent))} tokens</div>
                            <div className="text-muted-foreground">
                              {agent.usage.api_calls} calls · {agent.usage.runs} runs
                            </div>
                            {agent.usage.last_used_at ? (
                              <div className="text-muted-foreground">
                                {timeAgo(agent.usage.last_used_at)}
                              </div>
                            ) : null}
                          </div>
                        </td>
                        <td className="py-3 pr-4">
                          <SubscriptionCell model={model} />
                        </td>
                        <td className="py-3">
                          <div className="flex max-w-[16rem] flex-wrap gap-1">
                            {agent.tools.map((tool) => (
                              <span
                                key={tool}
                                className="bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
                              >
                                {tool}
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
