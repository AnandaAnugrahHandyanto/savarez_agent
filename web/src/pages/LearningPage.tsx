import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { Archive, ChevronDown, ChevronRight, GraduationCap } from "lucide-react";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Card, CardContent } from "@nous-research/ui/ui/components/card";
import { Input } from "@nous-research/ui/ui/components/input";
import { Label } from "@nous-research/ui/ui/components/label";
import { Toast } from "@nous-research/ui/ui/components/toast";
import { useToast } from "@nous-research/ui/hooks/use-toast";
import { api } from "@/lib/api";
import type { LearningTopic, LearningTopicDetail } from "@/lib/api";
import { usePageHeader } from "@/contexts/usePageHeader";

function accuracyLabel(acc: number | null | undefined): string {
  if (acc === null || acc === undefined) return "—";
  return `${Math.round(acc * 100)}%`;
}

function masteryPct(topic: LearningTopic): number {
  const p = topic.progress;
  if (!p || p.cards_total === 0) return 0;
  return Math.round((p.cards_mastered / p.cards_total) * 100);
}

type BadgeTone = "default" | "destructive" | "outline" | "secondary" | "success" | "warning";

const STATUS_TONE: Record<string, BadgeTone> = {
  active: "success",
  paused: "secondary",
  done: "default",
  archived: "outline",
};

export default function LearningPage() {
  const [topics, setTopics] = useState<LearningTopic[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<LearningTopicDetail | null>(null);
  const { toast, showToast } = useToast();
  const { setEnd } = usePageHeader();

  // Create form state.
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [goal, setGoal] = useState("");
  const [schedule, setSchedule] = useState("");
  const [mode, setMode] = useState("lesson");
  const [creating, setCreating] = useState(false);

  const loadTopics = useCallback(() => {
    api
      .getLearningTopics()
      .then(setTopics)
      .catch((e) => showToast(`Failed to load topics: ${e}`, "error"))
      .finally(() => setLoading(false));
  }, [showToast]);

  useEffect(() => {
    loadTopics();
  }, [loadTopics]);

  const toggleExpand = useCallback(
    (id: string) => {
      if (expanded === id) {
        setExpanded(null);
        setDetail(null);
        return;
      }
      setExpanded(id);
      setDetail(null);
      api
        .getLearningTopic(id)
        .then(setDetail)
        .catch((e) => showToast(`Failed to load topic: ${e}`, "error"));
    },
    [expanded, showToast],
  );

  const handleCreate = async () => {
    if (!title.trim()) {
      showToast("Title is required", "error");
      return;
    }
    setCreating(true);
    try {
      await api.createLearningTopic({
        title: title.trim(),
        goal: goal.trim() || undefined,
        schedule: schedule.trim() || undefined,
        mode,
      });
      showToast("Topic created ✓", "success");
      setTitle("");
      setGoal("");
      setSchedule("");
      setMode("lesson");
      setShowCreate(false);
      loadTopics();
    } catch (e) {
      showToast(`Failed to create: ${e}`, "error");
    } finally {
      setCreating(false);
    }
  };

  const handleArchive = async (topic: LearningTopic) => {
    try {
      await api.archiveLearningTopic(topic.id);
      showToast(`Archived "${topic.title}"`, "success");
      if (expanded === topic.id) {
        setExpanded(null);
        setDetail(null);
      }
      loadTopics();
    } catch (e) {
      showToast(`Failed to archive: ${e}`, "error");
    }
  };

  useLayoutEffect(() => {
    setEnd(
      <Button className="uppercase" size="sm" onClick={() => setShowCreate((v) => !v)}>
        New Topic
      </Button>,
    );
    return () => setEnd(null);
  }, [setEnd]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="text-2xl text-primary" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {showCreate && (
        <Card>
          <CardContent className="flex flex-col gap-3 pt-6">
            <div className="flex flex-col gap-1">
              <Label>Title</Label>
              <Input
                value={title}
                placeholder="e.g. Python, Mortgages, AI agents"
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label>Goal (optional)</Label>
              <Input
                value={goal}
                placeholder="What do you want to get out of it?"
                onChange={(e) => setGoal(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label>Schedule (optional)</Label>
              <Input
                value={schedule}
                placeholder="1d  •  every 2d  •  0 9 * * 0"
                onChange={(e) => setSchedule(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label>Mode</Label>
              <select
                className="rounded-md border bg-transparent px-2 py-1 text-sm"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
              >
                <option value="lesson">Lesson</option>
                <option value="quiz">Quiz</option>
                <option value="reminder">Reminder</option>
              </select>
            </div>
            <div className="flex gap-2">
              <Button size="sm" onClick={handleCreate} disabled={creating}>
                {creating ? "Creating…" : "Create"}
              </Button>
              <Button size="sm" outlined onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {topics.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-20 text-muted-foreground">
          <GraduationCap className="text-3xl" />
          <p>No learning topics yet. Create one, or just tell Jane "help me learn X".</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {topics.map((topic) => {
            const p = topic.progress;
            const isOpen = expanded === topic.id;
            return (
              <Card key={topic.id}>
                <CardContent className="pt-5">
                  <div className="flex items-center justify-between gap-3">
                    <button
                      className="flex flex-1 items-center gap-2 text-left"
                      onClick={() => toggleExpand(topic.id)}
                    >
                      {isOpen ? (
                        <ChevronDown className="shrink-0" />
                      ) : (
                        <ChevronRight className="shrink-0" />
                      )}
                      <span className="font-medium">{topic.title}</span>
                      <Badge tone={STATUS_TONE[topic.status] ?? "default"}>
                        {topic.status}
                      </Badge>
                      {topic.cadence && (
                        <span className="text-xs text-muted-foreground">↻ {topic.cadence}</span>
                      )}
                    </button>
                    <Button
                      size="icon"
                      ghost
                      title="Archive"
                      onClick={() => handleArchive(topic)}
                    >
                      <Archive />
                    </Button>
                  </div>

                  {p && (
                    <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 pl-7 text-sm text-muted-foreground">
                      <span>
                        Lessons: {p.lessons_taught}/{p.lessons_total}
                      </span>
                      <span>
                        Cards: {p.cards_total} ({p.cards_mastered} mastered, {masteryPct(topic)}%)
                      </span>
                      <span>Weak spots: {p.weak_spots}</span>
                      <span>Accuracy: {accuracyLabel(p.accuracy)}</span>
                    </div>
                  )}

                  {isOpen && (
                    <div className="mt-4 pl-7">
                      {!detail || detail.topic.id !== topic.id ? (
                        <Spinner className="text-primary" />
                      ) : (
                        <div className="flex flex-col gap-4">
                          {detail.lessons.length > 0 && (
                            <div>
                              <p className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
                                Lessons
                              </p>
                              <ul className="flex flex-col gap-0.5 text-sm">
                                {detail.lessons.map((ls) => (
                                  <li key={ls.id}>
                                    <span className="mr-2">
                                      {ls.status === "taught" ? "✓" : "·"}
                                    </span>
                                    {ls.seq}. {ls.title || "(untitled)"}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          <div>
                            <p className="mb-1 text-xs font-semibold uppercase text-muted-foreground">
                              Weak spots
                            </p>
                            {detail.weak_spots.length === 0 ? (
                              <p className="text-sm text-muted-foreground">
                                None yet — nothing missed.
                              </p>
                            ) : (
                              <ul className="flex flex-col gap-0.5 text-sm">
                                {detail.weak_spots.map((c) => (
                                  <li key={c.id}>
                                    <span className="mr-2 text-destructive">
                                      ✗{c.lapses}
                                    </span>
                                    {c.question}
                                  </li>
                                ))}
                              </ul>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      <Toast toast={toast} />
    </div>
  );
}
