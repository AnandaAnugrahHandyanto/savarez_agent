import { useCallback, useEffect, useRef, useState } from "react";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Toast } from "@/components/Toast";
import { JobCard, STAGE_LABELS } from "./JobCard";
import { JobDetailModal } from "./JobDetailModal";
import { api } from "@/lib/api";
import type { Job, PipelineStage } from "@/lib/api";
import { cn } from "@/lib/utils";

const VISIBLE_STAGES: PipelineStage[] = [
  "interested",
  "applied",
  "interviewing",
  "waiting_response",
  "offer",
  "rejected",
  "closed",
];

const STAGE_HEADER_COLOR: Record<PipelineStage, string> = {
  interested: "border-blue-500/40 text-blue-400",
  applied: "border-indigo-500/40 text-indigo-400",
  interviewing: "border-orange-500/40 text-orange-400",
  waiting_response: "border-yellow-500/40 text-yellow-400",
  offer: "border-green-500/40 text-green-400",
  rejected: "border-red-500/40 text-red-400",
  closed: "border-gray-500/40 text-gray-400",
};

const STAGE_DROP_BG: Record<PipelineStage, string> = {
  interested: "bg-blue-500/5",
  applied: "bg-indigo-500/5",
  interviewing: "bg-orange-500/5",
  waiting_response: "bg-yellow-500/5",
  offer: "bg-green-500/5",
  rejected: "bg-red-500/5",
  closed: "bg-gray-500/5",
};

export function PipelineView() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [dragJobId, setDragJobId] = useState<number | null>(null);
  const [dropTarget, setDropTarget] = useState<PipelineStage | null>(null);
  const { toast, showToast } = useToastState();

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.getJobs({ status: "in_pipeline", limit: 200 });
      setJobs(res.jobs);
    } catch {
      showToast("Failed to load pipeline", "error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchJobs(); }, [fetchJobs]);

  const jobsByStage = useCallback((stage: PipelineStage): Job[] => {
    return jobs.filter((j) => j.current_stage === stage);
  }, [jobs]);

  const handleDragStart = useCallback((e: React.DragEvent, job: Job) => {
    setDragJobId(job.id);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(job.id));
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent, stage: PipelineStage) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDropTarget(stage);
  }, []);

  const handleDragLeave = useCallback(() => {
    setDropTarget(null);
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent, targetStage: PipelineStage) => {
    e.preventDefault();
    setDropTarget(null);
    const jobId = dragJobId;
    setDragJobId(null);
    if (!jobId) return;

    const job = jobs.find((j) => j.id === jobId);
    if (!job || job.current_stage === targetStage) return;

    // Optimistic update
    setJobs((prev) =>
      prev.map((j) =>
        j.id === jobId
          ? { ...j, current_stage: targetStage, current_stage_date: new Date().toISOString().slice(0, 10) }
          : j,
      ),
    );

    try {
      await api.moveJobToStage(jobId, targetStage);
      showToast(`Moved to ${STAGE_LABELS[targetStage]}`, "success");
    } catch {
      // Revert on failure
      setJobs((prev) =>
        prev.map((j) =>
          j.id === jobId ? { ...j, current_stage: job.current_stage } : j,
        ),
      );
      showToast("Failed to move job", "error");
    }
  }, [dragJobId, jobs]);

  const handleJobUpdated = useCallback((updated: Job) => {
    setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
    setSelectedJob(updated);
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="w-5 h-5" />
      </div>
    );
  }

  const totalInPipeline = jobs.length;

  return (
    <div className="flex flex-col h-full">
      {totalInPipeline === 0 ? (
        <div className="flex flex-col items-center justify-center flex-1 text-muted-foreground text-sm py-16">
          <p>No jobs in the pipeline yet.</p>
          <p className="text-xs mt-1 text-muted-foreground/60">
            Use the Triage tab to add jobs using the + button.
          </p>
        </div>
      ) : (
        <div className="flex-1 overflow-x-auto overflow-y-hidden">
          <div className="flex gap-3 h-full px-4 py-3 min-w-max">
            {VISIBLE_STAGES.map((stage) => {
              const stageJobs = jobsByStage(stage);
              const isDropTarget = dropTarget === stage;

              return (
                <div
                  key={stage}
                  className="flex flex-col w-64 shrink-0"
                  onDragOver={(e) => handleDragOver(e, stage)}
                  onDragLeave={handleDragLeave}
                  onDrop={(e) => handleDrop(e, stage)}
                >
                  {/* Column header */}
                  <div
                    className={cn(
                      "flex items-center justify-between px-3 py-2 border-b-2 mb-2 text-xs font-bold uppercase tracking-wider",
                      STAGE_HEADER_COLOR[stage],
                    )}
                  >
                    <span>{STAGE_LABELS[stage]}</span>
                    <span className="opacity-60">{stageJobs.length}</span>
                  </div>

                  {/* Drop zone */}
                  <div
                    className={cn(
                      "flex-1 overflow-y-auto space-y-2 rounded transition-colors min-h-16",
                      isDropTarget && STAGE_DROP_BG[stage],
                      isDropTarget && "ring-1 ring-inset ring-ring/30",
                    )}
                  >
                    {stageJobs.length === 0 && (
                      <div className="flex items-center justify-center h-12 text-xs text-muted-foreground/40 border border-dashed border-border rounded">
                        drop here
                      </div>
                    )}
                    {stageJobs.map((job) => (
                      <JobCard
                        key={job.id}
                        job={job}
                        showStage={false}
                        draggable
                        onDragStart={(e) => handleDragStart(e, job)}
                        onClick={() => setSelectedJob(job)}
                        className={dragJobId === job.id ? "opacity-50" : ""}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <JobDetailModal
        job={selectedJob}
        onClose={() => setSelectedJob(null)}
        onJobUpdated={handleJobUpdated}
      />

      <Toast toast={toast} />
    </div>
  );
}

function useToastState() {
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const showToast = useCallback((message: string, type: "success" | "error") => {
    setToast({ message, type });
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setToast(null), 3000);
  }, []);
  return { toast, showToast };
}
