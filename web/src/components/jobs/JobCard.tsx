import type { ReactNode } from "react";
import { ExternalLink, MapPin, DollarSign, Calendar } from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Job, PipelineStage } from "@/lib/api";

export const STAGE_LABELS: Record<PipelineStage, string> = {
  interested: "Interested",
  applied: "Applied",
  interviewing: "Interviewing",
  waiting_response: "Waiting Response",
  offer: "Offer",
  rejected: "Rejected",
  closed: "Closed",
};

type BadgeTone = "default" | "destructive" | "outline" | "secondary" | "success" | "warning";

const STAGE_TONE: Record<PipelineStage, BadgeTone> = {
  interested: "default",
  applied: "secondary",
  interviewing: "warning",
  waiting_response: "warning",
  offer: "success",
  rejected: "destructive",
  closed: "outline",
};

const STATUS_BADGE: Record<string, { tone: BadgeTone; className?: string }> = {
  new: { tone: "secondary" },
  highlighted: { tone: "warning" },
  read: { tone: "outline", className: "border-blue-400/30 bg-blue-400/15 text-blue-400" },
  for_later: { tone: "outline", className: "border-purple-400/30 bg-purple-400/15 text-purple-400" },
  discarded: { tone: "destructive" },
  in_pipeline: { tone: "success" },
};

interface JobCardProps {
  job: Job;
  onClick?: () => void;
  actions?: ReactNode;
  draggable?: boolean;
  onDragStart?: (e: React.DragEvent) => void;
  className?: string;
  showStage?: boolean;
}

export function JobCard({
  job,
  onClick,
  actions,
  draggable,
  onDragStart,
  className,
  showStage = false,
}: JobCardProps) {
  const dateLabel = job.current_stage_date
    ? `In stage: ${job.current_stage_date}`
    : job.date_added
      ? `Added: ${job.date_added}`
      : null;

  const isDenver = /denver|colorado/i.test(job.location ?? "");

  return (
    <Card
      className={cn(
        "transition-colors",
        onClick && "cursor-pointer hover:bg-card",
        draggable && "cursor-grab active:cursor-grabbing",
        className,
      )}
      draggable={draggable}
      onDragStart={onDragStart}
      onClick={onClick}
    >
      <CardContent className="flex items-start gap-3 py-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-2 mb-1">
            <div className="flex-1 min-w-0">
              <span className="font-medium text-sm">{job.company}</span>
              {job.sector && (
                <span className="text-xs text-muted-foreground ml-1.5">
                  · {job.sector}
                </span>
              )}
            </div>
            {job.starred === 1 && (
              <span className="text-warning text-xs shrink-0">★</span>
            )}
          </div>

          <p className="text-sm text-foreground/90 mb-1.5 leading-snug">
            {job.title}
          </p>

          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
            {job.location && (
              <span
                className="flex items-center gap-1"
                style={isDenver ? { color: "color-mix(in oklab, var(--color-warning) 55%, transparent)" } : undefined}
              >
                <MapPin className="w-3 h-3 shrink-0" />
                <span className="truncate">{job.location}</span>
              </span>
            )}
            {job.comp_est && (
              <span className="flex items-center gap-1">
                <DollarSign className="w-3 h-3 shrink-0" />
                <span className="truncate">{job.comp_est}</span>
                {job.comp_source && job.comp_source !== "posting" && job.comp_source !== "posting_base_only" && (
                  <span
                    className="text-[10px] shrink-0 rounded px-1"
                    style={{
                      color: "var(--color-warning)",
                      border: "1px solid color-mix(in oklab, var(--color-warning) 40%, transparent)",
                    }}
                    title={`Comp source: ${job.comp_source}`}
                  >
                    est.
                  </span>
                )}
              </span>
            )}
            {dateLabel && (
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3 shrink-0" />
                <span>{dateLabel}</span>
              </span>
            )}
          </div>

          {showStage && job.current_stage && (
            <div className="mt-1.5">
              <Badge tone={STAGE_TONE[job.current_stage] ?? "secondary"}>
                {STAGE_LABELS[job.current_stage]}
              </Badge>
            </div>
          )}

          {!showStage && job.status && job.status !== "new" && (
            <div className="mt-1.5">
              {(() => {
                const b = STATUS_BADGE[job.status] ?? { tone: "secondary" as BadgeTone };
                return (
                  <Badge tone={b.tone} className={b.className}>
                    {job.status.replace(/_/g, " ")}
                  </Badge>
                );
              })()}
            </div>
          )}
        </div>

        <div
          className="flex items-center gap-1 shrink-0"
          onClick={(e) => e.stopPropagation()}
        >
          {job.link && (
            <a
              href={job.link}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1 text-muted-foreground hover:text-foreground transition-colors"
              title="Open job posting"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
          {actions}
        </div>
      </CardContent>
    </Card>
  );
}
