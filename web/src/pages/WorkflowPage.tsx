import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Circle, PauseCircle, Play, RefreshCw, XCircle } from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Typography } from "@/components/NouiTypography";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectOption } from "@nous-research/ui/ui/components/select";
import { api, type WorkflowGate, type WorkflowPayload } from "@/lib/api";

const STATUS_ICON = {
  blocked: XCircle,
  done: CheckCircle2,
  pending: Circle,
  ready: Play,
  skipped: PauseCircle,
} satisfies Record<WorkflowGate["status"], typeof Circle>;

const STATUS_CLASS = {
  blocked: "text-destructive",
  done: "text-emerald-400",
  pending: "text-muted-foreground",
  ready: "text-primary",
  skipped: "text-muted-foreground",
} satisfies Record<WorkflowGate["status"], string>;

export default function WorkflowPage() {
  const [repo, setRepo] = useState("");
  const [payload, setPayload] = useState<WorkflowPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [initName, setInitName] = useState("");
  const [initLinearIssue, setInitLinearIssue] = useState("");
  const [initLinearProject, setInitLinearProject] = useState("");
  const [initNote, setInitNote] = useState("");
  const [initForce, setInitForce] = useState(false);
  const [advanceGate, setAdvanceGate] = useState("codex_plan");
  const [advanceStatus, setAdvanceStatus] = useState<WorkflowGate["status"]>("done");
  const [advanceEvidence, setAdvanceEvidence] = useState("");
  const [advanceNote, setAdvanceNote] = useState("");
  const [verifyCommand, setVerifyCommand] = useState("");
  const [verifyResult, setVerifyResult] = useState<"passed" | "failed" | "blocked">("passed");
  const [verifyNote, setVerifyNote] = useState("");

  const gates = useMemo(() => payload?.state?.gates ?? [], [payload?.state?.gates]);
  const blockedCount = useMemo(
    () => gates.filter((gate) => gate.status === "blocked").length,
    [gates],
  );
  const doneCount = useMemo(
    () => gates.filter((gate) => gate.status === "done").length,
    [gates],
  );
  const selectedAdvanceGate = useMemo(
    () =>
      gates.some((gate) => gate.key === advanceGate)
        ? advanceGate
        : gates[0]?.key ?? advanceGate,
    [advanceGate, gates],
  );

  const load = useCallback(async (nextRepo: string) => {
    setLoading(true);
    setError(null);
    try {
      setPayload(await api.getWorkflowStatus(nextRepo || undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  async function init() {
    setLoading(true);
    setError(null);
    try {
      setPayload(
        await api.initWorkflow({
          repo: repo || undefined,
          name: initName || undefined,
          linear_issue: initLinearIssue || undefined,
          linear_project: initLinearProject || undefined,
          claude_gate_note: initNote || undefined,
          force: initForce,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function advance() {
    setLoading(true);
    setError(null);
    try {
      setPayload(
        await api.advanceWorkflow({
          repo: repo || undefined,
          gate: selectedAdvanceGate,
          status: advanceStatus,
          evidence: advanceEvidence || undefined,
          note: advanceNote,
        }),
      );
      setAdvanceEvidence("");
      setAdvanceNote("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function verify() {
    setLoading(true);
    setError(null);
    try {
      setPayload(
        await api.verifyWorkflow({
          repo: repo || undefined,
          command: verifyCommand,
          result: verifyResult,
          note: verifyNote,
        }),
      );
      setVerifyCommand("");
      setVerifyNote("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load("");
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 sm:p-6">
      <section className="flex flex-col gap-4 border-b border-border pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <Typography expanded className="text-3xl font-bold">
            Workflow Launcher
          </Typography>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            {payload?.state
              ? payload.state.workflow_name
              : "No workflow state loaded."}
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <div className="min-w-0 sm:w-[28rem]">
            <Label className="text-xs text-muted-foreground" htmlFor="workflow-repo">
              Repository
            </Label>
            <Input
              id="workflow-repo"
              placeholder={payload?.repo ?? "Default artifact repository"}
              value={repo}
              onChange={(event) => setRepo(event.target.value)}
            />
          </div>
          <Button onClick={() => void load(repo)} disabled={loading}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Button onClick={init} disabled={loading}>
            <Play className="mr-2 h-4 w-4" />
            Init
          </Button>
        </div>
      </section>

      {error ? (
        <div className="border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          <AlertTriangle className="mr-2 inline h-4 w-4" />
          {error}
        </div>
      ) : null}

      <section className="grid gap-4 md:grid-cols-3">
        <Stat label="Gates Done" value={String(doneCount)} />
        <Stat label="Blocked" value={String(blockedCount)} />
        <Stat label="Artifacts" value={String(payload?.inventory.total ?? 0)} />
      </section>

      <section className="grid gap-3 border border-border bg-muted/20 p-4 text-sm md:grid-cols-2">
        <Detail label="Repo" value={payload?.repo ?? "Pending"} />
        <Detail label="State Path" value={payload?.state_path ?? "Pending"} />
        <Detail label="Linear Issue" value={payload?.state?.linear_issue ?? "Pending"} />
        <Detail label="Linear Project" value={payload?.state?.linear_project ?? "Pending"} />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Initialize</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="workflow-init-name">Workflow Name</Label>
                <Input
                  id="workflow-init-name"
                  placeholder={payload?.state?.workflow_name ?? "Repo name"}
                  value={initName}
                  onChange={(event) => setInitName(event.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="workflow-init-linear-issue">Linear Issue</Label>
                <Input
                  id="workflow-init-linear-issue"
                  placeholder="ASO-123"
                  value={initLinearIssue}
                  onChange={(event) => setInitLinearIssue(event.target.value)}
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="workflow-init-linear-project">Linear Project</Label>
              <Input
                id="workflow-init-linear-project"
                placeholder="Optional project name"
                value={initLinearProject}
                onChange={(event) => setInitLinearProject(event.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="workflow-init-note">Claude Gate Note</Label>
              <Input
                id="workflow-init-note"
                placeholder="Optional note"
                value={initNote}
                onChange={(event) => setInitNote(event.target.value)}
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <Checkbox
                checked={initForce}
                onCheckedChange={(checked) => setInitForce(checked === true)}
              />
              Overwrite existing workflow files
            </label>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Advance Gate</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="workflow-advance-gate">Gate</Label>
                <Select
                  id="workflow-advance-gate"
                  value={selectedAdvanceGate}
                  onValueChange={setAdvanceGate}
                >
                  {gates.map((gate) => (
                    <SelectOption key={gate.key} value={gate.key}>
                      {gate.title}
                    </SelectOption>
                  ))}
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="workflow-advance-status">Status</Label>
                <Select
                  id="workflow-advance-status"
                  value={advanceStatus}
                  onValueChange={(value) => setAdvanceStatus(value as WorkflowGate["status"])}
                >
                  {(["pending", "ready", "blocked", "done", "skipped"] as const).map((status) => (
                    <SelectOption key={status} value={status}>
                      {status}
                    </SelectOption>
                  ))}
                </Select>
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="workflow-advance-evidence">Evidence</Label>
              <Input
                id="workflow-advance-evidence"
                placeholder="Optional path or reference"
                value={advanceEvidence}
                onChange={(event) => setAdvanceEvidence(event.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="workflow-advance-note">Note</Label>
              <Input
                id="workflow-advance-note"
                placeholder="Optional note"
                value={advanceNote}
                onChange={(event) => setAdvanceNote(event.target.value)}
              />
            </div>
            <div className="flex justify-end">
              <Button onClick={advance} disabled={loading || gates.length === 0}>
                <CheckCircle2 className="mr-2 h-4 w-4" />
                Save Gate
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>Gate Status</CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase text-muted-foreground">
                <th className="py-2 pr-4">Gate</th>
                <th className="py-2 pr-4">Owner</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Evidence</th>
                <th className="py-2">Note</th>
              </tr>
            </thead>
            <tbody>
              {gates.map((gate) => {
                const Icon = STATUS_ICON[gate.status] ?? Circle;
                return (
                  <tr className="border-b border-border/60" key={gate.key}>
                    <td className="py-3 pr-4 font-medium">{gate.title}</td>
                    <td className="py-3 pr-4 text-muted-foreground">{gate.owner}</td>
                    <td className="py-3 pr-4">
                      <span className={`inline-flex items-center gap-2 ${STATUS_CLASS[gate.status]}`}>
                        <Icon className="h-4 w-4" />
                        {gate.status}
                      </span>
                    </td>
                    <td className="py-3 pr-4 font-mono text-xs text-muted-foreground">
                      {gate.evidence}
                    </td>
                    <td className="py-3 text-muted-foreground">{gate.note}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Verification</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3">
          <div className="grid gap-3 lg:grid-cols-[1fr_12rem]">
            <div className="grid gap-2">
              <Label htmlFor="workflow-verify-command">Command</Label>
              <Input
                id="workflow-verify-command"
                placeholder="pytest tests/hermes_cli/test_workflow_launcher.py"
                value={verifyCommand}
                onChange={(event) => setVerifyCommand(event.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="workflow-verify-result">Result</Label>
              <Select
                id="workflow-verify-result"
                value={verifyResult}
                onValueChange={(value) => setVerifyResult(value as "passed" | "failed" | "blocked")}
              >
                {(["passed", "failed", "blocked"] as const).map((result) => (
                  <SelectOption key={result} value={result}>
                    {result}
                  </SelectOption>
                ))}
              </Select>
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="workflow-verify-note">Note</Label>
            <Input
              id="workflow-verify-note"
              placeholder="Optional note"
              value={verifyNote}
              onChange={(event) => setVerifyNote(event.target.value)}
            />
          </div>
          <div className="flex justify-end">
            <Button onClick={verify} disabled={loading || !verifyCommand.trim() || !payload?.state}>
              <CheckCircle2 className="mr-2 h-4 w-4" />
              Record
            </Button>
          </div>
          {(payload?.state?.verifications ?? []).slice(-5).map((record) => (
            <div className="border border-border bg-muted/20 p-3" key={`${record.ran_at}-${record.command}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs">{record.command}</span>
                <span className="text-xs uppercase text-muted-foreground">{record.result}</span>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">{record.note || record.ran_at}</p>
            </div>
          ))}
          {!payload?.state?.verifications.length ? (
            <p className="text-sm text-muted-foreground">No verification records.</p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 truncate font-mono text-xs">{value}</div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border border-border bg-muted/20 p-4">
      <div className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </div>
      <Typography expanded className="mt-3 text-3xl font-bold leading-none">
        {value}
      </Typography>
    </div>
  );
}
