import { useCallback, useEffect, useRef, useState } from "react";
import {
  X,
  ExternalLink,
  ChevronRight,
  Star,
  Trash2,
  ArrowLeftCircle,
} from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { useModalBehavior } from "@/hooks/useModalBehavior";
import { api } from "@/lib/api";
import type { Job, JobPipelineEvent, PipelineStage } from "@/lib/api";
import { STAGE_LABELS } from "./JobCard";
import { cn } from "@/lib/utils";

const PIPELINE_STAGES: PipelineStage[] = [
  "interested",
  "applied",
  "interviewing",
  "waiting_response",
  "offer",
  "rejected",
  "closed",
];

const STAGE_COLOR: Record<PipelineStage, string> = {
  interested: "text-blue-400",
  applied: "text-indigo-400",
  interviewing: "text-orange-400",
  waiting_response: "text-yellow-400",
  offer: "text-green-400",
  rejected: "text-red-400",
  closed: "text-gray-400",
};

interface JobDetailModalProps {
  job: Job | null;
  onClose: () => void;
  onJobUpdated: (updated: Job) => void;
  onJobDeleted?: (id: number) => void;
}

export function JobDetailModal({ job, onClose, onJobUpdated, onJobDeleted }: JobDetailModalProps) {
  const open = job !== null;
  const containerRef = useModalBehavior({ open, onClose });
  const [events, setEvents] = useState<JobPipelineEvent[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [notes, setNotes] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);
  const [movingStage, setMovingStage] = useState<PipelineStage | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const notesRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!job) return;
    setNotes(job.notes ?? "");
    setConfirmingDelete(false);
    setLoadingEvents(true);
    api.getJobPipeline(job.id).then((res) => {
      setEvents(res.events);
    }).catch(() => {}).finally(() => setLoadingEvents(false));
  }, [job?.id]);

  const saveNotes = useCallback(async () => {
    if (!job) return;
    setSavingNotes(true);
    try {
      const updated = await api.updateJob(job.id, { notes });
      onJobUpdated(updated);
    } catch {
      // silent — notes will be retried next blur
    } finally {
      setSavingNotes(false);
    }
  }, [job, notes, onJobUpdated]);

  const handleRemoveFromPipeline = useCallback(async () => {
    if (!job) return;
    try {
      const updated = await api.updateJob(job.id, { status: "new" });
      onJobUpdated(updated);
    } catch {
      // ignore
    }
  }, [job, onJobUpdated]);

  const handleMoveToStage = useCallback(async (stage: PipelineStage) => {
    if (!job) return;
    setMovingStage(stage);
    try {
      const event = await api.moveJobToStage(job.id, stage);
      setEvents((prev) => [...prev, event]);
      const updated = await api.updateJob(job.id, { status: "in_pipeline" });
      onJobUpdated(updated);
    } catch {
      // ignore
    } finally {
      setMovingStage(null);
    }
  }, [job, onJobUpdated]);

  const handleDeletePermanently = useCallback(async () => {
    if (!job) return;
    setDeleting(true);
    try {
      await api.deleteJob(job.id);
      onJobDeleted?.(job.id);
      onClose();
    } catch {
      setDeleting(false);
      setConfirmingDelete(false);
    }
  }, [job, onJobDeleted, onClose]);

  const handleToggleStar = useCallback(async () => {
    if (!job) return;
    const updated = await api.updateJob(job.id, { starred: job.starred ? 0 : 1 });
    onJobUpdated(updated);
  }, [job, onJobUpdated]);

  if (!open || !job) return null;

  const currentStageIdx = job.current_stage
    ? PIPELINE_STAGES.indexOf(job.current_stage)
    : -1;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-end"
      role="dialog"
      aria-modal="true"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Panel */}
      <div
        ref={containerRef}
        className="relative z-10 flex flex-col h-full w-full max-w-2xl bg-background border-l border-border shadow-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-start gap-3 p-4 border-b border-border shrink-0">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="font-bold text-sm">{job.company}</span>
              {job.sector && (
                <span className="text-xs text-muted-foreground">· {job.sector}</span>
              )}
              <button
                onClick={handleToggleStar}
                className={cn(
                  "text-sm transition-colors",
                  job.starred ? "text-warning" : "text-muted-foreground hover:text-warning",
                )}
                title={job.starred ? "Unstar" : "Star"}
              >
                <Star className="w-3.5 h-3.5" fill={job.starred ? "currentColor" : "none"} />
              </button>
            </div>
            <p className="text-sm text-foreground/90">{job.title}</p>
            <div className="flex flex-wrap gap-2 mt-1 text-xs text-muted-foreground">
              {job.location && <span>{job.location}</span>}
              {job.comp_est && <span>· {job.comp_est}</span>}
              {job.date_added && <span>· Added {job.date_added}</span>}
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {job.link && (
              <a
                href={job.link}
                target="_blank"
                rel="noopener noreferrer"
                className="p-1.5 text-muted-foreground hover:text-foreground transition-colors"
                title="Open posting"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            )}
            <Button ghost size="icon" onClick={onClose} title="Close">
              <X />
            </Button>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto min-h-0">
          {/* Description */}
          {job.description && (
            <section className="p-4 border-b border-border">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-2">
                Description
              </h3>
              <p className="text-sm leading-relaxed whitespace-pre-wrap text-foreground/80">
                {job.description}
              </p>
            </section>
          )}

          {/* Notes */}
          <section className="p-4 border-b border-border">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Notes
              </h3>
              {savingNotes && <Spinner className="w-3 h-3" />}
            </div>
            <textarea
              ref={notesRef}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              onBlur={saveNotes}
              placeholder="Add notes about this opportunity..."
              rows={4}
              className="w-full bg-transparent border border-border rounded px-3 py-2 text-sm resize-none focus:outline-none focus:border-ring placeholder:text-muted-foreground/50"
            />
          </section>

          {/* Move to stage */}
          <section className="p-4 border-b border-border">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Move to Stage
              </h3>
              {job.status === "in_pipeline" && (
                <button
                  onClick={handleRemoveFromPipeline}
                  className="flex items-center gap-1.5 px-2.5 py-1 text-xs border border-border rounded text-muted-foreground hover:border-ring/50 hover:text-foreground transition-colors"
                >
                  <ArrowLeftCircle className="w-3.5 h-3.5 shrink-0" />
                  Back to Triage
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              {PIPELINE_STAGES.map((stage, idx) => {
                const isCurrent = stage === job.current_stage;
                const isDisabled = movingStage !== null;
                return (
                  <button
                    key={stage}
                    disabled={isDisabled || isCurrent}
                    onClick={() => handleMoveToStage(stage)}
                    className={cn(
                      "flex items-center gap-1 px-2.5 py-1 text-xs border rounded transition-colors",
                      isCurrent
                        ? "border-ring bg-ring/10 text-foreground font-medium"
                        : "border-border text-muted-foreground hover:border-ring/50 hover:text-foreground",
                      isDisabled && !isCurrent && "opacity-50 cursor-not-allowed",
                    )}
                  >
                    {movingStage === stage ? (
                      <Spinner className="w-3 h-3" />
                    ) : (
                      idx > currentStageIdx && currentStageIdx !== -1 && (
                        <ChevronRight className="w-3 h-3" />
                      )
                    )}
                    <span className={STAGE_COLOR[stage]}>{STAGE_LABELS[stage]}</span>
                  </button>
                );
              })}
            </div>
          </section>

          {/* Pipeline history */}
          <section className="p-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-3">
              Pipeline History
            </h3>
            {loadingEvents ? (
              <div className="flex justify-center py-4">
                <Spinner className="w-4 h-4" />
              </div>
            ) : events.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Not in pipeline yet. Use the buttons above to start tracking.
              </p>
            ) : (
              <ol className="space-y-2">
                {events.map((ev, i) => (
                  <li key={ev.id} className="flex gap-3 text-sm">
                    <div className="flex flex-col items-center">
                      <div
                        className={cn(
                          "w-2 h-2 rounded-full mt-0.5 shrink-0",
                          i === events.length - 1 ? "bg-ring" : "bg-muted-foreground/40",
                        )}
                      />
                      {i < events.length - 1 && (
                        <div className="w-px flex-1 bg-border mt-1" />
                      )}
                    </div>
                    <div className="pb-2">
                      <div className="flex items-center gap-2">
                        <span className={cn("font-medium text-xs", STAGE_COLOR[ev.stage])}>
                          {STAGE_LABELS[ev.stage]}
                        </span>
                        <span className="text-xs text-muted-foreground">{ev.entered_at}</span>
                      </div>
                      {ev.notes && (
                        <p className="text-xs text-muted-foreground mt-0.5">{ev.notes}</p>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </section>
        </div>

        {/* Footer — permanent delete */}
        {onJobDeleted && (
          <div className="shrink-0 border-t border-border px-4 py-3 flex items-center justify-end">
            {confirmingDelete ? (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground text-xs">Permanently delete this job?</span>
                <button
                  disabled={deleting}
                  onClick={handleDeletePermanently}
                  className="px-3 py-1 text-xs rounded bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors disabled:opacity-50"
                >
                  {deleting ? "Deleting…" : "Yes, delete"}
                </button>
                <button
                  disabled={deleting}
                  onClick={() => setConfirmingDelete(false)}
                  className="px-3 py-1 text-xs rounded border border-border text-muted-foreground hover:text-foreground transition-colors"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setConfirmingDelete(true)}
                className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-destructive transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete permanently
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
