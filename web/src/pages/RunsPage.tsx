import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import type { RunEntry, RunsSummaryResponse } from "@/lib/api";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Stats } from "@nous-research/ui/ui/components/stats";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { usePageHeader } from "@/contexts/usePageHeader";
import { useI18n } from "@/i18n";
import { isoTimeAgo } from "@/lib/utils";

const LIMIT = 50;
const CLASSIFICATIONS = ["ok", "timeout", "process_error", "permission_error", "auth_error", "rate_limited"];

function classificationTone(value?: string | null): "success" | "warning" | "secondary" | "destructive" {
  if (value === "ok") return "success";
  if (value === "timeout" || value === "rate_limited") return "warning";
  if (value?.includes("error")) return "destructive";
  return "secondary";
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "-";
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 2 : 1)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function startedLabel(value?: string | null): string {
  if (!value) return "-";
  return isoTimeAgo(value);
}

export default function RunsPage() {
  const { t } = useI18n();
  const { setTitle } = usePageHeader();
  const [project, setProject] = useState("staam");
  const [classification, setClassification] = useState("");
  const [runs, setRuns] = useState<RunEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<RunsSummaryResponse | null>(null);
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const selectedProject = project.trim() || "staam";
      const [runsResp, summaryResp] = await Promise.all([
        api.getRuns({
          project: selectedProject,
          classification: classification || undefined,
          limit: LIMIT,
          offset,
        }),
        api.getRunsSummary(selectedProject),
      ]);
      setRuns(runsResp.runs);
      setTotal(runsResp.total);
      setSummary(summaryResp);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [classification, offset, project]);

  useEffect(() => {
    setTitle(t.runs.title);
    return () => setTitle(null);
  }, [setTitle, t.runs.title]);

  useEffect(() => {
    load();
  }, [load]);

  const counts = summary?.classification_counts ?? {};
  const totalPages = Math.max(1, Math.ceil(total / LIMIT));
  const page = Math.floor(offset / LIMIT) + 1;
  const expandedRun = useMemo(
    () => runs.find((run) => run.run_id === expandedRunId) ?? null,
    [expandedRunId, runs],
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <input
            className="h-8 w-40 border border-border bg-background px-2 text-xs"
            aria-label={t.runs.project}
            value={project}
            onChange={(event) => {
              setProject(event.target.value);
              setOffset(0);
            }}
          />
          <select
            className="h-8 border border-border bg-background px-2 text-xs"
            aria-label={t.runs.classification}
            value={classification}
            onChange={(event) => {
              setClassification(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">{t.runs.allClassifications}</option>
            {CLASSIFICATIONS.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
        <Button
          size="sm"
          outlined
          onClick={load}
          disabled={loading}
          prefix={loading ? <Spinner /> : <RefreshCw className="h-4 w-4" />}
        >
          {t.common.refresh}
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

      <Card>
        <CardContent className="py-4">
          <Stats
            items={[
              { label: t.runs.totalRuns, value: String(summary?.total ?? 0) },
              { label: t.runs.ok, value: String(counts.ok ?? 0) },
              { label: t.runs.timeout, value: String(counts.timeout ?? 0) },
              { label: t.runs.processError, value: String(counts.process_error ?? 0) },
              { label: t.runs.avgDuration, value: formatDuration(summary?.avg_duration_seconds) },
            ]}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-base">{t.runs.title}</CardTitle>
            <div className="text-xs text-muted-foreground">
              {total} {t.common.match} · {t.common.page} {page} {t.common.of} {totalPages}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading && runs.length === 0 ? (
            <div className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
              <Spinner /> {t.common.loading}
            </div>
          ) : runs.length === 0 ? (
            <div className="py-10 text-center text-sm text-muted-foreground">
              {t.runs.noRuns}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1000px] text-left text-sm">
                <thead className="border-b border-border text-xs text-muted-foreground">
                  <tr>
                    <th className="w-8 py-2 pr-2 font-medium" />
                    <th className="py-2 pr-4 font-medium">{t.runs.runId}</th>
                    <th className="py-2 pr-4 font-medium">{t.runs.taskId}</th>
                    <th className="py-2 pr-4 font-medium">{t.runs.agent}</th>
                    <th className="py-2 pr-4 font-medium">{t.runs.classification}</th>
                    <th className="py-2 pr-4 font-medium">{t.runs.runType}</th>
                    <th className="py-2 pr-4 font-medium">{t.runs.startedAt}</th>
                    <th className="py-2 pr-4 font-medium">{t.runs.duration}</th>
                    <th className="py-2 font-medium">{t.runs.exitCode}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {runs.map((run, idx) => {
                    const rowId = run.run_id || `${run.task_id || "run"}-${idx}`;
                    const expanded = expandedRunId === rowId;
                    return (
                      <tr key={rowId} className="align-top">
                        <td className="py-2 pr-2">
                          <button
                            type="button"
                            className="text-muted-foreground hover:text-foreground"
                            onClick={() => setExpandedRunId(expanded ? null : rowId)}
                            aria-label={expanded ? t.common.collapse : t.common.expand}
                          >
                            {expanded ? (
                              <ChevronUp className="h-4 w-4" />
                            ) : (
                              <ChevronDown className="h-4 w-4" />
                            )}
                          </button>
                        </td>
                        <td className="py-2 pr-4 font-mono text-xs">
                          <div className="max-w-[15rem] truncate">{run.run_id || "-"}</div>
                        </td>
                        <td className="py-2 pr-4 font-mono text-xs">
                          <div className="max-w-[13rem] truncate">{run.task_id || "-"}</div>
                        </td>
                        <td className="py-2 pr-4 text-xs">{run.agent_id || "-"}</td>
                        <td className="py-2 pr-4">
                          <Badge tone={classificationTone(run.classification)}>
                            {run.classification || "unknown"}
                          </Badge>
                        </td>
                        <td className="py-2 pr-4 text-xs text-muted-foreground">
                          {run.run_type || "-"}
                        </td>
                        <td className="py-2 pr-4 text-xs text-muted-foreground">
                          {startedLabel(run.started_at)}
                        </td>
                        <td className="py-2 pr-4 text-xs">
                          {formatDuration(run.duration_seconds)}
                        </td>
                        <td className="py-2 text-xs text-muted-foreground">
                          {run.exit_code ?? "-"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              {expandedRun ? (
                <div className="border-t border-border bg-muted/20 px-4 py-3">
                  <div className="space-y-3 text-xs">
                    {expandedRun.command ? (
                      <div>
                        <div className="mb-1 font-medium text-muted-foreground">{t.runs.command}</div>
                        <pre className="max-h-32 overflow-auto border border-border bg-background p-2 font-mono text-[11px] whitespace-pre-wrap">
                          {expandedRun.command}
                        </pre>
                      </div>
                    ) : null}
                    {expandedRun.stdout_tail ? (
                      <div>
                        <div className="mb-1 font-medium text-muted-foreground">{t.runs.stdoutTail}</div>
                        <pre className="max-h-48 overflow-auto border border-border bg-background p-2 font-mono text-[11px] whitespace-pre-wrap">
                          {expandedRun.stdout_tail}
                        </pre>
                      </div>
                    ) : null}
                    {expandedRun.stderr_tail ? (
                      <div>
                        <div className="mb-1 font-medium text-muted-foreground">{t.runs.stderrTail}</div>
                        <pre className="max-h-48 overflow-auto border border-border bg-background p-2 font-mono text-[11px] whitespace-pre-wrap text-destructive">
                          {expandedRun.stderr_tail}
                        </pre>
                      </div>
                    ) : null}
                  </div>
                </div>
              ) : null}
            </div>
          )}

          {total > LIMIT ? (
            <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
              <Button
                size="sm"
                outlined
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - LIMIT))}
              >
                {t.common.collapse}
              </Button>
              <span className="text-xs text-muted-foreground">
                {offset + 1}-{Math.min(offset + LIMIT, total)} {t.common.of} {total}
              </span>
              <Button
                size="sm"
                outlined
                disabled={offset + LIMIT >= total}
                onClick={() => setOffset(offset + LIMIT)}
              >
                {t.common.expand}
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
