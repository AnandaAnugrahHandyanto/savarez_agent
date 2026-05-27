import { useCallback, useEffect, useRef, useState } from "react";
import {
  Star,
  Highlighter,
  BookOpen,
  Clock,
  PlusCircle,
  X,
  ChevronLeft,
  ChevronRight,
  Search,
} from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Toast } from "@/components/Toast";
import { JobCard } from "./JobCard";
import { JobDetailModal } from "./JobDetailModal";
import { api } from "@/lib/api";
import type { Job, JobStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS_TABS: { key: JobStatus | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "new", label: "New" },
  { key: "highlighted", label: "Highlighted" },
  { key: "for_later", label: "For Later" },
  { key: "read", label: "Read" },
  { key: "in_pipeline", label: "In Pipeline" },
  { key: "discarded", label: "Discarded" },
];

const PAGE_SIZE = 20;

export function TriageView() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<JobStatus | "all">("new");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [page, setPage] = useState(0);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const { toast, showToast } = useToastState();
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const params: Parameters<typeof api.getJobs>[0] = {
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      };
      if (activeTab !== "all") params.status = activeTab;
      if (debouncedSearch) params.search = debouncedSearch;
      const res = await api.getJobs(params);
      setJobs(res.jobs);
      setTotal(res.total);
    } catch {
      showToast("Failed to load jobs", "error");
    } finally {
      setLoading(false);
    }
  }, [activeTab, debouncedSearch, page]);

  useEffect(() => { fetchJobs(); }, [fetchJobs]);

  useEffect(() => {
    setPage(0);
  }, [activeTab, debouncedSearch]);

  const handleSearchChange = (val: string) => {
    setSearch(val);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => setDebouncedSearch(val), 300);
  };

  const handleAction = useCallback(async (
    job: Job,
    status: JobStatus,
    label: string,
  ) => {
    try {
      const updated = await api.updateJob(job.id, { status });
      setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
      if (selectedJob?.id === updated.id) setSelectedJob(updated);
      showToast(`Marked as ${label}`, "success");
    } catch {
      showToast("Failed to update", "error");
    }
  }, [selectedJob]);

  const handleAddToPipeline = useCallback(async (job: Job) => {
    try {
      await api.moveJobToStage(job.id, "interested");
      const updated = await api.updateJob(job.id, { status: "in_pipeline" });
      setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
      if (selectedJob?.id === updated.id) setSelectedJob(updated);
      showToast("Added to pipeline", "success");
    } catch {
      showToast("Failed to add to pipeline", "error");
    }
  }, [selectedJob]);

  const handleToggleStar = useCallback(async (job: Job) => {
    try {
      const updated = await api.updateJob(job.id, { starred: job.starred ? 0 : 1 });
      setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
      if (selectedJob?.id === updated.id) setSelectedJob(updated);
    } catch {
      showToast("Failed to update", "error");
    }
  }, [selectedJob]);

  const handleJobDeleted = useCallback((id: number) => {
    setJobs((prev) => prev.filter((j) => j.id !== id));
    setTotal((t) => t - 1);
    setSelectedJob(null);
  }, []);

  const handleJobUpdated = useCallback((updated: Job) => {
    setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
    setSelectedJob(updated);
  }, []);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="flex flex-col h-full">
      {/* Filter bar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border shrink-0 overflow-x-auto scrollbar-none">
        <div className="flex gap-1 shrink-0">
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                "px-3 py-1 text-xs rounded transition-colors whitespace-nowrap",
                activeTab === tab.key
                  ? "bg-foreground/10 text-foreground font-medium"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 border border-border rounded px-2 py-1 ml-auto">
          <Search className="w-3 h-3 text-muted-foreground shrink-0" />
          <input
            type="text"
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
            placeholder="Search jobs..."
            className="text-xs bg-transparent outline-none w-40 placeholder:text-muted-foreground/60"
          />
          {search && (
            <button onClick={() => { setSearch(""); setDebouncedSearch(""); }}>
              <X className="w-3 h-3 text-muted-foreground hover:text-foreground" />
            </button>
          )}
        </div>
      </div>

      {/* Job list */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
        {loading ? (
          <div className="flex justify-center py-12">
            <Spinner className="w-5 h-5" />
          </div>
        ) : jobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-muted-foreground text-sm">
            <p>No jobs in this category.</p>
            {activeTab === "new" && (
              <p className="text-xs mt-1 text-muted-foreground/60">
                New jobs will appear here after the daily search runs.
              </p>
            )}
          </div>
        ) : (
          jobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onClick={() => setSelectedJob(job)}
              actions={
                <JobTriageActions
                  job={job}
                  onAction={handleAction}
                  onToggleStar={handleToggleStar}
                  onAddToPipeline={handleAddToPipeline}
                />
              }
            />
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 py-3 border-t border-border shrink-0 text-xs text-muted-foreground">
          <Button
            ghost
            size="icon"
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <span>
            Page {page + 1} of {totalPages} · {total} jobs
          </span>
          <Button
            ghost
            size="icon"
            disabled={page >= totalPages - 1}
            onClick={() => setPage((p) => p + 1)}
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      )}

      <JobDetailModal
        job={selectedJob}
        onClose={() => setSelectedJob(null)}
        onJobUpdated={handleJobUpdated}
        onJobDeleted={handleJobDeleted}
      />

      <Toast toast={toast} />
    </div>
  );
}

interface TriageActionsProps {
  job: Job;
  onAction: (job: Job, status: JobStatus, label: string) => void;
  onToggleStar: (job: Job) => void;
  onAddToPipeline: (job: Job) => void;
}

function JobTriageActions({ job, onAction, onToggleStar, onAddToPipeline }: TriageActionsProps) {
  return (
    <div className="flex items-center gap-0.5">
      <Button
        ghost
        size="icon"
        title={job.starred ? "Unstar" : "Star"}
        className={job.starred ? "text-warning" : "text-muted-foreground"}
        onClick={(e) => {
          e.stopPropagation();
          onToggleStar(job);
        }}
      >
        <Star className="w-3.5 h-3.5" fill={job.starred ? "currentColor" : "none"} />
      </Button>
      <Button
        ghost
        size="icon"
        title={job.status === "highlighted" ? "Remove highlight" : "Highlight"}
        className={job.status === "highlighted" ? "text-warning" : "text-muted-foreground"}
        onClick={(e) => {
          e.stopPropagation();
          job.status === "highlighted"
            ? onAction(job, "new", "unhighlighted")
            : onAction(job, "highlighted", "highlighted");
        }}
      >
        <Highlighter className="w-3.5 h-3.5" />
      </Button>
      <Button
        ghost
        size="icon"
        title={job.status === "read" ? "Mark unread" : "Mark read"}
        className={job.status === "read" ? "text-blue-400" : "text-muted-foreground"}
        onClick={(e) => {
          e.stopPropagation();
          job.status === "read"
            ? onAction(job, "new", "unread")
            : onAction(job, "read", "read");
        }}
      >
        <BookOpen className="w-3.5 h-3.5" />
      </Button>
      <Button
        ghost
        size="icon"
        title={job.status === "for_later" ? "Remove from later" : "Save for later"}
        className={job.status === "for_later" ? "text-purple-400" : "text-muted-foreground"}
        onClick={(e) => {
          e.stopPropagation();
          job.status === "for_later"
            ? onAction(job, "new", "removed from later")
            : onAction(job, "for_later", "for later");
        }}
      >
        <Clock className="w-3.5 h-3.5" />
      </Button>
      {job.status !== "in_pipeline" && (
        <Button
          ghost
          size="icon"
          title="Add to pipeline"
          className="text-muted-foreground"
          onClick={(e) => { e.stopPropagation(); onAddToPipeline(job); }}
        >
          <PlusCircle className="w-3.5 h-3.5" />
        </Button>
      )}
      <Button
        ghost
        size="icon"
        title={job.status === "discarded" ? "Restore" : "Discard"}
        className={job.status === "discarded" ? "text-destructive" : "text-muted-foreground hover:text-destructive"}
        onClick={(e) => {
          e.stopPropagation();
          job.status === "discarded"
            ? onAction(job, "new", "restored")
            : onAction(job, "discarded", "discarded");
        }}
      >
        <X className="w-3.5 h-3.5" />
      </Button>
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
