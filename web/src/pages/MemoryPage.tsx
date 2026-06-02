import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { Brain, Database, Filter, RefreshCw, Search, User } from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Toast } from "@/components/Toast";
import { useToast } from "@/hooks/useToast";
import { usePageHeader } from "@/contexts/usePageHeader";
import { api } from "@/lib/api";
import type { MemoriesResponse, MemoryEntryInfo, MemoryProfileSummary, MemoryTarget } from "@/lib/api";
import { cn } from "@/lib/utils";

type TargetFilter = "all" | MemoryTarget;

const TARGET_LABELS: Record<TargetFilter, string> = {
  all: "All memory",
  memory: "Agent notes",
  user: "User profile",
};

export default function MemoryPage() {
  const [data, setData] = useState<MemoriesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");
  const [activeProfile, setActiveProfile] = useState("all");
  const [activeTarget, setActiveTarget] = useState<TargetFilter>("all");
  const { toast, showToast } = useToast();
  const { setAfterTitle, setEnd } = usePageHeader();

  const load = useCallback(async () => {
    setRefreshing(true);
    try {
      const res = await api.getMemories({ profile: "all" });
      setData(res);
    } catch (e) {
      showToast(`Error loading memory: ${e}`, "error");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [showToast]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(id);
  }, [load]);

  const profiles = useMemo(() => data?.profiles ?? [], [data]);
  const memories = useMemo(() => data?.memories ?? [], [data]);
  const lowerSearch = search.trim().toLowerCase();

  const filtered = useMemo(() => {
    return memories.filter((entry) => {
      if (activeProfile !== "all" && entry.profile !== activeProfile) return false;
      if (activeTarget !== "all" && entry.target !== activeTarget) return false;
      if (!lowerSearch) return true;
      return (
        entry.content.toLowerCase().includes(lowerSearch) ||
        entry.tags.some((tag) => tag.toLowerCase().includes(lowerSearch))
      );
    });
  }, [activeProfile, activeTarget, lowerSearch, memories]);

  useLayoutEffect(() => {
    setAfterTitle(
      <span className="whitespace-nowrap text-xs text-muted-foreground">
        {filtered.length} of {memories.length} entries
      </span>,
    );
    setEnd(
      <div className="flex items-center gap-2">
        <div className="relative hidden min-w-0 sm:block sm:w-64">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="h-8 rounded-none pl-8 text-xs"
            placeholder="Search memory or tags..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Button ghost size="sm" onClick={load} disabled={refreshing}>
          {refreshing ? <Spinner /> : <RefreshCw className="h-3.5 w-3.5" />}
          <span className="sr-only">Refresh memory</span>
        </Button>
      </div>,
    );
    return () => {
      setAfterTitle(null);
      setEnd(null);
    };
  }, [filtered.length, load, memories.length, refreshing, search, setAfterTitle, setEnd]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="text-2xl text-primary" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Toast toast={toast} />

      <div className="relative sm:hidden">
        <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="h-9 rounded-none pl-8 text-xs"
          placeholder="Search memory or tags..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <aside className="flex flex-col gap-3">
          <FilterPanel
            profiles={profiles}
            activeProfile={activeProfile}
            activeTarget={activeTarget}
            onProfileChange={setActiveProfile}
            onTargetChange={setActiveTarget}
          />
        </aside>

        <section className="min-w-0">
          <Card className="rounded-none">
            <CardHeader className="py-3 px-4">
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <Database className="h-4 w-4" />
                  Hermes memory
                </CardTitle>
                <Badge tone="secondary" className="text-xs">
                  {filtered.length} entr{filtered.length === 1 ? "y" : "ies"}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="px-4 pb-4">
              {filtered.length === 0 ? (
                <div className="py-10 text-center text-sm text-muted-foreground">
                  No memory entries match these filters.
                </div>
              ) : (
                <div className="grid gap-3">
                  {filtered.map((entry) => (
                    <MemoryEntryCard key={entry.id} entry={entry} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}

function FilterPanel({
  profiles,
  activeProfile,
  activeTarget,
  onProfileChange,
  onTargetChange,
}: {
  profiles: MemoryProfileSummary[];
  activeProfile: string;
  activeTarget: TargetFilter;
  onProfileChange: (profile: string) => void;
  onTargetChange: (target: TargetFilter) => void;
}) {
  const totalEntries = profiles.reduce((sum, profile) => sum + profile.entry_count, 0);

  return (
    <div className="rounded-none border border-border bg-muted/20">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Filter className="h-3 w-3 text-text-tertiary" />
        <span className="font-mondwest text-display text-xs tracking-[0.12em] text-text-secondary">
          Filters
        </span>
      </div>

      <div className="p-2">
        <div className="px-2 pb-1 font-mondwest text-display text-xs tracking-[0.12em] text-text-tertiary">
          Agent / profile tags
        </div>
        <FilterButton
          active={activeProfile === "all"}
          label="All agents"
          count={totalEntries}
          onClick={() => onProfileChange("all")}
        />
        {profiles.map((profile) => (
          <FilterButton
            key={profile.name}
            active={activeProfile === profile.name}
            label={`agent:${profile.name}`}
            count={profile.entry_count}
            onClick={() => onProfileChange(profile.name)}
          />
        ))}
      </div>

      <div className="border-t border-border p-2">
        <div className="px-2 pb-1 font-mondwest text-display text-xs tracking-[0.12em] text-text-tertiary">
          Store tags
        </div>
        {(["all", "memory", "user"] as TargetFilter[]).map((target) => (
          <FilterButton
            key={target}
            active={activeTarget === target}
            label={target === "all" ? TARGET_LABELS[target] : `target:${target}`}
            onClick={() => onTargetChange(target)}
          />
        ))}
      </div>
    </div>
  );
}

function FilterButton({
  active,
  label,
  count,
  onClick,
}: {
  active: boolean;
  label: string;
  count?: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full items-center justify-between gap-2 px-2 py-1.5 text-left text-xs transition-colors",
        active ? "bg-midground/10 text-midground" : "text-text-secondary hover:text-midground",
      )}
    >
      <span className="truncate font-mono">{label}</span>
      {count !== undefined && (
        <span className="shrink-0 tabular-nums text-text-tertiary">{count}</span>
      )}
    </button>
  );
}

function MemoryEntryCard({ entry }: { entry: MemoryEntryInfo }) {
  return (
    <article className="rounded-none border border-border bg-background/40 p-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        {entry.target === "user" ? (
          <User className="h-4 w-4 text-muted-foreground" />
        ) : (
          <Brain className="h-4 w-4 text-muted-foreground" />
        )}
        <Badge tone={entry.target === "user" ? "success" : "secondary"} className="text-xs">
          {TARGET_LABELS[entry.target]}
        </Badge>
        <span className="font-mono text-xs text-muted-foreground">
          #{entry.entry_index + 1}
        </span>
      </div>

      <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-primary">
        {entry.content}
      </p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {entry.tags.map((tag) => (
          <Badge key={tag} tone="outline" className="font-mono text-xs">
            {tag}
          </Badge>
        ))}
      </div>

      <div className="mt-2 truncate font-mono text-[0.68rem] text-text-tertiary">
        profile:{entry.profile} · agent:{entry.agent} · target:{entry.target}
      </div>
    </article>
  );
}
