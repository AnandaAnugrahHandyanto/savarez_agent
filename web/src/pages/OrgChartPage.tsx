import { LayoutTemplate } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  INVOKE_MATRIX,
  LEAD_ROLE,
  ORG_SECTIONS,
  VERIFICATION_LEVELS,
  WORKFLOW_STEPS,
  type InvokeRow,
  type OrgRole,
  type OrgSection,
  type RuntimePolicy,
} from "@/data/hermesOrgChart.generated";
import { cn } from "@/lib/utils";

function humanizeToken(value: string): string {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function roleToneClass(role: OrgRole): string {
  if (role.tone === "success") {
    return "border-emerald-500/30 bg-emerald-950/10";
  }
  if (role.tone === "warning") {
    return "border-amber-500/30 bg-amber-950/10";
  }
  return "";
}

function PolicyFlag({ label, value }: { label: string; value: boolean }) {
  return (
    <Badge variant={value ? "success" : "outline"} className="text-[0.62rem]">
      {label}: {value ? "Yes" : "No"}
    </Badge>
  );
}

function ModeBadges({ modes }: { modes: RuntimePolicy["allowed_execution_modes"] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {modes.map((mode) => (
        <Badge key={mode} variant="outline" className="text-[0.62rem]">
          {humanizeToken(mode)}
        </Badge>
      ))}
    </div>
  );
}

function TagList({ items }: { items: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <Badge key={item} variant="outline" className="text-[0.62rem]">
          {item}
        </Badge>
      ))}
    </div>
  );
}

function RoleCard({ role }: { role: OrgRole }) {
  const Icon = role.icon;

  return (
    <Card className={cn("h-full", roleToneClass(role))}>
      <CardHeader className="gap-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Icon className="h-4 w-4 shrink-0 text-midground/80" />
              <CardTitle className="text-sm">{role.title}</CardTitle>
            </div>
            <CardDescription className="mt-1">{role.position}</CardDescription>
          </div>
          <Badge
            variant={role.tone === "success" ? "success" : role.tone === "warning" ? "warning" : "outline"}
            className="shrink-0 text-[0.62rem]"
          >
            {role.tone ? humanizeToken(role.tone) : "Role"}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <p className="text-sm leading-relaxed text-foreground/90">{role.mission}</p>

        <div className="space-y-2">
          <p className="text-[0.64rem] uppercase tracking-[0.14em] text-muted-foreground">
            Responsibilities
          </p>
          <ul className="space-y-1 text-sm text-foreground/90">
            {role.responsibilities.map((item) => (
              <li key={item} className="flex gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-current/60 shrink-0" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-2">
          <p className="text-[0.64rem] uppercase tracking-[0.14em] text-muted-foreground">
            Activation
          </p>
          <p className="text-sm text-foreground/90">{role.activation}</p>
        </div>

        <div className="grid gap-3 text-sm lg:grid-cols-2">
          <div className="space-y-1 rounded border border-border/60 bg-background/30 p-3">
            <p className="text-[0.64rem] uppercase tracking-[0.14em] text-muted-foreground">
              Reports to
            </p>
            <p className="text-foreground/90">{role.reportsTo}</p>
          </div>
          <div className="space-y-1 rounded border border-border/60 bg-background/30 p-3">
            <p className="text-[0.64rem] uppercase tracking-[0.14em] text-muted-foreground">
              Model
            </p>
            <p className="text-foreground/90">{role.model}</p>
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-[0.64rem] uppercase tracking-[0.14em] text-muted-foreground">
            Tool focus
          </p>
          <TagList items={role.toolFocus} />
        </div>

        <div className="space-y-2">
          <p className="text-[0.64rem] uppercase tracking-[0.14em] text-muted-foreground">
            Invoke for
          </p>
          <TagList items={role.invokeFor} />
        </div>

        <div className="space-y-2 rounded border border-border/60 bg-background/30 p-3">
          <p className="text-[0.64rem] uppercase tracking-[0.14em] text-muted-foreground">
            Runtime policy
          </p>
          <div className="flex flex-wrap gap-1.5">
            <Badge variant="success" className="text-[0.62rem]">
              Default: {humanizeToken(role.runtimePolicy.default_execution_mode)}
            </Badge>
            <Badge variant="outline" className="text-[0.62rem]">
              Worktree: {humanizeToken(role.runtimePolicy.worktree_strategy)}
            </Badge>
          </div>
          <div className="flex flex-wrap gap-1.5 pt-1">
            <PolicyFlag
              label="Independent session"
              value={role.runtimePolicy.requires_independent_session}
            />
            <PolicyFlag
              label="Artifact handoff"
              value={role.runtimePolicy.requires_artifact_handoff}
            />
            <PolicyFlag
              label="Lead coordinates"
              value={role.runtimePolicy.lead_coordinates_feedback}
            />
            <PolicyFlag
              label="Lead review"
              value={role.runtimePolicy.lead_review_required_before_next_handoff}
            />
            <PolicyFlag
              label="Revalidate after fix"
              value={role.runtimePolicy.requires_revalidation_after_fix}
            />
          </div>
          <div className="pt-1">
            <ModeBadges modes={role.runtimePolicy.allowed_execution_modes} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function SectionCard({ section }: { section: OrgSection }) {
  return (
    <Card id={section.id}>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>{section.title}</CardTitle>
            <CardDescription className="mt-1">{section.description}</CardDescription>
          </div>
          <Badge variant="outline" className="text-[0.62rem]">
            {section.lane}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
          {section.roles.map((role) => (
            <RoleCard key={role.title} role={role} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function WorkflowStepList() {
  return (
    <ol className="space-y-2">
      {WORKFLOW_STEPS.map((step, index) => (
        <li
          key={step}
          className="flex items-start gap-3 rounded border border-border/60 bg-background/30 px-3 py-2"
        >
          <Badge variant="outline" className="mt-0.5 shrink-0 text-[0.62rem]">
            {index + 1}
          </Badge>
          <span className="text-sm text-foreground/90">{step}</span>
        </li>
      ))}
    </ol>
  );
}

function VerificationLevelList() {
  return (
    <div className="space-y-2">
      {VERIFICATION_LEVELS.map((level) => (
        <div
          key={level.id}
          className="rounded border border-border/60 bg-background/30 px-3 py-2"
        >
          <div className="flex items-center gap-2">
            <Badge variant="success" className="text-[0.62rem]">
              {level.id}
            </Badge>
            <p className="text-sm font-medium text-foreground/90">{level.label}</p>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{level.detail}</p>
        </div>
      ))}
    </div>
  );
}

function InvocationMatrixList() {
  return (
    <div className="space-y-2">
      {INVOKE_MATRIX.map((row: InvokeRow) => (
        <div
          key={row.trigger}
          className="rounded border border-border/60 bg-background/30 px-3 py-2"
        >
          <p className="text-sm font-medium text-foreground/90">{row.trigger}</p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <Badge variant="outline" className="text-[0.62rem]">
              Primary: {row.primary}
            </Badge>
            <Badge variant="outline" className="text-[0.62rem]">
              Verify: {row.verification}
            </Badge>
          </div>
          <div className="mt-2">
            <TagList items={row.supporting} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function OrgChartPage() {
  const totalRoles = ORG_SECTIONS.reduce((sum, section) => sum + section.roles.length, 0);

  return (
    <div className="space-y-6 pb-6">
      <section className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <LayoutTemplate className="h-5 w-5 text-midground/80" />
                  <CardTitle className="text-lg sm:text-xl">Org Chart</CardTitle>
                </div>
                <CardDescription className="max-w-2xl text-sm sm:text-base">
                  Canonical role definitions, runtime policy defaults, and the workflow spine
                  that drives role-team execution.
                </CardDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline" className="text-[0.62rem]">
                  {ORG_SECTIONS.length} sections
                </Badge>
                <Badge variant="outline" className="text-[0.62rem]">
                  {totalRoles} roles
                </Badge>
                <Badge variant="outline" className="text-[0.62rem]">
                  {VERIFICATION_LEVELS.length} verification levels
                </Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="rounded border border-emerald-500/20 bg-emerald-950/10 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[0.64rem] uppercase tracking-[0.14em] text-muted-foreground">
                    Policy anchor
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <LEAD_ROLE.icon className="h-5 w-5 shrink-0 text-midground/80" />
                    <div>
                      <p className="text-base font-semibold text-foreground/90">
                        {LEAD_ROLE.title}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {LEAD_ROLE.position} · reports to {LEAD_ROLE.reportsTo}
                      </p>
                    </div>
                  </div>
                </div>
                <Badge variant="success" className="text-[0.62rem]">
                  Always active
                </Badge>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-foreground/90">
                {LEAD_ROLE.mission}
              </p>
              <ul className="mt-3 space-y-1 text-sm text-foreground/90">
                {LEAD_ROLE.responsibilities.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-current/60 shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="space-y-2 rounded border border-border/60 bg-background/30 p-4">
              <p className="text-[0.64rem] uppercase tracking-[0.14em] text-muted-foreground">
                Lead runtime policy
              </p>
              <div className="flex flex-wrap gap-1.5">
                <Badge variant="success" className="text-[0.62rem]">
                  Default: {humanizeToken(LEAD_ROLE.runtimePolicy.default_execution_mode)}
                </Badge>
                <Badge variant="outline" className="text-[0.62rem]">
                  Worktree: {humanizeToken(LEAD_ROLE.runtimePolicy.worktree_strategy)}
                </Badge>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                <PolicyFlag
                  label="Independent session"
                  value={LEAD_ROLE.runtimePolicy.requires_independent_session}
                />
                <PolicyFlag
                  label="Artifact handoff"
                  value={LEAD_ROLE.runtimePolicy.requires_artifact_handoff}
                />
                <PolicyFlag
                  label="Lead coordinates"
                  value={LEAD_ROLE.runtimePolicy.lead_coordinates_feedback}
                />
                <PolicyFlag
                  label="Lead review"
                  value={LEAD_ROLE.runtimePolicy.lead_review_required_before_next_handoff}
                />
                <PolicyFlag
                  label="Revalidate after fix"
                  value={LEAD_ROLE.runtimePolicy.requires_revalidation_after_fix}
                />
              </div>
              <div className="pt-1">
                <ModeBadges modes={LEAD_ROLE.runtimePolicy.allowed_execution_modes} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg sm:text-xl">Workflow spine</CardTitle>
            <CardDescription className="text-sm sm:text-base">
              The canonical sequence for non-trivial role-team work.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <WorkflowStepList />
            <div className="space-y-2">
              <p className="text-[0.64rem] uppercase tracking-[0.14em] text-muted-foreground">
                Verification levels
              </p>
              <div className="rounded border border-border/60 bg-background/30 p-3">
                <p className="text-sm text-foreground/90">
                  V1 starts with reasoning checks, V2 proves the workflow, V3 covers the
                  runtime environment, and V4 requires the actual target device.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-4">
        {ORG_SECTIONS.map((section) => (
          <SectionCard key={section.id} section={section} />
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg sm:text-xl">Verification levels</CardTitle>
            <CardDescription className="text-sm sm:text-base">
              Evidence depth increases as the surface gets more physical or user-facing.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <VerificationLevelList />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg sm:text-xl">Invocation matrix</CardTitle>
            <CardDescription className="text-sm sm:text-base">
              Common triggers and the primary roles that should take ownership.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <InvocationMatrixList />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
