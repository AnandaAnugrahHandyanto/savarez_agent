import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  ArrowUpRight,
  Bot,
  Brain,
  CalendarClock,
  CheckCircle2,
  CircleDot,
  Database,
  Fingerprint,
  Gauge,
  Globe2,
  Layers3,
  LockKeyhole,
  Radar,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Workflow,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Card, CardContent, CardHeader, CardTitle } from "@nous-research/ui/ui/components/card";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { api } from "@/lib/api";
import type {
  MissionControlCoverageItem,
  MissionControlDomainScore,
  MissionControlSnapshot,
  MissionControlStatus,
} from "@/lib/api";
import { usePageHeader } from "@/contexts/usePageHeader";
import { cn } from "@/lib/utils";
import { PluginSlot } from "@/plugins";

type AnyRecord = Record<string, unknown>;

function num(record: AnyRecord, key: string, fallback = 0): number {
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function str(record: AnyRecord, key: string, fallback = "—"): string {
  const value = record[key];
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "yes" : "no";
  return fallback;
}

function boolText(record: AnyRecord, key: string): string {
  return record[key] === true ? "yes" : "no";
}

function strArray(record: AnyRecord, key: string): string[] {
  const value = record[key];
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value);
}

function statusTone(status: MissionControlStatus): "success" | "warning" | "secondary" | "outline" {
  if (status === "active") return "success";
  if (status === "partial") return "warning";
  if (status === "watch") return "secondary";
  return "outline";
}

function statusLabel(status: MissionControlStatus): string {
  if (status === "active") return "active";
  if (status === "partial") return "partial";
  if (status === "watch") return "watch";
  if (status === "planned") return "planned";
  return String(status);
}

function ScoreRing({ value, label }: { value: number; label: string }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className="relative grid place-items-center" aria-label={`${label}: ${clamped}%`}>
      <div
        className="h-36 w-36 rounded-full p-[1px] shadow-[0_0_80px_rgba(255,230,203,0.16)]"
        style={{
          background: `conic-gradient(var(--midground-base) ${clamped * 3.6}deg, color-mix(in srgb, var(--midground-base) 10%, transparent) 0deg)`,
        }}
      >
        <div className="grid h-full w-full place-items-center rounded-full bg-background-base/92 backdrop-blur-xl">
          <div className="text-center">
            <div className="text-4xl font-semibold tracking-[-0.05em] text-midground">
              {clamped}
            </div>
            <div className="mt-1 text-[10px] uppercase tracking-[0.28em] text-text-tertiary">
              readiness
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
}: {
  label: string;
  value: string;
  detail: string;
  icon: LucideIcon;
}) {
  return (
    <Card className="min-w-0 overflow-hidden border-current/15 bg-card/70 backdrop-blur-xl">
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-[11px] uppercase tracking-[0.22em] text-text-tertiary">{label}</p>
            <p className="mt-2 truncate text-2xl font-semibold tracking-[-0.03em] text-foreground sm:text-3xl">
              {value}
            </p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{detail}</p>
          </div>
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl border border-current/15 bg-midground/10 text-midground">
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function DomainBar({ domain }: { domain: MissionControlDomainScore }) {
  return (
    <div className="min-w-0 rounded-2xl border border-current/10 bg-background-base/35 p-3" data-testid={`mission-domain-${domain.name}`}>
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="min-w-0 truncate font-medium text-foreground">{domain.name}</span>
        <span className="font-mono text-text-tertiary">{domain.score}% · {domain.items}</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-midground/10">
        <div
          className="h-full rounded-full bg-midground shadow-[0_0_24px_rgba(255,230,203,0.25)]"
          style={{ width: `${Math.max(4, Math.min(100, domain.score))}%` }}
        />
      </div>
    </div>
  );
}

function CoverageCard({ item, compact = false }: { item: MissionControlCoverageItem; compact?: boolean }) {
  return (
    <div
      className={cn(
        "group min-w-0 overflow-hidden rounded-[1.35rem] border border-current/10 bg-background-base/35 p-4 transition-colors",
        "hover:border-current/20 hover:bg-midground/[0.055]",
      )}
      data-testid={`mission-coverage-${item.id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge>
            <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-tertiary">
              {item.number ?? item.id}
            </span>
            {item.missionControl && <Badge tone="outline">route live</Badge>}
          </div>
          <h3 className="mt-3 line-clamp-2 text-base font-semibold leading-snug tracking-[-0.02em] text-foreground">
            {item.title}
          </h3>
        </div>
        <div className="shrink-0 rounded-full border border-current/10 bg-midground/10 px-2.5 py-1 font-mono text-xs text-midground">
          {item.readiness}%
        </div>
      </div>
      {!compact && (
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">{item.summary}</p>
      )}
      <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-midground/10">
        <div className="h-full rounded-full bg-midground/80" style={{ width: `${Math.max(4, item.readiness)}%` }} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2 text-[11px] text-text-tertiary">
        <span className="rounded-full border border-current/10 px-2 py-1">{item.domain}</span>
        {item.part && <span className="rounded-full border border-current/10 px-2 py-1">{item.part}</span>}
        {item.route && <span className="rounded-full border border-current/10 px-2 py-1">{item.route}</span>}
      </div>
      <div className="mt-4 space-y-1.5 text-xs leading-relaxed text-muted-foreground">
        {item.evidence.slice(0, compact ? 1 : 2).map((line) => (
          <div key={line} className="flex gap-2">
            <CircleDot className="mt-0.5 h-3.5 w-3.5 shrink-0 text-midground/70" />
            <span className="min-w-0 break-words">{line}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ActionCard({ action }: { action: MissionControlSnapshot["actionQueue"][number] }) {
  return (
    <a
      href={action.route}
      className="group block min-w-0 rounded-[1.35rem] border border-current/10 bg-background-base/40 p-4 text-left transition hover:border-current/20 hover:bg-midground/[0.06]"
    >
      <div className="flex items-start gap-3">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-midground/10 font-mono text-xs text-midground">
          {action.rank}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={action.tone === "now" ? "warning" : "outline"}>{action.tone}</Badge>
            <ArrowUpRight className="h-3.5 w-3.5 text-text-tertiary transition group-hover:text-midground" />
          </div>
          <h3 className="mt-2 text-sm font-semibold text-foreground">{action.title}</h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{action.reason}</p>
        </div>
      </div>
    </a>
  );
}

function Section({
  eyebrow,
  title,
  children,
  icon: Icon,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  icon: LucideIcon;
}) {
  return (
    <section className="space-y-4" data-testid={`mission-section-${eyebrow.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="flex items-center gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-2xl border border-current/10 bg-midground/10 text-midground">
          <Icon className="h-4 w-4" />
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-[0.24em] text-text-tertiary">{eyebrow}</p>
          <h2 className="text-lg font-semibold tracking-[-0.03em] text-foreground sm:text-xl">{title}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}

function RuntimePanel({ data }: { data: MissionControlSnapshot }) {
  const { runtime } = data;
  const model = runtime.model;
  const sessions = runtime.sessions;
  const gateway = runtime.gateway;
  const skills = runtime.skills;
  const cron = runtime.cron;
  const mcp = runtime.mcp;
  const safety = runtime.safety;
  const env = runtime.env;
  const voice = runtime.voice;
  const families = strArray(env, "families");
  const platforms = strArray(gateway, "configuredPlatforms");

  const rows = [
    ["Model", `${str(model, "provider")} · ${str(model, "model")}`, `Reasoning ${str(model, "reasoning")}`],
    ["Sessions", `${num(sessions, "total")} sessions · ${num(sessions, "messages")} messages`, `${num(sessions, "toolCalls")} tool calls`],
    ["Gateway", `${num(gateway, "configuredCount")} configured`, platforms.length ? platforms.join(", ") : `running: ${boolText(gateway, "running")}`],
    ["Skills", `${num(skills, "total")} installed`, `${num(skills, "usageTracked")} usage-tracked`],
    ["Cron", `${num(cron, "enabled")} enabled / ${num(cron, "total")} total`, "proactive and scheduled work"],
    ["MCP", `${num(mcp, "configured")} configured`, strArray(mcp, "servers").join(", ") || "no servers listed"],
    ["Safety", `approvals: ${str(safety, "approvalsMode")}`, `redaction: ${boolText(safety, "redactSecrets")}`],
    ["Voice", `STT ${boolText(voice, "sttEnabled")}`, `TTS ${str(voice, "ttsProvider", "not configured")}`],
    ["Env", `${num(env, "configuredKeys")} configured values`, families.length ? families.join(", ") : "no provider families exposed"],
  ];

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" data-testid="mission-runtime-grid">
      {rows.map(([label, value, detail]) => (
        <div key={label} className="min-w-0 rounded-2xl border border-current/10 bg-background-base/35 p-4">
          <p className="text-[11px] uppercase tracking-[0.22em] text-text-tertiary">{label}</p>
          <p className="mt-2 truncate text-sm font-semibold text-foreground">{value}</p>
          <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">{detail}</p>
        </div>
      ))}
    </div>
  );
}

export default function MissionControlPage() {
  const [data, setData] = useState<MissionControlSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { setAfterTitle, setEnd } = usePageHeader();

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .getMissionControlBlueprint()
      .then(setData)
      .catch((err) => setError(String(err)))
      .finally(() => setLoading(false));
  }, []);

  useLayoutEffect(() => {
    setAfterTitle(
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="outline">Claude Agent blueprint</Badge>
        {data && <Badge tone="success">{data.coverage.summary.readiness}% ready</Badge>}
      </div>,
    );
    setEnd(
      <Button ghost size="icon" onClick={load} disabled={loading} aria-label="Refresh Mission Control">
        {loading ? <Spinner /> : <RefreshCw />}
      </Button>,
    );
    return () => {
      setAfterTitle(null);
      setEnd(null);
    };
  }, [data, load, loading, setAfterTitle, setEnd]);

  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);

  const topSteps = useMemo(
    () => [...(data?.coverage.steps ?? [])].sort((a, b) => a.readiness - b.readiness).slice(0, 6),
    [data],
  );
  const hermesFeatures = useMemo(
    () => (data?.coverage.features ?? []).filter((f) => f.id.startsWith("H")),
    [data],
  );
  const openClawFeatures = useMemo(
    () => (data?.coverage.features ?? []).filter((f) => f.id.startsWith("O")),
    [data],
  );

  if (loading && !data) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Spinner className="text-3xl text-primary" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <p className="text-sm text-destructive">{error}</p>
          <Button className="mt-4" onClick={load}>Retry</Button>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  const sessions = data.runtime.sessions;
  const skills = data.runtime.skills;
  const cron = data.runtime.cron;
  const mcp = data.runtime.mcp;
  const summary = data.coverage.summary;

  return (
    <div className="flex flex-col gap-6 pb-[max(2rem,env(safe-area-inset-bottom))]" data-testid="mission-control-page">
      <PluginSlot name="mission-control:top" />

      <section
        className="relative isolate min-w-0 overflow-hidden rounded-[2rem] border border-current/10 bg-card/70 p-5 shadow-[0_24px_100px_rgba(0,0,0,0.32)] backdrop-blur-2xl sm:p-7 lg:p-8"
        data-testid="mission-hero"
      >
        <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_20%_20%,rgba(255,230,203,0.16),transparent_34%),radial-gradient(circle_at_80%_10%,rgba(52,211,153,0.12),transparent_30%),linear-gradient(135deg,rgba(255,255,255,0.045),transparent)]" />
        <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="outline">source: {data.source.title}</Badge>
              <Badge tone="secondary">{data.blueprint.stepCount} tracked steps</Badge>
              <Badge tone="secondary">{data.blueprint.hermesFeatureCount + data.blueprint.openclawFeatureCount} feature-picker items</Badge>
            </div>
            <h1 className="mt-5 max-w-4xl text-4xl font-semibold tracking-[-0.07em] text-foreground sm:text-5xl lg:text-6xl">
              Mission Control for the full agent blueprint.
            </h1>
            <p className="mt-5 max-w-3xl text-sm leading-7 text-muted-foreground sm:text-base">
              This is not a static mirror. Hermes maps every step, Hermes feature, and OpenClaw feature from the guide to live local runtime evidence — without exposing raw chat content, commands, logs, secrets, or absolute local paths.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <a href={data.source.url} target="_blank" rel="noreferrer">
                <Button outlined>
                  Source guide <ArrowUpRight className="ml-2 h-4 w-4" />
                </Button>
              </a>
              <a href="/system">
                <Button ghost>System evidence</Button>
              </a>
            </div>
          </div>
          <ScoreRing value={summary.readiness} label="Mission readiness" />
        </div>
      </section>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5" data-testid="mission-metrics">
        <MetricCard label="Coverage" value={`${summary.total}`} detail={`${summary.counts.active ?? 0} active · ${summary.counts.partial ?? 0} partial`} icon={Gauge} />
        <MetricCard label="Sessions" value={formatNumber(num(sessions, "total"))} detail={`${formatNumber(num(sessions, "messages"))} messages counted`} icon={Database} />
        <MetricCard label="Skills" value={formatNumber(num(skills, "total"))} detail="portable procedural memory" icon={Brain} />
        <MetricCard label="Cron" value={formatNumber(num(cron, "enabled"))} detail={`${formatNumber(num(cron, "total"))} scheduled job(s)`} icon={CalendarClock} />
        <MetricCard label="MCP" value={formatNumber(num(mcp, "configured"))} detail="configured external tool servers" icon={Workflow} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
        <Section eyebrow="operator queue" title="Smart next actions" icon={Radar}>
          <div className="grid gap-3 sm:grid-cols-2">
            {data.actionQueue.map((action) => <ActionCard key={`${action.rank}-${action.title}`} action={action} />)}
          </div>
        </Section>

        <Section eyebrow="readiness heatmap" title="Weakest domains first" icon={Activity}>
          <div className="grid gap-3">
            {data.coverage.weakestDomains.map((domain) => <DomainBar key={domain.name} domain={domain} />)}
          </div>
        </Section>
      </div>

      <Section eyebrow="live runtime" title="Smart things Mission Control can honestly show" icon={Bot}>
        <RuntimePanel data={data} />
      </Section>

      <Section eyebrow="source coverage" title="All guide steps, mapped to routes and evidence" icon={Layers3}>
        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3" data-testid="mission-step-grid">
          {data.coverage.steps.map((step) => <CoverageCard key={step.id} item={step} />)}
        </div>
      </Section>

      <div className="grid gap-6 xl:grid-cols-2">
        <Section eyebrow="Hermes picker" title="H1–H11 feature status" icon={Sparkles}>
          <div className="grid gap-3" data-testid="mission-hermes-features">
            {hermesFeatures.map((feature) => <CoverageCard key={feature.id} item={feature} compact />)}
          </div>
        </Section>
        <Section eyebrow="OpenClaw picker" title="O1–O10 production feature status" icon={Zap}>
          <div className="grid gap-3" data-testid="mission-openclaw-features">
            {openClawFeatures.map((feature) => <CoverageCard key={feature.id} item={feature} compact />)}
          </div>
        </Section>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Section eyebrow="privacy boundary" title="Useful without leaking the operator" icon={LockKeyhole}>
          <div className="grid gap-3 sm:grid-cols-2">
            {data.privacy.map((item) => (
              <div key={item.label} className="rounded-[1.35rem] border border-current/10 bg-background-base/35 p-4">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-midground" />
                  <Badge tone="outline">{item.policy}</Badge>
                </div>
                <h3 className="mt-3 text-sm font-semibold text-foreground">{item.label}</h3>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{item.detail}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section eyebrow="device proof" title="Desktop, tablet, mobile — no cockpit collapse" icon={Fingerprint}>
          <Card className="overflow-hidden bg-card/65 backdrop-blur-xl">
            <CardHeader>
              <CardTitle className="text-base">Responsive proof markers</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2 sm:grid-cols-2">
                {data.deviceProof.breakpoints.map((bp) => (
                  <div key={bp} className="rounded-2xl border border-current/10 bg-background-base/35 px-3 py-2 text-sm text-foreground">
                    <CheckCircle2 className="mr-2 inline h-4 w-4 text-midground" />
                    {bp}
                  </div>
                ))}
              </div>
              <div className="space-y-2 text-xs leading-relaxed text-muted-foreground">
                {data.deviceProof.principles.map((line) => (
                  <p key={line}>• {line}</p>
                ))}
              </div>
            </CardContent>
          </Card>
        </Section>
      </div>

      <Section eyebrow="attention" title="Lowest readiness guide steps" icon={Globe2}>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {topSteps.map((step) => <CoverageCard key={step.id} item={step} compact />)}
        </div>
      </Section>

      <p className="text-center text-xs text-text-tertiary">
        Generated {data.runtime.generatedAt}. Source checked {data.source.lastChecked}. {data.source.note}
      </p>
      <PluginSlot name="mission-control:bottom" />
    </div>
  );
}
