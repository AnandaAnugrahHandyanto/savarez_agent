import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import {
  Package,
  Search,
  Wrench,
  X,
  Cpu,
  Globe,
  Shield,
  Eye,
  Paintbrush,
  Brain,
  Blocks,
  Code,
  Zap,
  Filter,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Download,
} from "lucide-react";
import { api } from "@/lib/api";
import type {
  SkillInfo,
  ToolsetInfo,
  SkillsHubBrowseItem,
  SkillsHubBrowseResponse,
  SkillsHubInstalledSkill,
} from "@/lib/api";
import { useToast } from "@/hooks/useToast";
import { Toast } from "@/components/Toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Select, SelectOption } from "@/components/ui/select";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { PluginSlot } from "@/plugins";

/* ------------------------------------------------------------------ */
/*  Types & helpers                                                    */
/* ------------------------------------------------------------------ */

const CATEGORY_LABELS: Record<string, string> = {
  mlops: "MLOps",
  "mlops/cloud": "MLOps / Cloud",
  "mlops/evaluation": "MLOps / Evaluation",
  "mlops/inference": "MLOps / Inference",
  "mlops/models": "MLOps / Models",
  "mlops/training": "MLOps / Training",
  "mlops/vector-databases": "MLOps / Vector DBs",
  mcp: "MCP",
  "red-teaming": "Red Teaming",
  ocr: "OCR",
  p5js: "p5.js",
  ai: "AI",
  ux: "UX",
  ui: "UI",
};

function prettyCategory(
  raw: string | null | undefined,
  generalLabel: string,
): string {
  if (!raw) return generalLabel;
  if (CATEGORY_LABELS[raw]) return CATEGORY_LABELS[raw];
  return raw
    .split(/[-_/]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

const TOOLSET_ICONS: Record<
  string,
  React.ComponentType<{ className?: string }>
> = {
  computer: Cpu,
  web: Globe,
  security: Shield,
  vision: Eye,
  design: Paintbrush,
  ai: Brain,
  integration: Blocks,
  code: Code,
  automation: Zap,
};

function toolsetIcon(
  name: string,
): React.ComponentType<{ className?: string }> {
  const lower = name.toLowerCase();
  for (const [key, icon] of Object.entries(TOOLSET_ICONS)) {
    if (lower.includes(key)) return icon;
  }
  return Wrench;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function SkillsPage() {
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [toolsets, setToolsets] = useState<ToolsetInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [view, setView] = useState<"skills" | "toolsets" | "hub">("skills");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [togglingSkills, setTogglingSkills] = useState<Set<string>>(new Set());
  const [hub, setHub] = useState<SkillsHubBrowseResponse | null>(null);
  const [hubInstalled, setHubInstalled] = useState<SkillsHubInstalledSkill[]>([]);
  const [hubLoading, setHubLoading] = useState(false);
  const [hubPage, setHubPage] = useState(1);
  const [hubSource, setHubSource] = useState("all");
  const [installing, setInstalling] = useState<string | null>(null);
  const [confirmInstall, setConfirmInstall] = useState<SkillsHubBrowseItem | null>(null);
  const { toast, showToast } = useToast();
  const { t } = useI18n();
  const { setAfterTitle, setEnd } = usePageHeader();

  useEffect(() => {
    Promise.all([api.getSkills(), api.getToolsets(), api.getInstalledHubSkills()])
      .then(([s, tsets, hubSkills]) => {
        setSkills(s);
        setToolsets(tsets);
        setHubInstalled(hubSkills.installed);
      })
      .catch(() => showToast(t.common.loading, "error"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const id = window.setInterval(() => {
      Promise.all([api.getSkills(), api.getToolsets(), api.getInstalledHubSkills()])
        .then(([s, tsets, hubSkills]) => {
          setSkills(s);
          setToolsets(tsets);
          setHubInstalled(hubSkills.installed);
        })
        .catch(() => {});
    }, 8000);
    return () => window.clearInterval(id);
  }, []);

  const loadHub = useCallback(
    (p: number, src: string) => {
      setHubLoading(true);
      api
        .browseSkillsHub(p, 20, src)
        .then(setHub)
        .catch((e) => showToast(String(e), "error"))
        .finally(() => setHubLoading(false));
    },
    [showToast],
  );

  useEffect(() => {
    if (view !== "hub") return;
    loadHub(hubPage, hubSource);
  }, [hubPage, hubSource, loadHub, view]);

  const installedSkillNames = useMemo(
    () => new Set(skills.map((s) => s.name)),
    [skills],
  );

  const hubInstalledNames = useMemo(
    () => new Set(hubInstalled.map((s) => s.name)),
    [hubInstalled],
  );

  const handleInstallHub = async (item: SkillsHubBrowseItem, confirm: boolean) => {
    setInstalling(item.identifier);
    try {
      await api.installHubSkill({
        identifier: item.identifier,
        confirm,
        activate_now: true,
      });
      showToast(`${t.common.create} ${item.name}`, "success");
      const [s, installed] = await Promise.all([
        api.getSkills(),
        api.getInstalledHubSkills(),
      ]);
      setSkills(s);
      setHubInstalled(installed.installed);
    } catch (e) {
      const msg = String(e);
      if (msg.includes("409") && msg.includes("confirmation_required")) {
        setConfirmInstall(item);
      } else {
        showToast(msg, "error");
      }
    } finally {
      setInstalling(null);
    }
  };

  const handleUninstallHub = async (name: string) => {
    setInstalling(name);
    try {
      await api.uninstallHubSkill({ name, activate_now: true });
      showToast(`${t.common.removed}: ${name}`, "success");
      const [s, installed] = await Promise.all([
        api.getSkills(),
        api.getInstalledHubSkills(),
      ]);
      setSkills(s);
      setHubInstalled(installed.installed);
    } catch (e) {
      showToast(String(e), "error");
    } finally {
      setInstalling(null);
    }
  };

  useEffect(() => {
    if (view !== "hub") return;
    api
      .getInstalledHubSkills()
      .then((r) => setHubInstalled(r.installed))
      .catch(() => {});
  }, [view]);

  /* ---- Toggle skill ---- */
  const handleToggleSkill = async (skill: SkillInfo) => {
    setTogglingSkills((prev) => new Set(prev).add(skill.name));
    try {
      await api.toggleSkill(skill.name, !skill.enabled);
      setSkills((prev) =>
        prev.map((s) =>
          s.name === skill.name ? { ...s, enabled: !s.enabled } : s,
        ),
      );
      showToast(
        `${skill.name} ${skill.enabled ? t.common.disabled : t.common.enabled}`,
        "success",
      );
    } catch {
      showToast(`${t.common.failedToToggle} ${skill.name}`, "error");
    } finally {
      setTogglingSkills((prev) => {
        const next = new Set(prev);
        next.delete(skill.name);
        return next;
      });
    }
  };

  /* ---- Derived data ---- */
  const lowerSearch = search.toLowerCase();
  const isSearching = search.trim().length > 0;

  const searchMatchedSkills = useMemo(() => {
    if (!isSearching) return [];
    return skills.filter(
      (s) =>
        s.name.toLowerCase().includes(lowerSearch) ||
        s.description.toLowerCase().includes(lowerSearch) ||
        (s.category ?? "").toLowerCase().includes(lowerSearch),
    );
  }, [skills, isSearching, lowerSearch]);

  const activeSkills = useMemo(() => {
    if (isSearching) return [];
    if (!activeCategory)
      return [...skills].sort((a, b) => a.name.localeCompare(b.name));
    return skills
      .filter((s) =>
        activeCategory === "__none__"
          ? !s.category
          : s.category === activeCategory,
      )
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [skills, activeCategory, isSearching]);

  const allCategories = useMemo(() => {
    const cats = new Map<string, number>();
    for (const s of skills) {
      const key = s.category || "__none__";
      cats.set(key, (cats.get(key) || 0) + 1);
    }
    return [...cats.entries()]
      .sort((a, b) => {
        if (a[0] === "__none__") return -1;
        if (b[0] === "__none__") return 1;
        return a[0].localeCompare(b[0]);
      })
      .map(([key, count]) => ({
        key,
        name: prettyCategory(key === "__none__" ? null : key, t.common.general),
        count,
      }));
  }, [skills, t]);

  const enabledCount = skills.filter((s) => s.enabled).length;

  useLayoutEffect(() => {
    if (loading) {
      setAfterTitle(null);
      setEnd(null);
      return;
    }
    if (view === "hub") {
      setAfterTitle(
        <span className="whitespace-nowrap text-xs text-muted-foreground">
          {hub
            ? `${hub.page}/${hub.total_pages} · ${hub.total}`
            : "Skills Hub"}
        </span>,
      );
    } else {
      setAfterTitle(
        <span className="whitespace-nowrap text-xs text-muted-foreground">
          {t.skills.enabledOf
            .replace("{enabled}", String(enabledCount))
            .replace("{total}", String(skills.length))}
        </span>,
      );
    }
    setEnd(
      <div className="relative w-full min-w-0 sm:max-w-xs">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          className="h-8 pl-8 pr-7 text-xs"
          placeholder={t.common.search}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        {search && (
          <button
            type="button"
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => setSearch("")}
          >
            <X className="h-3 w-3" />
          </button>
        )}
      </div>,
    );
    return () => {
      setAfterTitle(null);
      setEnd(null);
    };
  }, [
    enabledCount,
    hub,
    loading,
    search,
    setAfterTitle,
    setEnd,
    skills.length,
    view,
    t,
  ]);

  const filteredToolsets = useMemo(() => {
    return toolsets.filter(
      (ts) =>
        !search ||
        ts.name.toLowerCase().includes(lowerSearch) ||
        ts.label.toLowerCase().includes(lowerSearch) ||
        ts.description.toLowerCase().includes(lowerSearch),
    );
  }, [toolsets, search, lowerSearch]);

  /* ---- Loading ---- */
  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <PluginSlot name="skills:top" />
      <Toast toast={toast} />

      {/* ═══════════════ Filter panel + Content ═══════════════ */}
      <div className="flex flex-col sm:flex-row sm:items-start gap-4">
        {/* ---- Filter panel ---- */}
        <aside
          aria-label={t.skills.title}
          className="sm:w-56 sm:shrink-0"
        >
          <div className="sm:sticky sm:top-0">
            <div
              className={`
                flex flex-col
                border border-border bg-muted/20
              `}
            >
              {/* Filter heading */}
              <div className="hidden sm:flex items-center gap-2 px-3 py-2 border-b border-border">
                <Filter className="h-3 w-3 text-muted-foreground" />
                <span className="font-mondwest text-[0.65rem] tracking-[0.12em] uppercase text-muted-foreground">
                  {t.skills.filters}
                </span>
              </div>

              {/* View switch (Skills / Toolsets) */}
              <div className="flex sm:flex-col gap-1 overflow-x-auto sm:overflow-x-visible scrollbar-none p-2">
                <PanelItem
                  icon={Package}
                  label={`${t.skills.all} (${skills.length})`}
                  active={view === "skills" && !isSearching}
                  onClick={() => {
                    setView("skills");
                    setActiveCategory(null);
                    setSearch("");
                  }}
                />
                <PanelItem
                  icon={Wrench}
                  label={`${t.skills.toolsets} (${toolsets.length})`}
                  active={view === "toolsets"}
                  onClick={() => {
                    setView("toolsets");
                    setSearch("");
                  }}
                />
                <PanelItem
                  icon={Download}
                  label="Skills Hub"
                  active={view === "hub"}
                  onClick={() => {
                    setView("hub");
                    setActiveCategory(null);
                    setHubPage(1);
                  }}
                />
              </div>

              {/* Category sub-filters (only for Skills view) */}
              {view === "skills" && !isSearching && allCategories.length > 0 && (
                <div className="hidden sm:flex flex-col border-t border-border">
                  <div className="px-3 pt-2 pb-1 font-mondwest text-[0.6rem] tracking-[0.12em] uppercase text-muted-foreground/70">
                    {t.skills.categories}
                  </div>
                  <div className="flex flex-col p-2 pt-1 gap-px max-h-[calc(100vh-340px)] overflow-y-auto">
                    {allCategories.map(({ key, name, count }) => {
                      const isActive = activeCategory === key;

                      return (
                        <button
                          key={key}
                          type="button"
                          onClick={() =>
                            setActiveCategory(isActive ? null : key)
                          }
                          className={`
                            group flex items-center gap-2 px-2 py-1
                            rounded-sm text-left text-[11px] cursor-pointer
                            transition-colors
                            ${
                              isActive
                                ? "bg-foreground/10 text-foreground"
                                : "text-muted-foreground hover:text-foreground hover:bg-foreground/5"
                            }
                          `}
                        >
                          <span className="flex-1 truncate">{name}</span>
                          <span
                            className={`text-[10px] tabular-nums ${
                              isActive
                                ? "text-foreground/60"
                                : "text-muted-foreground/50"
                            }`}
                          >
                            {count}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        </aside>

        {/* ---- Content ---- */}
        <div className="flex-1 min-w-0">
          {isSearching ? (
            /* Search results */
            <Card>
              <CardHeader className="py-3 px-4">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Search className="h-4 w-4" />
                    {t.skills.title}
                  </CardTitle>
                  <Badge variant="secondary" className="text-[10px]">
                    {t.skills.resultCount
                      .replace("{count}", String(searchMatchedSkills.length))
                      .replace(
                        "{s}",
                        searchMatchedSkills.length !== 1 ? "s" : "",
                      )}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="px-4 pb-4">
                {searchMatchedSkills.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-8">
                    {t.skills.noSkillsMatch}
                  </p>
                ) : (
                  <div className="grid gap-4">
                    <div>
                      <div className="flex items-center justify-between pb-2">
                        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                          {t.common.active}
                        </span>
                        <Badge variant="success" className="text-[10px]">
                          {searchMatchedSkills.filter((s) => s.enabled).length}
                        </Badge>
                      </div>
                      <div className="grid gap-1">
                        {searchMatchedSkills
                          .filter((s) => s.enabled)
                          .map((skill) => (
                            <SkillRow
                              key={skill.name}
                              skill={skill}
                              toggling={togglingSkills.has(skill.name)}
                              onToggle={() => handleToggleSkill(skill)}
                              noDescriptionLabel={t.skills.noDescription}
                            />
                          ))}
                        {searchMatchedSkills.filter((s) => s.enabled).length === 0 && (
                          <p className="text-xs text-muted-foreground py-4 text-center">
                            {t.common.none}
                          </p>
                        )}
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center justify-between pb-2">
                        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                          {t.common.inactive}
                        </span>
                        <Badge variant="outline" className="text-[10px]">
                          {searchMatchedSkills.filter((s) => !s.enabled).length}
                        </Badge>
                      </div>
                      <div className="grid gap-1">
                        {searchMatchedSkills
                          .filter((s) => !s.enabled)
                          .map((skill) => (
                            <SkillRow
                              key={skill.name}
                              skill={skill}
                              toggling={togglingSkills.has(skill.name)}
                              onToggle={() => handleToggleSkill(skill)}
                              noDescriptionLabel={t.skills.noDescription}
                            />
                          ))}
                        {searchMatchedSkills.filter((s) => !s.enabled).length === 0 && (
                          <p className="text-xs text-muted-foreground py-4 text-center">
                            {t.common.none}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ) : view === "skills" ? (
            /* Skills list */
            <div className="grid gap-4">
              <Card>
                <CardHeader className="py-3 px-4">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Package className="h-4 w-4" />
                      {activeCategory
                        ? prettyCategory(
                            activeCategory === "__none__"
                              ? null
                              : activeCategory,
                            t.common.general,
                          )
                        : t.skills.all}
                    </CardTitle>
                    <Badge variant="secondary" className="text-[10px]">
                      {t.skills.skillCount
                        .replace("{count}", String(activeSkills.length))
                        .replace("{s}", activeSkills.length !== 1 ? "s" : "")}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="px-4 pb-4 grid gap-4">
                  {activeSkills.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      {skills.length === 0
                        ? t.skills.noSkills
                        : t.skills.noSkillsMatch}
                    </p>
                  ) : (
                    <>
                      <div>
                        <div className="flex items-center justify-between pb-2">
                          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            {t.common.active}
                          </span>
                          <Badge variant="success" className="text-[10px]">
                            {activeSkills.filter((s) => s.enabled).length}
                          </Badge>
                        </div>
                        <div className="grid gap-1">
                          {activeSkills
                            .filter((s) => s.enabled)
                            .map((skill) => (
                              <SkillRow
                                key={skill.name}
                                skill={skill}
                                toggling={togglingSkills.has(skill.name)}
                                onToggle={() => handleToggleSkill(skill)}
                                noDescriptionLabel={t.skills.noDescription}
                              />
                            ))}
                          {activeSkills.filter((s) => s.enabled).length === 0 && (
                            <p className="text-xs text-muted-foreground py-4 text-center">
                              {t.common.none}
                            </p>
                          )}
                        </div>
                      </div>
                      <div>
                        <div className="flex items-center justify-between pb-2">
                          <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                            {t.common.inactive}
                          </span>
                          <Badge variant="outline" className="text-[10px]">
                            {activeSkills.filter((s) => !s.enabled).length}
                          </Badge>
                        </div>
                        <div className="grid gap-1">
                          {activeSkills
                            .filter((s) => !s.enabled)
                            .map((skill) => (
                              <SkillRow
                                key={skill.name}
                                skill={skill}
                                toggling={togglingSkills.has(skill.name)}
                                onToggle={() => handleToggleSkill(skill)}
                                noDescriptionLabel={t.skills.noDescription}
                              />
                            ))}
                          {activeSkills.filter((s) => !s.enabled).length === 0 && (
                            <p className="text-xs text-muted-foreground py-4 text-center">
                              {t.common.none}
                            </p>
                          )}
                        </div>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : view === "hub" ? (
            <div className="flex flex-col gap-3">
              <ConfirmDialog
                open={confirmInstall !== null}
                onCancel={() => setConfirmInstall(null)}
                onConfirm={() => {
                  if (!confirmInstall) return;
                  void handleInstallHub(confirmInstall, true);
                  setConfirmInstall(null);
                }}
                title="Install skill?"
                description="This skill requires confirmation based on its security scan. Confirm to proceed."
                confirmLabel={t.common.confirm}
                cancelLabel={t.common.cancel}
              />

              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Select value={hubSource} onValueChange={(v) => setHubSource(v)}>
                    <SelectOption value="all">all</SelectOption>
                    <SelectOption value="official">official</SelectOption>
                    <SelectOption value="skills-sh">skills.sh</SelectOption>
                    <SelectOption value="well-known">well-known</SelectOption>
                    <SelectOption value="github">github</SelectOption>
                  </Select>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 text-xs gap-1.5"
                    onClick={() => window.open("https://agentskills.io", "_blank", "noopener,noreferrer")}
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                    SkillHub
                  </Button>
                </div>

                <div className="flex items-center gap-1">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 w-8 p-0"
                    disabled={hubLoading || hubPage <= 1}
                    onClick={() => setHubPage((p) => Math.max(1, p - 1))}
                    aria-label="Previous"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 w-8 p-0"
                    disabled={hubLoading || (hub ? hubPage >= hub.total_pages : true)}
                    onClick={() => setHubPage((p) => p + 1)}
                    aria-label="Next"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>

              <Card>
                <CardHeader className="py-3 px-4">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Download className="h-4 w-4" />
                      Skills Hub
                    </CardTitle>
                    {hubLoading && (
                      <div className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                    )}
                  </div>
                </CardHeader>
                <CardContent className="px-4 pb-4">
                  {!hub || hub.items.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      {t.common.noResults}
                    </p>
                  ) : (
                    <div className="grid gap-2">
                      {hub.items
                        .filter((it) => {
                          if (!search.trim()) return true;
                          const q = search.trim().toLowerCase();
                          return (
                            it.name.toLowerCase().includes(q) ||
                            it.description.toLowerCase().includes(q) ||
                            it.identifier.toLowerCase().includes(q)
                          );
                        })
                        .map((it) => {
                          const isInstalled = installedSkillNames.has(it.name);
                          const isHubInstalled = hubInstalledNames.has(it.name);
                          const busy = installing === it.identifier || installing === it.name;
                          return (
                            <div key={it.identifier} className="border border-border p-3">
                              <div className="flex items-start justify-between gap-2">
                                <div className="min-w-0">
                                  <div className="flex items-center gap-2">
                                    <span className="font-mono-ui text-sm">{it.name}</span>
                                    <Badge variant="secondary" className="text-[10px]">
                                      {it.source}
                                    </Badge>
                                    <Badge variant="outline" className="text-[10px]">
                                      {it.trust}
                                    </Badge>
                                    {isInstalled && (
                                      <Badge variant="success" className="text-[10px]">
                                        {t.common.installed}
                                      </Badge>
                                    )}
                                  </div>
                                  <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                    {it.description}
                                  </p>
                                  <p className="text-[10px] text-muted-foreground/60 mt-1 font-mono-ui break-all">
                                    {it.identifier}
                                  </p>
                                </div>
                                <div className="shrink-0 flex flex-col gap-2">
                                  {!isInstalled && (
                                    <Button
                                      type="button"
                                      size="sm"
                                      disabled={busy}
                                      onClick={() => void handleInstallHub(it, false)}
                                      className="h-8 text-xs"
                                    >
                                      {busy ? "…" : "Install"}
                                    </Button>
                                  )}
                                  {isHubInstalled && (
                                    <Button
                                      type="button"
                                      size="sm"
                                      variant="destructive"
                                      disabled={busy}
                                      onClick={() => void handleUninstallHub(it.name)}
                                      className="h-8 text-xs"
                                    >
                                      {busy ? "…" : t.common.delete}
                                    </Button>
                                  )}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : (
            /* Toolsets grid */
            <>
              {filteredToolsets.length === 0 ? (
                <Card>
                  <CardContent className="py-8 text-center text-sm text-muted-foreground">
                    {t.skills.noToolsetsMatch}
                  </CardContent>
                </Card>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {filteredToolsets.map((ts) => {
                    const TsIcon = toolsetIcon(ts.name);
                    const labelText =
                      ts.label.replace(/^[\p{Emoji}\s]+/u, "").trim() ||
                      ts.name;

                    return (
                      <Card key={ts.name} className="relative">
                        <CardContent className="py-4">
                          <div className="flex items-start gap-3">
                            <TsIcon className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1">
                                <span className="font-medium text-sm">
                                  {labelText}
                                </span>
                                <Badge
                                  variant={ts.enabled ? "success" : "outline"}
                                  className="text-[10px]"
                                >
                                  {ts.enabled
                                    ? t.common.active
                                    : t.common.inactive}
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground mb-2">
                                {ts.description}
                              </p>
                              {ts.enabled && !ts.configured && (
                                <p className="text-[10px] text-amber-300/80 mb-2">
                                  {t.skills.setupNeeded}
                                </p>
                              )}
                              {ts.tools.length > 0 && (
                                <div className="flex flex-wrap gap-1">
                                  {ts.tools.map((tool) => (
                                    <Badge
                                      key={tool}
                                      variant="secondary"
                                      className="text-[10px] font-mono"
                                    >
                                      {tool}
                                    </Badge>
                                  ))}
                                </div>
                              )}
                              {ts.tools.length === 0 && (
                                <span className="text-[10px] text-muted-foreground/60">
                                  {ts.enabled
                                    ? t.skills.toolsetLabel.replace(
                                        "{name}",
                                        ts.name,
                                      )
                                    : t.skills.disabledForCli}
                                </span>
                              )}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </div>
      <PluginSlot name="skills:bottom" />
    </div>
  );
}

function SkillRow({
  skill,
  toggling,
  onToggle,
  noDescriptionLabel,
}: SkillRowProps) {
  return (
    <div className="group flex items-start gap-3 px-3 py-2.5 transition-colors hover:bg-muted/40">
      <div className="pt-0.5 shrink-0">
        <Switch
          checked={skill.enabled}
          onCheckedChange={onToggle}
          disabled={toggling}
        />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span
            className={`font-mono-ui text-sm ${
              skill.enabled ? "text-foreground" : "text-muted-foreground"
            }`}
          >
            {skill.name}
          </span>
        </div>
        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
          {skill.description || noDescriptionLabel}
        </p>
      </div>
    </div>
  );
}

function PanelItem({ active, icon: Icon, label, onClick }: PanelItemProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        group flex items-center gap-2 px-2.5 py-1.5
        font-mondwest text-[0.7rem] tracking-[0.08em] uppercase
        rounded-sm text-left cursor-pointer whitespace-nowrap
        transition-colors
        ${
          active
            ? "bg-foreground/90 text-background"
            : "text-muted-foreground hover:text-foreground hover:bg-foreground/10"
        }
      `}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span className="flex-1 truncate">{label}</span>
    </button>
  );
}

interface PanelItemProps {
  active: boolean;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onClick: () => void;
}

interface SkillRowProps {
  noDescriptionLabel: string;
  onToggle: () => void;
  skill: SkillInfo;
  toggling: boolean;
}
