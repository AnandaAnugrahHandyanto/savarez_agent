import {
  ArrowDown,
  ArrowRight,
  Blocks,
  Bot,
  Briefcase,
  Building2,
  Database,
  Eye,
  Handshake,
  KeyRound,
  Layers3,
  Library,
  Lock,
  Network,
  Route,
  Scale,
  Shield,
  Sparkles,
  Users,
  Workflow,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface LayerCardData {
  name: string;
  scope: string;
  owner: string;
  persists: string[];
  examples: string[];
  icon: React.ComponentType<{ className?: string }>;
}

const ARCHITECTURE_LAYERS: LayerCardData[] = [
  {
    name: "Enterprise / Privileged orchestration",
    scope: "Cross-domain oversight, policy, audit, executive synthesis",
    owner: "Exec + platform governance",
    persists: ["constitution", "global policy", "approval classes"],
    examples: ["Admin governance", "CFO insights", "risk / audit worker"],
    icon: Shield,
  },
  {
    name: "Domain ownership",
    scope: "Department-level context, memory, skills, and approved systems",
    owner: "Finance / HR / Marketing / BI domain owners",
    persists: ["domain memory", "tool registry", "policy overlay"],
    examples: ["Finance", "HR", "Marketing", "BI"],
    icon: Building2,
  },
  {
    name: "Functional capability",
    scope: "Recurring process clusters inside a domain",
    owner: "Process owners + builders",
    persists: ["runbooks", "functional skills", "KPIs / SLAs"],
    examples: ["R2R", "P2P", "O2C", "incident triage"],
    icon: Workflow,
  },
  {
    name: "Workflow execution",
    scope: "Single workflow units that should be narrow, testable, and bounded",
    owner: "Ops / workflow maintainers",
    persists: ["task templates", "approval steps", "evidence schema"],
    examples: ["bank reconciliation", "invoice exception", "ticket routing"],
    icon: Route,
  },
  {
    name: "Runtime task workers",
    scope: "Ephemeral workers created under least privilege to do a specific job",
    owner: "Harness runtime",
    persists: ["event log", "output artifacts"],
    examples: ["run recon for account X", "prepare approval pack", "draft escalation"],
    icon: Bot,
  },
];

const CONTROL_PANELS = [
  {
    title: "SOUL",
    icon: Sparkles,
    summary: "Persistent identity belongs to enterprise, domain, and workstream — not to the temporary worker instance.",
    layers: [
      "Enterprise: constitution and non-negotiables",
      "Domain: operating posture and vocabulary",
      "Workstream: judgment rules and escalation norms",
      "Runtime: temporary posture like reviewer / executor / triage",
    ],
  },
  {
    title: "MEMORY",
    icon: Database,
    summary: "Separate policy, semantic, procedural, episodic, profile, and scratch memory. Promotion into durable memory must be governed.",
    layers: [
      "Policy memory: authoritative controls",
      "Semantic memory: approved organizational knowledge",
      "Procedural memory: skills, runbooks, tested routines",
      "Episodic memory: what happened, what was decided, what worked",
      "Scratch memory: runtime-only context, never durable by default",
    ],
  },
  {
    title: "SKILLS",
    icon: Library,
    summary: "Skills are versioned capabilities layered from enterprise foundation to domain to workstream to guarded actions.",
    layers: [
      "Foundation skills: summarize, search, extract, route",
      "Domain skills: finance / HR / legal / engineering packs",
      "Workstream skills: recon, approval prep, escalation routing",
      "Guarded skills: payment, entitlement, prod change, external communications",
    ],
  },
  {
    title: "GUARDRAILS",
    icon: Lock,
    summary: "Policy must live outside the model. Permissions, approvals, action thresholds, and data boundaries govern every layer.",
    layers: [
      "Constitutional guardrails: global never-do rules",
      "Domain guardrails: domain-specific thresholds",
      "Workstream guardrails: stage gates and max autonomy",
      "Runtime guardrails: tool allowlists, TTLs, budgets, kill switches",
    ],
  },
  {
    title: "ACCESSIBILITY",
    icon: Eye,
    summary: "A governed system is only real if humans can understand it, approve it, and intervene easily.",
    layers: [
      "Exec view: health, risk, coverage, escalations",
      "Builder view: skills, memory promotion, workflow design",
      "Operator view: tasks, approvals, evidence, exceptions",
      "Auditor view: lineage, provenance, policy checks, event logs",
    ],
  },
  {
    title: "INTEROPERABILITY",
    icon: Handshake,
    summary: "Domains should expose approved capabilities, not raw internals. Cross-domain traffic should be contract-based.",
    layers: [
      "Request contracts: ask another domain to do something",
      "Consult contracts: ask for opinion or validation",
      "Handoff contracts: transfer ownership or next step",
      "Outcome contracts: return evidence, result, confidence, policy basis",
    ],
  },
] as const;

const GOVERNANCE_ROLES = [
  {
    name: "Admin",
    responsibility: "Owns policy, domain setup, permissions, publishing, and emergency controls",
    icon: Shield,
  },
  {
    name: "Builder",
    responsibility: "Designs skills, workflows, memory promotion rules, and dashboards under policy",
    icon: Blocks,
  },
  {
    name: "User",
    responsibility: "Invokes approved capabilities, reviews outputs, and submits tasks",
    icon: Users,
  },
  {
    name: "Approver / Auditor",
    responsibility: "Reviews evidence, signs off on high-risk actions, and investigates history",
    icon: Scale,
  },
] as const;

const PERMISSION_OVERLAY = [
  "Read: what a layer can see",
  "Write: what memory or systems it can update",
  "Act: what external side effects it can trigger",
  "Delegate: what lower-level workers it can spawn",
  "Escalate: who it can hand work or approval to",
  "Interoperate: which adjacent domains it can talk to and under what contract",
];

const FINANCE_WALKTHROUGH = [
  {
    layer: "Domain",
    title: "Finance domain",
    detail: "Owns finance memory, tools, policy overlay, and approved skills. No single permanent 'Finance persona' is required.",
  },
  {
    layer: "Function",
    title: "R2R / P2P / O2C",
    detail: "Persistent capability clusters that hold reusable runbooks, KPIs, and action rights.",
  },
  {
    layer: "Workflow",
    title: "Bank reconciliation",
    detail: "Narrow workflow unit with known inputs, outputs, approval logic, and evidence requirements.",
  },
  {
    layer: "Runtime",
    title: "Recon worker for account X",
    detail: "Ephemeral worker receives a task contract, scoped credentials, and a bounded memory set; it produces outputs and logs, then dies.",
  },
] as const;

function LayerCard({ layer, index, total }: { layer: LayerCardData; index: number; total: number }) {
  const Icon = layer.icon;

  return (
    <div className="flex flex-col items-center gap-3">
      <Card className="w-full border-border/80 bg-background/80">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="mb-2 flex items-center gap-2">
                <Badge variant="outline">Layer {index + 1}</Badge>
                <span className="font-display text-[0.7rem] uppercase tracking-[0.16em] text-muted-foreground">
                  {layer.owner}
                </span>
              </div>
              <CardTitle className="text-base sm:text-lg">{layer.name}</CardTitle>
            </div>
            <Icon className="h-5 w-5 shrink-0 text-muted-foreground" />
          </div>
        </CardHeader>
        <CardContent className="grid gap-4 text-sm">
          <p className="text-muted-foreground">{layer.scope}</p>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <div className="mb-2 font-display text-[0.72rem] uppercase tracking-[0.14em] text-foreground/70">Persists here</div>
              <div className="flex flex-wrap gap-2">
                {layer.persists.map((item) => (
                  <Badge key={item} variant="secondary">{item}</Badge>
                ))}
              </div>
            </div>
            <div>
              <div className="mb-2 font-display text-[0.72rem] uppercase tracking-[0.14em] text-foreground/70">Examples</div>
              <div className="flex flex-wrap gap-2">
                {layer.examples.map((item) => (
                  <Badge key={item} variant="outline">{item}</Badge>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      {index < total - 1 && <ArrowDown className="h-5 w-5 text-muted-foreground/60" />}
    </div>
  );
}

export default function ArchitecturePage() {
  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="success">Draft architecture map</Badge>
            <Badge variant="outline">Org-persistent</Badge>
            <Badge variant="outline">Permission-governed</Badge>
            <Badge variant="outline">Visual dashboard seed</Badge>
          </div>
          <CardTitle className="mt-2 text-xl sm:text-2xl">Enterprise agent architecture map</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 text-sm sm:text-base">
          <p className="text-muted-foreground">
            This view turns the whiteboard idea into a more rigorous operating model: persistent identity lives at the
            <strong className="text-foreground"> enterprise, domain, and workstream </strong>
            layers, while execution happens through
            <strong className="text-foreground"> ephemeral runtime workers </strong>
            under external policy and permission controls.
          </p>
          <div className="grid gap-3 lg:grid-cols-3">
            <MetricCard icon={Layers3} title="Primary operating unit" value="Workstream" note="Departments own; workstreams run." />
            <MetricCard icon={KeyRound} title="Primary control unit" value="Permission domain" note="Policy lives outside the model." />
            <MetricCard icon={Network} title="Primary execution unit" value="Runtime worker" note="Least privilege, bounded TTL, full audit." />
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="map">
        {(active, setActive) => (
          <>
            <TabsList className="flex h-auto flex-wrap gap-1 border-b-0">
              {[
                ["map", "Architecture map"],
                ["controls", "Control panels"],
                ["governance", "Governance overlays"],
                ["walkthrough", "Finance walkthrough"],
              ].map(([value, label]) => (
                <TabsTrigger
                  key={value}
                  active={active === value}
                  value={value}
                  onClick={() => setActive(value)}
                  className="border border-border"
                >
                  {label}
                </TabsTrigger>
              ))}
            </TabsList>

            {active === "map" && (
              <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
                <div className="grid gap-2">
                  {ARCHITECTURE_LAYERS.map((layer, index) => (
                    <LayerCard key={layer.name} layer={layer} index={index} total={ARCHITECTURE_LAYERS.length} />
                  ))}
                </div>

                <div className="grid gap-4">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">How to read the map</CardTitle>
                    </CardHeader>
                    <CardContent className="grid gap-3 text-sm text-muted-foreground">
                      <p>Higher layers own context, policy, and organizational legitimacy.</p>
                      <p>Lower layers execute narrower work with tighter controls and stronger testability.</p>
                      <p>Runtime workers should be disposable; memory and identity should not depend on a single worker surviving.</p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle className="text-base">What should persist?</CardTitle>
                    </CardHeader>
                    <CardContent className="grid gap-2 text-sm">
                      {[
                        "Enterprise constitution and global policy",
                        "Domain knowledge, tools, and policy overlays",
                        "Workstream runbooks, skills, and operational memory",
                        "Audit logs, approvals, and outcome records",
                      ].map((item) => (
                        <div key={item} className="flex items-start gap-2">
                          <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                          <span>{item}</span>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                </div>
              </div>
            )}

            {active === "controls" && (
              <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
                {CONTROL_PANELS.map((panel) => {
                  const Icon = panel.icon;
                  return (
                    <Card key={panel.title}>
                      <CardHeader>
                        <div className="flex items-center gap-2">
                          <Icon className="h-5 w-5 text-muted-foreground" />
                          <CardTitle className="text-base">{panel.title}</CardTitle>
                        </div>
                      </CardHeader>
                      <CardContent className="grid gap-3 text-sm">
                        <p className="text-muted-foreground">{panel.summary}</p>
                        <div className="grid gap-2">
                          {panel.layers.map((item) => (
                            <div key={item} className="rounded-sm border border-border/70 p-3">
                              {item}
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}

            {active === "governance" && (
              <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Human governance roles</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-3">
                    {GOVERNANCE_ROLES.map((role) => {
                      const Icon = role.icon;
                      return (
                        <div key={role.name} className="flex gap-3 border border-border/70 p-3">
                          <Icon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                          <div>
                            <div className="font-medium">{role.name}</div>
                            <div className="text-sm text-muted-foreground">{role.responsibility}</div>
                          </div>
                        </div>
                      );
                    })}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Permission overlay applied to every layer</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-2 text-sm">
                    {PERMISSION_OVERLAY.map((item) => (
                      <div key={item} className="flex items-start gap-2 border border-border/70 p-3">
                        <Lock className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                        <span>{item}</span>
                      </div>
                    ))}
                  </CardContent>
                </Card>
              </div>
            )}

            {active === "walkthrough" && (
              <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Finance walkthrough</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-4">
                    {FINANCE_WALKTHROUGH.map((step, index) => (
                      <div key={step.title} className="grid gap-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge variant="outline">{step.layer}</Badge>
                          <span className="font-medium">{step.title}</span>
                        </div>
                        <p className="text-sm text-muted-foreground">{step.detail}</p>
                        {index < FINANCE_WALKTHROUGH.length - 1 && (
                          <div className="flex justify-center">
                            <ArrowDown className="h-4 w-4 text-muted-foreground/60" />
                          </div>
                        )}
                      </div>
                    ))}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">Design heuristics</CardTitle>
                  </CardHeader>
                  <CardContent className="grid gap-3 text-sm text-muted-foreground">
                    <Heuristic text="Do not create a permanent named bot for every person or workflow." />
                    <Heuristic text="Keep the persistent layer thin: org, domain, function, workstream, policy." />
                    <Heuristic text="Keep the execution layer thick: many temporary workers, each tightly scoped." />
                    <Heuristic text="Let permissions decide what a worker can do — not just its label." />
                    <Heuristic text="Cross-domain communication should happen through typed requests, consults, handoffs, and outcome records." />
                  </CardContent>
                </Card>
              </div>
            )}
          </>
        )}
      </Tabs>
    </div>
  );
}

function MetricCard({
  icon: Icon,
  title,
  value,
  note,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  value: string;
  note: string;
}) {
  return (
    <div className="border border-border/80 p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-display text-[0.72rem] uppercase tracking-[0.14em] text-muted-foreground">{title}</span>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="font-display text-lg text-foreground">{value}</div>
      <div className="mt-1 text-sm text-muted-foreground">{note}</div>
    </div>
  );
}

function Heuristic({ text }: { text: string }) {
  return (
    <div className="flex items-start gap-2 border border-border/70 p-3">
      <Briefcase className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
      <span>{text}</span>
    </div>
  );
}
