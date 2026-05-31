import { useEffect, useLayoutEffect, useRef, useState, useMemo } from "react";
import {
  Code,
  Download,
  FormInput,
  Plus,
  RotateCcw,
  Search,
  Trash2,
  Upload,
  X,
  Settings2,
  FileText,
  Settings,
  Bot,
  Monitor,
  Palette,
  Users,
  Brain,
  Package,
  Lock,
  Globe,
  Mic,
  Volume2,
  Ear,
  ClipboardList,
  MessageCircle,
  Wrench,
  FileQuestion,
  Filter,
  Cloud,
  Sparkles,
  LayoutDashboard,
  BookOpen,
  Route,
  History,
  Shield,
  FileOutput,
  RefreshCw,
} from "lucide-react";
import {
  api,
  type FallbackProviderConfig,
  type ModelRouteConfig,
  type ModelRoutingResponse,
} from "@/lib/api";
import { getNestedValue, setNestedValue } from "@/lib/nested";
import { useToast } from "@nous-research/ui/hooks/use-toast";
import { Toast } from "@nous-research/ui/ui/components/toast";
import { AutoField } from "@/components/AutoField";
import { Button } from "@nous-research/ui/ui/components/button";
import { ListItem } from "@nous-research/ui/ui/components/list-item";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import { Card, CardContent, CardHeader, CardTitle } from "@nous-research/ui/ui/components/card";
import { ConfirmDialog } from "@nous-research/ui/ui/components/confirm-dialog";
import { Input } from "@nous-research/ui/ui/components/input";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";
import { PluginSlot } from "@/plugins";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const CATEGORY_ICONS: Record<
  string,
  React.ComponentType<{ className?: string }>
> = {
  general: Settings,
  agent: Bot,
  terminal: Monitor,
  display: Palette,
  delegation: Users,
  memory: Brain,
  compression: Package,
  security: Lock,
  browser: Globe,
  voice: Mic,
  tts: Volume2,
  stt: Ear,
  logging: ClipboardList,
  discord: MessageCircle,
  auxiliary: Wrench,
  bedrock: Cloud,
  curator: Sparkles,
  kanban: LayoutDashboard,
  model_catalog: BookOpen,
  openrouter: Route,
  sessions: History,
  tool_loop_guardrails: Shield,
  tool_output: FileOutput,
  updates: RefreshCw,
};

function CategoryIcon({
  category,
  className,
}: {
  category: string;
  className?: string;
}) {
  const Icon = CATEGORY_ICONS[category] ?? FileQuestion;
  return <Icon className={className ?? "h-4 w-4"} />;
}

const EMPTY_FALLBACK: FallbackProviderConfig = {
  provider: "",
  model: "",
  base_url: "",
  api_mode: "",
  context_length: "",
};

type EditableRoute = ModelRouteConfig & Partial<FallbackProviderConfig>;

function routeNumberValue(value: unknown): string {
  if (value === undefined || value === null) return "";
  return String(value);
}

function updateRouteField(
  route: EditableRoute,
  key: keyof EditableRoute,
  value: string,
): EditableRoute {
  if ((key === "context_length" || key === "max_tokens") && value !== "") {
    const parsed = Number(value);
    return { ...route, [key]: Number.isNaN(parsed) ? value : parsed };
  }
  return { ...route, [key]: value };
}

function ModelRouteFields({
  route,
  onChange,
  modelKey,
}: {
  route: EditableRoute;
  onChange: (route: EditableRoute) => void;
  modelKey: "default" | "model";
}) {
  return (
    <div className="grid gap-2 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.2fr)_minmax(0,1.4fr)_minmax(0,0.8fr)_minmax(0,0.8fr)]">
      <Input
        value={String(route.provider ?? "")}
        onChange={(e) => onChange(updateRouteField(route, "provider", e.target.value))}
        placeholder="provider"
        aria-label="provider"
      />
      <Input
        value={String(route[modelKey] ?? "")}
        onChange={(e) => onChange(updateRouteField(route, modelKey, e.target.value))}
        placeholder="model"
        aria-label="model"
      />
      <Input
        value={String(route.base_url ?? "")}
        onChange={(e) => onChange(updateRouteField(route, "base_url", e.target.value))}
        placeholder="base_url"
        aria-label="base_url"
      />
      <Input
        value={String(route.api_mode ?? "")}
        onChange={(e) => onChange(updateRouteField(route, "api_mode", e.target.value))}
        placeholder="api_mode"
        aria-label="api_mode"
      />
      <Input
        type="number"
        min={0}
        value={routeNumberValue(route.context_length)}
        onChange={(e) => onChange(updateRouteField(route, "context_length", e.target.value))}
        placeholder="context"
        aria-label="context_length"
      />
    </div>
  );
}

function ModelRoutingCard({
  routing,
  saving,
  onChange,
  onSave,
}: {
  routing: ModelRoutingResponse | null;
  saving: boolean;
  onChange: (routing: ModelRoutingResponse) => void;
  onSave: () => void;
}) {
  if (!routing) return null;

  const updateFallback = (index: number, route: EditableRoute) => {
    onChange({
      ...routing,
      fallback_providers: routing.fallback_providers.map((entry, i) =>
        i === index ? (route as FallbackProviderConfig) : entry,
      ),
    });
  };

  const removeFallback = (index: number) => {
    onChange({
      ...routing,
      fallback_providers: routing.fallback_providers.filter((_, i) => i !== index),
    });
  };

  return (
    <Card>
      <CardHeader className="py-3 px-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-sm flex items-center gap-2">
            <Route className="h-4 w-4" />
            Model routing
          </CardTitle>
          <Button
            size="sm"
            className="uppercase"
            onClick={onSave}
            disabled={saving}
            prefix={saving ? <Spinner /> : <Route />}
          >
            {saving ? "Saving" : "Save routing"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="grid gap-4 px-4 pb-4">
        <div className="grid gap-2">
          <div className="text-xs font-medium uppercase text-muted-foreground">
            Main model
          </div>
          <ModelRouteFields
            route={routing.model as EditableRoute}
            modelKey="default"
            onChange={(route) =>
              onChange({ ...routing, model: route as ModelRouteConfig })
            }
          />
        </div>

        <div className="grid gap-2">
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs font-medium uppercase text-muted-foreground">
              Fallback providers
            </div>
            <Button
              ghost
              size="sm"
              prefix={<Plus />}
              onClick={() =>
                onChange({
                  ...routing,
                  fallback_providers: [
                    ...routing.fallback_providers,
                    { ...EMPTY_FALLBACK },
                  ],
                })
              }
            >
              Add fallback
            </Button>
          </div>
          <div className="grid gap-2">
            {routing.fallback_providers.length === 0 ? (
              <div className="border border-dashed border-border px-3 py-4 text-sm text-muted-foreground">
                No fallback providers configured.
              </div>
            ) : (
              routing.fallback_providers.map((fallback, index) => (
                <div
                  key={index}
                  className="grid gap-2 border border-border bg-muted/20 p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-mono text-muted-foreground">
                      fallback_providers[{index}]
                    </span>
                    <Button
                      ghost
                      size="icon"
                      onClick={() => removeFallback(index)}
                      title="Remove fallback"
                      aria-label="Remove fallback"
                    >
                      <Trash2 />
                    </Button>
                  </div>
                  <ModelRouteFields
                    route={fallback as EditableRoute}
                    modelKey="model"
                    onChange={(route) => updateFallback(index, route)}
                  />
                </div>
              ))
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function ConfigPage() {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [schema, setSchema] = useState<Record<
    string,
    Record<string, unknown>
  > | null>(null);
  const [categoryOrder, setCategoryOrder] = useState<string[]>([]);
  const [defaults, setDefaults] = useState<Record<string, unknown> | null>(
    null,
  );
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [yamlMode, setYamlMode] = useState(false);
  const [yamlText, setYamlText] = useState("");
  const [yamlLoading, setYamlLoading] = useState(false);
  const [yamlSaving, setYamlSaving] = useState(false);
  const [configPath, setConfigPath] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string>("");
  const [confirmReset, setConfirmReset] = useState(false);
  const [modelRouting, setModelRouting] = useState<ModelRoutingResponse | null>(null);
  const [routingSaving, setRoutingSaving] = useState(false);
  const { toast, showToast } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { t } = useI18n();
  const { setEnd } = usePageHeader();

  useLayoutEffect(() => {
    if (!config || !schema) {
      setEnd(null);
      return;
    }
    setEnd(
      <div className="relative w-full min-w-0 sm:max-w-xs">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          className="h-8 pl-8 pr-7 text-xs"
          placeholder={t.common.search}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        {searchQuery && (
          <Button
            ghost
            size="xs"
            className="absolute right-1.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            onClick={() => setSearchQuery("")}
            aria-label={t.common.clear}
          >
            <X />
          </Button>
        )}
      </div>,
    );
    return () => setEnd(null);
  }, [config, schema, searchQuery, setEnd, t.common.clear, t.common.search]);

  function prettyCategoryName(cat: string): string {
    const key = cat as keyof typeof t.config.categories;
    if (t.config.categories[key]) return t.config.categories[key];
    return cat.charAt(0).toUpperCase() + cat.slice(1);
  }

  useEffect(() => {
    api
      .getConfig()
      .then(setConfig)
      .catch(() => {});
    api
      .getSchema()
      .then((resp) => {
        setSchema(resp.fields as Record<string, Record<string, unknown>>);
        setCategoryOrder(resp.category_order ?? []);
      })
      .catch(() => {});
    api
      .getDefaults()
      .then(setDefaults)
      .catch(() => {});
    api
      .getStatus()
      .then((resp) => setConfigPath(resp.config_path))
      .catch(() => {});
    api
      .getModelRouting()
      .then(setModelRouting)
      .catch(() => {});
  }, []);

  // Set active category when categories load
  useEffect(() => {
    if (categoryOrder.length > 0 && !activeCategory) {
      setActiveCategory(categoryOrder[0]);
    }
  }, [categoryOrder, activeCategory]);

  // Load YAML when switching to YAML mode
  useEffect(() => {
    if (yamlMode) {
      setYamlLoading(true);
      api
        .getConfigRaw()
        .then((resp) => setYamlText(resp.yaml))
        .catch(() => showToast(t.config.failedToLoadRaw, "error"))
        .finally(() => setYamlLoading(false));
    }
  }, [yamlMode]);

  /* ---- Categories ---- */
  const categories = useMemo(() => {
    if (!schema) return [];
    const allCats = [
      ...new Set(
        Object.values(schema).map((s) => String(s.category ?? "general")),
      ),
    ];
    const ordered = categoryOrder.filter((c) => allCats.includes(c));
    const extra = allCats.filter((c) => !categoryOrder.includes(c)).sort();
    return [...ordered, ...extra];
  }, [schema, categoryOrder]);

  /* ---- Category field counts ---- */
  const categoryCounts = useMemo(() => {
    if (!schema) return {};
    const counts: Record<string, number> = {};
    for (const s of Object.values(schema)) {
      const cat = String(s.category ?? "general");
      counts[cat] = (counts[cat] || 0) + 1;
    }
    return counts;
  }, [schema]);

  /* ---- Search ---- */
  const isSearching = searchQuery.trim().length > 0;
  const lowerSearch = searchQuery.toLowerCase();

  const searchMatchedFields = useMemo(() => {
    if (!isSearching || !schema) return [];
    return Object.entries(schema).filter(([key, s]) => {
      const label = key.split(".").pop() ?? key;
      const humanLabel = label.replace(/_/g, " ");
      return (
        key.toLowerCase().includes(lowerSearch) ||
        humanLabel.toLowerCase().includes(lowerSearch) ||
        String(s.category ?? "")
          .toLowerCase()
          .includes(lowerSearch) ||
        String(s.description ?? "")
          .toLowerCase()
          .includes(lowerSearch)
      );
    });
  }, [isSearching, lowerSearch, schema]);

  /* ---- Active tab fields ---- */
  const activeFields = useMemo(() => {
    if (!schema || isSearching) return [];
    return Object.entries(schema).filter(
      ([, s]) => String(s.category ?? "general") === activeCategory,
    );
  }, [schema, activeCategory, isSearching]);

  /* ---- Handlers ---- */
  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      await api.saveConfig(config);
      showToast(t.config.configSaved, "success");
    } catch (e) {
      showToast(`${t.config.failedToSave}: ${e}`, "error");
    } finally {
      setSaving(false);
    }
  };

  const handleRoutingSave = async () => {
    if (!modelRouting) return;
    setRoutingSaving(true);
    try {
      await api.saveModelRouting(modelRouting);
      const [nextConfig, nextRouting] = await Promise.all([
        api.getConfig(),
        api.getModelRouting(),
      ]);
      setConfig(nextConfig);
      setModelRouting(nextRouting);
      showToast("Model routing saved", "success");
    } catch (e) {
      showToast(`Failed to save model routing: ${e}`, "error");
    } finally {
      setRoutingSaving(false);
    }
  };

  const handleYamlSave = async () => {
    setYamlSaving(true);
    try {
      await api.saveConfigRaw(yamlText);
      showToast(t.config.yamlConfigSaved, "success");
      const [nextConfig, nextRouting] = await Promise.all([
        api.getConfig(),
        api.getModelRouting(),
      ]);
      setConfig(nextConfig);
      setModelRouting(nextRouting);
    } catch (e) {
      showToast(`${t.config.failedToSaveYaml}: ${e}`, "error");
    } finally {
      setYamlSaving(false);
    }
  };

  const handleReset = () => {
    if (!defaults || !config) return;
    // Scope the reset to what the user is currently looking at:
    //   - search mode → the matched fields
    //   - form mode   → the active category's fields
    // Resetting the whole config here was a footgun (issue reported by @ykmfb001):
    // the button sits next to the category tabs and users reasonably assumed
    // "reset this tab", not "wipe my entire config.yaml".
    const scopedFields = isSearching ? searchMatchedFields : activeFields;
    if (scopedFields.length === 0) return;
    setConfirmReset(true);
  };

  const executeReset = () => {
    if (!defaults || !config) return;
    setConfirmReset(false);
    const scopedFields = isSearching ? searchMatchedFields : activeFields;
    if (scopedFields.length === 0) return;
    const scopeLabel = isSearching
      ? t.config.searchResults
      : prettyCategoryName(activeCategory);
    let next: Record<string, unknown> = config;
    for (const [key] of scopedFields) {
      next = setNestedValue(next, key, getNestedValue(defaults, key));
    }
    setConfig(next);
    showToast(
      t.config.resetScopeToast.replace("{scope}", scopeLabel),
      "success",
    );
  };

  const handleExport = () => {
    if (!config) return;
    const blob = new Blob([JSON.stringify(config, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "hermes-config.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const imported = JSON.parse(reader.result as string);
        setConfig(imported);
        showToast(t.config.configImported, "success");
      } catch {
        showToast(t.config.invalidJson, "error");
      }
    };
    reader.readAsText(file);
  };

  /* ---- Loading ---- */
  if (!config || !schema) {
    return (
      <div className="flex items-center justify-center py-24">
        <Spinner className="text-2xl text-primary" />
      </div>
    );
  }

  /* ---- Render field list (shared between search & normal) ---- */
  const renderFields = (
    fields: [string, Record<string, unknown>][],
    showCategory = false,
  ) => {
    let lastSection = "";
    let lastCat = "";
    return fields.map(([key, s]) => {
      const parts = key.split(".");
      const section = parts.length > 1 ? parts[0] : "";
      const cat = String(s.category ?? "general");
      const showCatBadge = showCategory && cat !== lastCat;
      const showSection =
        !showCategory &&
        section &&
        section !== lastSection &&
        section !== activeCategory;
      lastSection = section;
      lastCat = cat;

      return (
        <div key={key}>
          {showCatBadge && (
            <div className="flex items-center gap-2 pt-4 pb-2 first:pt-0">
              <CategoryIcon
                category={cat}
                className="h-4 w-4 text-muted-foreground"
              />
              <span className="font-mondwest text-display text-xs font-semibold tracking-wider text-muted-foreground">
                {prettyCategoryName(cat)}
              </span>
              <div className="flex-1 border-t border-border" />
            </div>
          )}
          {showSection && (
            <div className="flex items-center gap-2 pt-4 pb-2 first:pt-0">
              <span className="font-mondwest text-display text-xs font-semibold tracking-wider text-muted-foreground">
                {section.replace(/_/g, " ")}
              </span>
              <div className="flex-1 border-t border-border" />
            </div>
          )}
          <div className="py-1">
            <AutoField
              schemaKey={key}
              schema={s}
              value={getNestedValue(config, key)}
              onChange={(v) => setConfig(setNestedValue(config, key, v))}
            />
          </div>
        </div>
      );
    });
  };

  return (
    <div className="flex flex-col gap-4">
      <PluginSlot name="config:top" />
      <Toast toast={toast} />

      <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
        <div className="flex min-w-0 items-center gap-2 sm:flex-1">
          <Settings2 className="h-4 w-4 shrink-0 text-muted-foreground" />
          <code className="min-w-0 flex-1 break-words text-xs text-muted-foreground bg-muted/50 px-2 py-0.5">
            {configPath ?? t.config.configPath}
          </code>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 sm:shrink-0">
          <Button
            ghost
            size="icon"
            onClick={handleExport}
            title={t.config.exportConfig}
            aria-label={t.config.exportConfig}
          >
            <Download />
          </Button>
          <Button
            ghost
            size="icon"
            onClick={() => fileInputRef.current?.click()}
            title={t.config.importConfig}
            aria-label={t.config.importConfig}
          >
            <Upload />
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            className="hidden"
            onChange={handleImport}
          />
          {!yamlMode &&
            (() => {
              const resetScopeLabel = isSearching
                ? t.config.searchResults
                : prettyCategoryName(activeCategory);
              const resetTitle = t.config.resetScopeTooltip.replace(
                "{scope}",
                resetScopeLabel,
              );
              return (
                <Button
                  ghost
                  size="icon"
                  onClick={handleReset}
                  title={resetTitle}
                  aria-label={resetTitle}
                >
                  <RotateCcw />
                </Button>
              );
            })()}

          <div className="w-px h-5 bg-border mx-1" />

          <Button
            size="sm"
            outlined={!yamlMode}
            onClick={() => setYamlMode(!yamlMode)}
            prefix={yamlMode ? <FormInput /> : <Code />}
          >
            {yamlMode ? t.common.form : "YAML"}
          </Button>

          {yamlMode ? (
            <Button
              size="sm"
              className="uppercase"
              onClick={handleYamlSave}
              disabled={yamlSaving}
            >
              {yamlSaving ? t.common.saving : t.common.save}
            </Button>
          ) : (
            <Button
              size="sm"
              className="uppercase"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? t.common.saving : t.common.save}
            </Button>
          )}
        </div>
      </div>

      {yamlMode ? (
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <FileText className="h-4 w-4" />
              {t.config.rawYaml}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {yamlLoading ? (
              <div className="flex items-center justify-center py-12">
                <Spinner className="text-xl text-primary" />
              </div>
            ) : (
              <textarea
                className="flex min-h-[600px] w-full bg-transparent px-4 py-3 text-sm font-mono leading-relaxed placeholder:text-muted-foreground focus-visible:outline-none border-t border-border"
                value={yamlText}
                onChange={(e) => setYamlText(e.target.value)}
                spellCheck={false}
              />
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col sm:flex-row gap-4">
          <aside aria-label={t.config.filters} className="sm:w-56 sm:shrink-0">
            <div className="sm:sticky sm:top-4">
              <div className="flex flex-col border border-border bg-muted/20">
                <div className="hidden sm:flex items-center gap-2 px-3 py-2 border-b border-border">
                  <Filter className="h-3 w-3 text-text-tertiary" />
                  <span className="font-mondwest text-display text-xs tracking-[0.12em] text-text-secondary">
                    {t.config.filters}
                  </span>
                </div>

                <div className="hidden sm:block px-3 pt-2 pb-1 font-mondwest text-display text-xs tracking-[0.12em] text-text-tertiary">
                  {t.config.sections}
                </div>

                <div className="flex sm:flex-col gap-1 sm:gap-px p-2 sm:pt-1 overflow-x-auto sm:overflow-x-visible scrollbar-none sm:max-h-[calc(100vh-260px)] sm:overflow-y-auto">
                  {categories.map((cat) => {
                    const isActive = !isSearching && activeCategory === cat;

                    return (
                      <ListItem
                        key={cat}
                        active={isActive}
                        onClick={() => {
                          setSearchQuery("");
                          setActiveCategory(cat);
                        }}
                        className="rounded-none whitespace-nowrap px-2 py-1 text-xs"
                      >
                        <CategoryIcon
                          category={cat}
                          className="h-3.5 w-3.5 shrink-0"
                        />
                        <span className="flex-1 truncate">
                          {prettyCategoryName(cat)}
                        </span>
                        <span
                          className={`text-xs tabular-nums ${
                            isActive
                              ? "text-text-secondary"
                              : "text-text-tertiary"
                          }`}
                        >
                          {categoryCounts[cat] || 0}
                        </span>
                      </ListItem>
                    );
                  })}
                </div>
              </div>
            </div>
          </aside>

          <div className="flex-1 min-w-0 grid gap-4">
            {!isSearching && (
              <ModelRoutingCard
                routing={modelRouting}
                saving={routingSaving}
                onChange={setModelRouting}
                onSave={handleRoutingSave}
              />
            )}
            {isSearching ? (
              <Card>
                <CardHeader className="py-3 px-4">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Search className="h-4 w-4" />
                      {t.config.searchResults}
                    </CardTitle>
                    <Badge tone="secondary" className="text-xs">
                      {searchMatchedFields.length}{" "}
                      {t.config.fields.replace(
                        "{s}",
                        searchMatchedFields.length !== 1 ? "s" : "",
                      )}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="grid gap-2 px-4 pb-4">
                  {searchMatchedFields.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      {t.config.noFieldsMatch.replace("{query}", searchQuery)}
                    </p>
                  ) : (
                    renderFields(searchMatchedFields, true)
                  )}
                </CardContent>
              </Card>
            ) : (
              /* Active category */
              <Card>
                <CardHeader className="py-3 px-4">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <CategoryIcon
                        category={activeCategory}
                        className="h-4 w-4"
                      />
                      {prettyCategoryName(activeCategory)}
                    </CardTitle>
                    <Badge tone="secondary" className="text-xs">
                      {activeFields.length}{" "}
                      {t.config.fields.replace(
                        "{s}",
                        activeFields.length !== 1 ? "s" : "",
                      )}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent className="grid gap-2 px-4 pb-4">
                  {renderFields(activeFields)}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
      <PluginSlot name="config:bottom" />
      <ConfirmDialog
        open={confirmReset}
        onCancel={() => setConfirmReset(false)}
        onConfirm={executeReset}
        title={t.config.confirmResetScope.replace(
          "{scope}",
          isSearching
            ? t.config.searchResults
            : prettyCategoryName(activeCategory),
        )}
        description={`This will reset ${
          (isSearching ? searchMatchedFields : activeFields).length
        } field(s) to their default values.`}
        destructive
        confirmLabel={t.config.resetDefaults}
      />
    </div>
  );
}
