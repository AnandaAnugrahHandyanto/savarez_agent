import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Archive,
  Bot,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileText,
  Gauge,
  Layers3,
  ShieldCheck,
} from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@nous-research/ui/ui/components/card";
import { cn } from "@/lib/utils";
import {
  getSourceRefs,
  virtualHqData,
  type AgentStatus,
  type ApprovalItem,
  type Confidence,
  type ContextPack,
  type DataMode,
  type ErrorState,
  type EvidenceRef,
  type ProductZone,
  type ProjectStatus,
  type RedactionState,
  type SourceRef,
  type SystemStatus,
} from "@/lib/virtual-hq";

type DrawerItem =
  | { kind: "agent"; title: string; sourceIds: string[]; data: AgentStatus }
  | { kind: "project"; title: string; sourceIds: string[]; data: ProjectStatus }
  | { kind: "approval"; title: string; sourceIds: string[]; data: ApprovalItem }
  | { kind: "evidence"; title: string; sourceIds: string[]; data: EvidenceRef }
  | { kind: "context"; title: string; sourceIds: string[]; data: ContextPack }
  | { kind: "system"; title: string; sourceIds: string[]; data: SystemStatus }
  | { kind: "zone"; title: string; sourceIds: string[]; data: ProductZone };

const confidenceClass: Record<Confidence, string> = {
  verified: "border-emerald-400/40 bg-emerald-500/10 text-emerald-200",
  inferred: "border-sky-400/40 bg-sky-500/10 text-sky-200",
  unknown: "border-amber-400/40 bg-amber-500/10 text-amber-200",
};

const dataModeClass: Record<DataMode, string> = {
  real: "border-emerald-400/40 bg-emerald-500/10 text-emerald-200",
  mock: "border-violet-400/40 bg-violet-500/10 text-violet-200",
  not_connected: "border-amber-400/40 bg-amber-500/10 text-amber-200",
};

const errorClass: Record<ErrorState, string> = {
  none: "border-emerald-400/40 bg-emerald-500/10 text-emerald-200",
  source_missing: "border-orange-400/40 bg-orange-500/10 text-orange-200",
  stale: "border-yellow-400/40 bg-yellow-500/10 text-yellow-200",
  permission_denied: "border-red-400/40 bg-red-500/10 text-red-200",
  parse_failed: "border-red-400/40 bg-red-500/10 text-red-200",
  not_connected: "border-amber-400/40 bg-amber-500/10 text-amber-200",
};

const redactionClass: Record<RedactionState, string> = {
  safe: "border-emerald-400/40 bg-emerald-500/10 text-emerald-200",
  redacted: "border-sky-400/40 bg-sky-500/10 text-sky-200",
  sensitive_hidden: "border-amber-400/40 bg-amber-500/10 text-amber-200",
};

function formatWhen(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function DataBadge({ label, className }: { label: string; className: string }) {
  return (
    <Badge className={cn("border px-2 py-0.5 font-mono-ui text-[11px] normal-case", className)}>
      {label}
    </Badge>
  );
}

function MetaBadges({
  confidence,
  errorState,
  redactionState,
  dataMode,
}: {
  confidence: Confidence;
  errorState: ErrorState;
  redactionState: RedactionState;
  dataMode: DataMode;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <DataBadge label={confidence} className={confidenceClass[confidence]} />
      <DataBadge label={errorState} className={errorClass[errorState]} />
      <DataBadge label={redactionState} className={redactionClass[redactionState]} />
      <DataBadge label={dataMode} className={dataModeClass[dataMode]} />
    </div>
  );
}

function SourceTrail({ sourceIds }: { sourceIds: string[] }) {
  const sources = getSourceRefs(sourceIds);
  return (
    <div className="mt-3 space-y-1.5 border-t border-border/60 pt-3">
      <div className="font-mono-ui text-[11px] uppercase tracking-[0.16em] text-text-tertiary">
        Source / timestamp
      </div>
      {sources.length === 0 ? (
        <div className="text-sm text-amber-200">source_missing — no source refs are attached</div>
      ) : (
        sources.map((source) => (
          <div key={source.id} className="rounded-md border border-border/70 bg-background/40 p-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-foreground">{source.label}</span>
              <DataBadge label={source.dataMode} className={dataModeClass[source.dataMode]} />
              <DataBadge label={source.confidence} className={confidenceClass[source.confidence]} />
              <DataBadge label={source.errorState} className={errorClass[source.errorState]} />
            </div>
            <div className="mt-1 break-all font-mono-ui text-xs text-text-secondary">{source.location}</div>
            <div className="mt-1 text-xs text-text-tertiary">updated {formatWhen(source.updatedAt)} · {source.truth}</div>
          </div>
        ))
      )}
    </div>
  );
}

function SectionCard({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: typeof Bot;
  children: React.ReactNode;
}) {
  return (
    <Card className="border-border/80 bg-card/70 backdrop-blur">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon className="h-4 w-4 text-muted-foreground" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function ReadOnlyCard({
  title,
  subtitle,
  status,
  sourceIds,
  confidence,
  errorState,
  redactionState,
  dataMode,
  onInspect,
}: {
  title: string;
  subtitle: string;
  status: string;
  sourceIds: string[];
  confidence: Confidence;
  errorState: ErrorState;
  redactionState: RedactionState;
  dataMode: DataMode;
  onInspect: () => void;
}) {
  return (
    <div
      className="group cursor-pointer rounded-lg border border-border/80 bg-background/45 p-3 transition hover:border-primary/60 hover:bg-muted/40"
      onClick={onInspect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") onInspect();
      }}
      role="button"
      tabIndex={0}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-medium text-foreground">{title}</h3>
          <p className="mt-1 text-sm text-text-secondary">{subtitle}</p>
        </div>
        <DataBadge label={status} className={errorState === "none" ? confidenceClass[confidence] : errorClass[errorState]} />
      </div>
      <div className="mt-3">
        <MetaBadges
          confidence={confidence}
          errorState={errorState}
          redactionState={redactionState}
          dataMode={dataMode}
        />
      </div>
      <SourceTrail sourceIds={sourceIds} />
    </div>
  );
}

function DetailDrawer({ item, sources }: { item: DrawerItem; sources: SourceRef[] }) {
  const detailRows = Object.entries(item.data).filter(([, value]) => {
    return typeof value === "string" || value === null || Array.isArray(value);
  });

  return (
    <aside className="sticky top-4 max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-xl border border-border bg-card/90 p-4 shadow-2xl backdrop-blur">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-5 w-5 text-emerald-200" />
        <div>
          <div className="font-mono-ui text-[11px] uppercase tracking-[0.18em] text-text-tertiary">Read-only drawer</div>
          <h2 className="text-lg font-semibold text-foreground">{item.title}</h2>
        </div>
      </div>
      <p className="mt-3 rounded-md border border-emerald-400/25 bg-emerald-500/10 p-3 text-sm text-emerald-100">
        View-only details. This drawer intentionally exposes no restart, deploy, merge, config, memory-write, or external-send controls.
      </p>
      <div className="mt-4 space-y-2">
        {detailRows.map(([key, value]) => (
          <div key={key} className="rounded-md border border-border/70 bg-background/40 p-2">
            <div className="font-mono-ui text-[11px] uppercase tracking-[0.14em] text-text-tertiary">{key}</div>
            <div className="mt-1 text-sm text-foreground">
              {Array.isArray(value) ? value.join(", ") || "none" : value ?? "none"}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-4 space-y-2">
        <div className="font-mono-ui text-[11px] uppercase tracking-[0.18em] text-text-tertiary">Resolved source registry</div>
        {sources.map((source) => (
          <div key={source.id} className="rounded-md border border-border/70 bg-background/40 p-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">{source.label}</span>
              <DataBadge label={source.redactionState} className={redactionClass[source.redactionState]} />
            </div>
            <div className="mt-1 break-all font-mono-ui text-xs text-text-secondary">{source.location}</div>
            <div className="mt-1 text-xs text-text-tertiary">{formatWhen(source.updatedAt)}</div>
          </div>
        ))}
      </div>
    </aside>
  );
}

export default function VirtualHqPage() {
  const defaultItem: DrawerItem = useMemo(
    () => ({
      kind: "context",
      title: "Hermes Virtual HQ R1 Context Pack",
      sourceIds: virtualHqData.contextPacks[0]?.sourceRefs ?? [],
      data: virtualHqData.contextPacks[0],
    }),
    [],
  );
  const [drawerItem, setDrawerItem] = useState<DrawerItem>(defaultItem);
  const drawerSources = getSourceRefs(drawerItem.sourceIds);

  return (
    <div className="h-full overflow-y-auto p-4 md:p-6">
      <div className="mx-auto max-w-7xl space-y-6">
        <header className="rounded-xl border border-border/80 bg-card/75 p-5 backdrop-blur">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <DataBadge label="R1 P0+P1" className="border-cyan-400/40 bg-cyan-500/10 text-cyan-200" />
                <DataBadge label="read-only" className="border-emerald-400/40 bg-emerald-500/10 text-emerald-200" />
                <DataBadge label="no side effects" className="border-amber-400/40 bg-amber-500/10 text-amber-200" />
              </div>
              <h1 className="mt-3 text-3xl font-semibold tracking-tight text-foreground">Hermes Virtual HQ</h1>
              <p className="mt-2 max-w-3xl text-text-secondary">
                Operational command-center MVP for Agent, Project, Approval, Evidence, System, and Context panels. Every visible status carries source, timestamp, confidence, error, redaction, and mock/not_connected boundary labels.
              </p>
            </div>
            <div className="rounded-lg border border-border/70 bg-background/45 p-3 text-sm text-text-secondary">
              <div className="font-mono-ui text-[11px] uppercase tracking-[0.16em] text-text-tertiary">Generated</div>
              <div className="mt-1 text-foreground">{formatWhen(virtualHqData.generatedAt)}</div>
              <div className="mt-2 text-xs">Source registry: {virtualHqData.sourceRegistry.length} entries · execute controls: 0</div>
            </div>
          </div>
        </header>

        <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
          <main className="space-y-6">
            <SectionCard title="Product zones and panel list" icon={Layers3}>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {virtualHqData.productZones.map((zone) => (
                  <ReadOnlyCard
                    key={zone.id}
                    title={zone.name}
                    subtitle={`${zone.panel}: ${zone.purpose}`}
                    status={zone.scope}
                    sourceIds={zone.sourceRefs}
                    confidence="verified"
                    errorState="none"
                    redactionState="safe"
                    dataMode="real"
                    onInspect={() => setDrawerItem({ kind: "zone", title: zone.name, sourceIds: zone.sourceRefs, data: zone })}
                  />
                ))}
              </div>
            </SectionCard>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="Agent Status Board" icon={Bot}>
                <div className="space-y-3">
                  {virtualHqData.agents.map((agent) => (
                    <ReadOnlyCard
                      key={agent.agentId}
                      title={agent.displayName}
                      subtitle={`${agent.role} · ${agent.currentFocus}`}
                      status={agent.state}
                      sourceIds={agent.sourceRefs}
                      confidence={agent.confidence}
                      errorState={agent.errorState}
                      redactionState={agent.redactionState}
                      dataMode={agent.dataMode}
                      onInspect={() => setDrawerItem({ kind: "agent", title: agent.displayName, sourceIds: agent.sourceRefs, data: agent })}
                    />
                  ))}
                </div>
              </SectionCard>

              <SectionCard title="Project Status Board" icon={ClipboardCheck}>
                <div className="space-y-3">
                  {virtualHqData.projects.map((project) => (
                    <ReadOnlyCard
                      key={project.projectId}
                      title={project.name}
                      subtitle={`${project.phase} · next: ${project.nextAction}`}
                      status={project.state}
                      sourceIds={project.sourceRefs}
                      confidence={project.confidence}
                      errorState={project.errorState}
                      redactionState={project.redactionState}
                      dataMode={project.dataMode}
                      onInspect={() => setDrawerItem({ kind: "project", title: project.name, sourceIds: project.sourceRefs, data: project })}
                    />
                  ))}
                </div>
              </SectionCard>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="Approval Desk" icon={CheckCircle2}>
                <div className="space-y-3">
                  {virtualHqData.approvals.map((approval) => (
                    <ReadOnlyCard
                      key={approval.approvalId}
                      title={approval.decisionNeeded}
                      subtitle={`${approval.recommendation} Risk: ${approval.riskLevel}.`}
                      status={approval.status}
                      sourceIds={approval.sourceRefs}
                      confidence={approval.confidence}
                      errorState={approval.errorState}
                      redactionState={approval.redactionState}
                      dataMode={approval.dataMode}
                      onInspect={() => setDrawerItem({ kind: "approval", title: approval.decisionNeeded, sourceIds: approval.sourceRefs, data: approval })}
                    />
                  ))}
                </div>
              </SectionCard>

              <SectionCard title="Evidence Panel" icon={Archive}>
                <div className="space-y-3">
                  {virtualHqData.evidence.map((evidence) => (
                    <ReadOnlyCard
                      key={evidence.evidenceId}
                      title={evidence.title}
                      subtitle={`${evidence.type} · verified by ${evidence.verifiedBy}`}
                      status={evidence.redactionState}
                      sourceIds={evidence.sourceRefs}
                      confidence={evidence.verifiedBy.startsWith("pending") ? "unknown" : "verified"}
                      errorState={evidence.verifiedBy.startsWith("pending") ? "source_missing" : "none"}
                      redactionState={evidence.redactionState}
                      dataMode="real"
                      onInspect={() => setDrawerItem({ kind: "evidence", title: evidence.title, sourceIds: evidence.sourceRefs, data: evidence })}
                    />
                  ))}
                </div>
              </SectionCard>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <SectionCard title="Context Pack Drawer" icon={FileText}>
                <div className="space-y-3">
                  {virtualHqData.contextPacks.map((context) => (
                    <ReadOnlyCard
                      key={context.contextId}
                      title={context.summary}
                      subtitle={`Must know: ${context.mustKnow.join(" · ")}`}
                      status={context.freshness}
                      sourceIds={context.sourceRefs}
                      confidence={context.confidence}
                      errorState={context.errorState}
                      redactionState={context.redactionState}
                      dataMode={context.dataMode}
                      onInspect={() => setDrawerItem({ kind: "context", title: context.summary, sourceIds: context.sourceRefs, data: context })}
                    />
                  ))}
                </div>
              </SectionCard>

              <SectionCard title="Command Wall System Status" icon={Gauge}>
                <div className="space-y-3">
                  {virtualHqData.systems.map((system) => (
                    <ReadOnlyCard
                      key={system.serviceId}
                      title={system.displayName}
                      subtitle={`last check: ${formatWhen(system.lastCheckAt)}`}
                      status={system.state}
                      sourceIds={system.sourceRefs}
                      confidence={system.confidence}
                      errorState={system.errorState}
                      redactionState={system.redactionState}
                      dataMode={system.dataMode}
                      onInspect={() => setDrawerItem({ kind: "system", title: system.displayName, sourceIds: system.sourceRefs, data: system })}
                    />
                  ))}
                </div>
              </SectionCard>
            </div>

            <SectionCard title="Mock vs real boundary and security rules" icon={Database}>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-lg border border-emerald-400/30 bg-emerald-500/10 p-3">
                  <div className="font-medium text-emerald-100">Real source refs</div>
                  <p className="mt-1 text-sm text-emerald-100/80">Notes and Kanban references are shown as real only when a source path or card id is present.</p>
                </div>
                <div className="rounded-lg border border-amber-400/30 bg-amber-500/10 p-3">
                  <div className="font-medium text-amber-100">not_connected</div>
                  <p className="mt-1 text-sm text-amber-100/80">Live profile and service adapters are intentionally labeled not_connected instead of inventing health or activity.</p>
                </div>
                <div className="rounded-lg border border-red-400/30 bg-red-500/10 p-3">
                  <div className="flex items-center gap-2 font-medium text-red-100"><AlertTriangle className="h-4 w-4" /> Side-effect controls</div>
                  <p className="mt-1 text-sm text-red-100/80">No deploy, restart, merge, config, billing, external-send, or durable memory write controls are rendered in this R1 page.</p>
                </div>
              </div>
            </SectionCard>
          </main>

          <DetailDrawer item={drawerItem} sources={drawerSources} />
        </div>
      </div>
    </div>
  );
}
