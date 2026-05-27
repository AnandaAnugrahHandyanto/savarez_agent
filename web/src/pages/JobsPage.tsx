import { useEffect, useLayoutEffect, useState } from "react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { usePageHeader } from "@/contexts/usePageHeader";
import { api } from "@/lib/api";
import { TriageView } from "@/components/jobs/TriageView";
import { PipelineView } from "@/components/jobs/PipelineView";
import { cn } from "@/lib/utils";

type Tab = "triage" | "pipeline";

export default function JobsPage() {
  const [activeTab, setActiveTab] = useState<Tab>("triage");
  const [newCount, setNewCount] = useState<number | null>(null);
  const [pipelineCount, setPipelineCount] = useState<number | null>(null);
  const { setAfterTitle } = usePageHeader();

  useEffect(() => {
    api.getJobStats().then((stats) => {
      setNewCount(stats.status_counts["new"] ?? 0);
      const total = Object.values(stats.stage_counts).reduce((a, b) => a + b, 0);
      setPipelineCount(total);
    }).catch(() => {});
  }, []);

  useLayoutEffect(() => {
    setAfterTitle(
      <div className="flex items-center gap-2">
        {newCount !== null && newCount > 0 && (
          <Badge tone="warning">{newCount} new</Badge>
        )}
        {pipelineCount !== null && pipelineCount > 0 && (
          <Badge tone="success">{pipelineCount} in pipeline</Badge>
        )}
      </div>,
    );
    return () => setAfterTitle(null);
  }, [newCount, pipelineCount, setAfterTitle]);

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex gap-0 border-b border-border shrink-0 px-4">
        {(["triage", "pipeline"] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px capitalize",
              activeTab === tab
                ? "border-foreground text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* View */}
      <div className="flex-1 min-h-0">
        {activeTab === "triage" ? <TriageView /> : <PipelineView />}
      </div>
    </div>
  );
}
