import { Fragment, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Copy,
  Pencil,
  Plus,
  Terminal,
  Trash2,
  Users,
  X,
  XCircle,
} from "lucide-react";
import { H2 } from "@/components/NouiTypography";
import { api } from "@/lib/api";
import type { ProfileInfo } from "@/lib/api";
import { cn } from "@/lib/utils";
import { DeleteConfirmDialog } from "@/components/DeleteConfirmDialog";
import { useToast } from "@/hooks/useToast";
import { useConfirmDelete } from "@/hooks/useConfirmDelete";
import { useModalBehavior } from "@/hooks/useModalBehavior";
import { Toast } from "@/components/Toast";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { useI18n } from "@/i18n";
import { usePageHeader } from "@/contexts/usePageHeader";

// Mirrors hermes_cli/profiles.py::_PROFILE_ID_RE so we can reject obviously
// invalid names (uppercase, spaces, …) before round-tripping a doomed POST.
const PROFILE_NAME_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/;
const EXPECTED_RUNTIME = {
  model: "gpt-5.5",
  provider: "openai-codex",
  reasoning: "high",
} as const;

type DriftItem = {
  key: "model" | "provider" | "reasoning";
  current: string;
  expected: string;
};

const emptyValue = "-";

function normalizeRuntimeValue(value: string | null | undefined): string {
  return (value ?? "").trim().toLowerCase();
}

function displayRuntimeValue(value: string | null | undefined): string {
  const trimmed = (value ?? "").trim();
  return trimmed || emptyValue;
}

function hasOpusModel(profile: ProfileInfo): boolean {
  return normalizeRuntimeValue(profile.model).includes("opus");
}

function usesAnthropicProvider(profile: ProfileInfo): boolean {
  return normalizeRuntimeValue(profile.provider).includes("anthropic");
}

function usesGlobalAuthFallback(profile: ProfileInfo): boolean {
  return (profile.auth_sources || []).some((source) =>
    source.toLowerCase().includes("global auth.json"),
  );
}

function getRuntimeDrift(profile: ProfileInfo): DriftItem[] {
  const checks: DriftItem[] = [];
  if (normalizeRuntimeValue(profile.model) !== EXPECTED_RUNTIME.model) {
    checks.push({
      key: "model",
      current: displayRuntimeValue(profile.model),
      expected: EXPECTED_RUNTIME.model,
    });
  }
  if (normalizeRuntimeValue(profile.provider) !== EXPECTED_RUNTIME.provider) {
    checks.push({
      key: "provider",
      current: displayRuntimeValue(profile.provider),
      expected: EXPECTED_RUNTIME.provider,
    });
  }
  if (normalizeRuntimeValue(profile.reasoning_effort) !== EXPECTED_RUNTIME.reasoning) {
    checks.push({
      key: "reasoning",
      current: displayRuntimeValue(profile.reasoning_effort),
      expected: EXPECTED_RUNTIME.reasoning,
    });
  }
  return checks;
}

function getProfileSeverity(profile: ProfileInfo): "critical" | "warning" | "ok" {
  if (hasOpusModel(profile) || usesAnthropicProvider(profile)) return "critical";
  if (usesGlobalAuthFallback(profile) || getRuntimeDrift(profile).length > 0) return "warning";
  return "ok";
}

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<ProfileInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast, showToast } = useToast();
  const { t, locale } = useI18n();
  const { setEnd } = usePageHeader();
  const profileLabels =
    locale === "ja"
      ? {
          actions: "操作",
          auth: "認証",
          authSource: "認証元",
          authKinds: {
            api_key: "API key",
            aws_sdk: "AWS SDK",
            external_process: "External process",
            mixed: "OAuth + API key",
            oauth: "OAuth",
          },
          closeDetails: "詳細を閉じる",
          config: "設定",
          copy: "コピー",
          copyConfigPath: "config pathをコピー",
          copyEnvPath: "env pathをコピー",
          copyProfilePath: "profile pathをコピー",
          critical: "要修正",
          details: "詳細",
          drift: "期待値との差分",
          env: "Env",
          expected: "期待値",
          expectedRuntime: "GPT-5.5 + openai-codex + high",
          gateway: "Gateway",
          globalFallback: "global auth.json fallback",
          harness: "ハーネス",
          inherit: "継承",
          model: "モデル",
          noDrift: "期待値通り",
          notConfigured: "未設定",
          ok: "OK",
          path: "Profile path",
          profile: "Profile",
          provider: "Provider",
          reasoning: "推論",
          running: "稼働中",
          settings: "設定 / 参照",
          source: "Source",
          status: "状態",
          stopped: "停止",
          subagents: "Subagents",
          warning: "注意",
        }
      : {
          actions: "Actions",
          auth: "Auth",
          authSource: "Auth source",
          authKinds: {
            api_key: "API key",
            aws_sdk: "AWS SDK",
            external_process: "External process",
            mixed: "OAuth + API key",
            oauth: "OAuth",
          },
          closeDetails: "Close details",
          config: "Config",
          copy: "Copy",
          copyConfigPath: "Copy config path",
          copyEnvPath: "Copy env path",
          copyProfilePath: "Copy profile path",
          critical: "Fix",
          details: "Details",
          drift: "Expected drift",
          env: "Env",
          expected: "Expected",
          expectedRuntime: "GPT-5.5 + openai-codex + high",
          gateway: "Gateway",
          globalFallback: "global auth.json fallback",
          harness: "Harness",
          inherit: "inherit",
          model: "Model",
          noDrift: "matches expected",
          notConfigured: "not configured",
          ok: "OK",
          path: "Profile path",
          profile: "Profile",
          provider: "Provider",
          reasoning: "Reasoning",
          running: "running",
          settings: "Settings / reference",
          source: "Source",
          status: "Status",
          stopped: "stopped",
          subagents: "Subagents",
          warning: "Warning",
        };
  const formatAuthKind = (kind: string | null | undefined) =>
    kind ? profileLabels.authKinds[kind as keyof typeof profileLabels.authKinds] || kind : profileLabels.notConfigured;

  // Create modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [cloneFromDefault, setCloneFromDefault] = useState(true);
  const [creating, setCreating] = useState(false);
  const closeCreateModal = useCallback(() => setCreateModalOpen(false), []);
  const createModalRef = useModalBehavior({
    open: createModalOpen,
    onClose: closeCreateModal,
  });

  // Inline rename state
  const [renamingFrom, setRenamingFrom] = useState<string | null>(null);
  const [renameTo, setRenameTo] = useState("");
  const [expandedProfile, setExpandedProfile] = useState<string | null>(null);

  // Inline SOUL editor state
  const [editingSoulFor, setEditingSoulFor] = useState<string | null>(null);
  const [soulText, setSoulText] = useState("");
  const [soulSaving, setSoulSaving] = useState(false);
  // Tracks the latest SOUL request so out-of-order responses don't overwrite
  // newer state when the user switches profiles or closes the editor.
  const activeSoulRequest = useRef<string | null>(null);

  const load = useCallback(() => {
    api
      .getProfiles()
      .then((res) => setProfiles(res.profiles))
      .catch((e) => showToast(`${t.status.error}: ${e}`, "error"))
      .finally(() => setLoading(false));
  }, [showToast, t.status.error]);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) {
      showToast(t.profiles.nameRequired, "error");
      return;
    }
    if (!PROFILE_NAME_RE.test(name)) {
      showToast(`${t.profiles.invalidName}: ${t.profiles.nameRule}`, "error");
      return;
    }
    setCreating(true);
    try {
      await api.createProfile({ name, clone_from_default: cloneFromDefault });
      showToast(`${t.profiles.created}: ${name}`, "success");
      setNewName("");
      setCreateModalOpen(false);
      load();
    } catch (e) {
      showToast(`${t.status.error}: ${e}`, "error");
    } finally {
      setCreating(false);
    }
  };

  const handleRenameSubmit = async () => {
    if (!renamingFrom) return;
    const target = renameTo.trim();
    if (!target || target === renamingFrom) {
      setRenamingFrom(null);
      setRenameTo("");
      return;
    }
    if (!PROFILE_NAME_RE.test(target)) {
      showToast(`${t.profiles.invalidName}: ${t.profiles.nameRule}`, "error");
      return;
    }
    try {
      await api.renameProfile(renamingFrom, target);
      showToast(`${t.profiles.renamed}: ${renamingFrom} → ${target}`, "success");
      setRenamingFrom(null);
      setRenameTo("");
      load();
    } catch (e) {
      showToast(`${t.status.error}: ${e}`, "error");
    }
  };

  const openSoulEditor = useCallback(
    async (name: string) => {
      if (editingSoulFor === name) {
        activeSoulRequest.current = null;
        setEditingSoulFor(null);
        return;
      }
      setExpandedProfile(name);
      setEditingSoulFor(name);
      setSoulText("");
      activeSoulRequest.current = name;
      try {
        const soul = await api.getProfileSoul(name);
        if (activeSoulRequest.current === name) {
          setSoulText(soul.content);
        }
      } catch (e) {
        if (activeSoulRequest.current === name) {
          showToast(`${t.status.error}: ${e}`, "error");
        }
      }
    },
    [editingSoulFor, showToast, t.status.error],
  );

  const copyText = useCallback(
    async (label: string, value: string | null | undefined) => {
      if (!value) return;
      try {
        await navigator.clipboard.writeText(value);
        showToast(`${label}: ${value}`, "success");
      } catch {
        showToast(`${t.profiles.copyFailed}: ${value}`, "error");
      }
    },
    [showToast, t.profiles.copyFailed],
  );

  const handleSaveSoul = async (name: string) => {
    setSoulSaving(true);
    try {
      await api.updateProfileSoul(name, soulText);
      showToast(`${t.profiles.soulSaved}: ${name}`, "success");
    } catch (e) {
      showToast(`${t.status.error}: ${e}`, "error");
    } finally {
      setSoulSaving(false);
    }
  };

  const handleCopyTerminalCommand = async (name: string) => {
    let cmd: string;
    try {
      const res = await api.getProfileSetupCommand(name);
      cmd = res.command;
    } catch (e) {
      showToast(`${t.status.error}: ${e}`, "error");
      return;
    }
    try {
      await navigator.clipboard.writeText(cmd);
      showToast(`${t.profiles.commandCopied}: ${cmd}`, "success");
    } catch {
      showToast(`${t.profiles.copyFailed}: ${cmd}`, "error");
    }
  };

  const profileDelete = useConfirmDelete<string>({
    onDelete: useCallback(
      async (name: string) => {
        try {
          await api.deleteProfile(name);
          showToast(`${t.profiles.deleted}: ${name}`, "success");
          load();
        } catch (e) {
          showToast(`${t.status.error}: ${e}`, "error");
          throw e;
        }
      },
      [load, showToast, t.profiles.deleted, t.status.error],
    ),
  });

  const pendingName = profileDelete.pendingId;

  // Put "Create" button in page header
  useLayoutEffect(() => {
    setEnd(
      <Button
        size="sm"
        onClick={() => setCreateModalOpen(true)}
      >
        <Plus className="h-3 w-3" />
        {t.common.create}
      </Button>,
    );
    return () => {
      setEnd(null);
    };
  }, [setEnd, t.common.create, loading]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    // Profile names, model slugs, and paths are case-sensitive; opt out of
    // the app shell's global ``uppercase`` so they render as the user typed.
    // Children that explicitly opt back in (Badges, etc.) keep their casing.
    <div className="flex flex-col gap-6 normal-case">
      <Toast toast={toast} />

      <DeleteConfirmDialog
        open={profileDelete.isOpen}
        onCancel={profileDelete.cancel}
        onConfirm={profileDelete.confirm}
        title={t.profiles.confirmDeleteTitle}
        description={
          pendingName
            ? t.profiles.confirmDeleteMessage.replace("{name}", pendingName)
            : t.profiles.confirmDeleteMessage
        }
        loading={profileDelete.isDeleting}
      />

      {/* Create profile modal */}
      {createModalOpen && (
        <div
          ref={createModalRef}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-background/85 backdrop-blur-sm p-4"
          onClick={(e) => e.target === e.currentTarget && setCreateModalOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="create-profile-title"
        >
          <div className="relative w-full max-w-md border border-border bg-card shadow-2xl flex flex-col">
            <Button
              ghost
              size="icon"
              onClick={() => setCreateModalOpen(false)}
              className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
              aria-label="Close"
            >
              <X />
            </Button>

            <header className="p-5 pb-3 border-b border-border">
              <h2
                id="create-profile-title"
                className="font-display text-base tracking-wider uppercase"
              >
                {t.profiles.newProfile}
              </h2>
            </header>

            <div className="p-5 grid gap-4">
              <div className="grid gap-2">
                <Label htmlFor="profile-name">{t.profiles.name}</Label>
                <Input
                  id="profile-name"
                  autoFocus
                  placeholder={t.profiles.namePlaceholder}
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleCreate();
                  }}
                  aria-invalid={
                    newName.trim() !== "" &&
                    !PROFILE_NAME_RE.test(newName.trim())
                  }
                />
                <p className="text-xs text-muted-foreground">
                  {t.profiles.nameRule}
                </p>
              </div>

              <Checkbox
                id="clone-from-default"
                checked={cloneFromDefault}
                onChange={(e) => setCloneFromDefault(e.target.checked)}
                label={t.profiles.cloneFromDefault}
              />

              <div className="flex justify-end">
                <Button size="sm" onClick={handleCreate} disabled={creating}>
                  <Plus className="h-3 w-3" />
                  {creating ? t.common.creating : t.common.create}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* List */}
      <div className="flex flex-col gap-3">
        <H2
          variant="sm"
          className="flex items-center gap-2 text-muted-foreground"
        >
          <Users className="h-4 w-4" />
          {t.profiles.allProfiles} ({profiles.length})
        </H2>

        {profiles.length === 0 && (
          <Card>
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              {t.profiles.noProfiles}
            </CardContent>
          </Card>
        )}

        {profiles.length > 0 && (
          <div className="overflow-x-auto border border-border bg-card/80">
            <table className="w-full min-w-[1120px] text-left text-sm">
              <thead className="border-b border-border bg-muted/20 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-medium">{profileLabels.profile}</th>
                  <th className="px-4 py-3 font-medium">{profileLabels.model}</th>
                  <th className="px-4 py-3 font-medium">{profileLabels.provider}</th>
                  <th className="px-4 py-3 font-medium">{profileLabels.auth}</th>
                  <th className="px-4 py-3 font-medium">{profileLabels.reasoning}</th>
                  <th className="px-4 py-3 font-medium">{profileLabels.gateway}</th>
                  <th className="px-4 py-3 font-medium">{profileLabels.drift}</th>
                  <th className="px-4 py-3 text-right font-medium">{profileLabels.actions}</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((p) => {
                  const isRenaming = renamingFrom === p.name;
                  const isEditingSoul = editingSoulFor === p.name;
                  const isExpanded = expandedProfile === p.name;
                  const drift = getRuntimeDrift(p);
                  const severity = getProfileSeverity(p);
                  const isCritical = severity === "critical";
                  const isWarning = severity === "warning";
                  const globalFallback = usesGlobalAuthFallback(p);
                  const authLabel = p.auth_configured
                    ? formatAuthKind(p.auth_kind)
                    : profileLabels.notConfigured;
                  const authSources = p.auth_sources?.length
                    ? p.auth_sources.join(", ")
                    : profileLabels.notConfigured;
                  const subagentReasoning =
                    p.delegation_reasoning_effort ||
                    (p.reasoning_effort
                      ? `${profileLabels.inherit} (${p.reasoning_effort})`
                      : profileLabels.inherit);
                  const subagentModel = [p.delegation_provider, p.delegation_model]
                    .filter(Boolean)
                    .join(":");
                  const soulPath = `${p.path}/SOUL.md`;

                  return (
                    <Fragment key={p.name}>
                      <tr
                        className={cn(
                          "border-b border-border align-top transition-colors",
                          isExpanded && "bg-muted/10",
                          isCritical && "bg-destructive/10",
                          isWarning && "bg-yellow-500/10",
                        )}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-start gap-2">
                            <Button
                              ghost
                              size="icon"
                              className="h-7 w-7 shrink-0"
                              title={isExpanded ? profileLabels.closeDetails : profileLabels.details}
                              aria-label={isExpanded ? profileLabels.closeDetails : profileLabels.details}
                              onClick={() => setExpandedProfile(isExpanded ? null : p.name)}
                            >
                              {isExpanded ? (
                                <ChevronDown className="h-4 w-4" />
                              ) : (
                                <ChevronRight className="h-4 w-4" />
                              )}
                            </Button>
                            <div className="min-w-0">
                              {isRenaming ? (
                                <Input
                                  autoFocus
                                  value={renameTo}
                                  onChange={(e) => setRenameTo(e.target.value)}
                                  onKeyDown={(e) => {
                                    if (e.key === "Enter") handleRenameSubmit();
                                    if (e.key === "Escape") setRenamingFrom(null);
                                  }}
                                  aria-invalid={
                                    renameTo.trim() !== "" &&
                                    renameTo.trim() !== p.name &&
                                    !PROFILE_NAME_RE.test(renameTo.trim())
                                  }
                                  className="h-8 max-w-[13rem]"
                                />
                              ) : (
                                <div className="flex items-center gap-2">
                                  <span className="truncate font-medium">{p.name}</span>
                                  {severity === "ok" && (
                                    <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
                                  )}
                                  {severity === "warning" && (
                                    <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-yellow-600" />
                                  )}
                                  {severity === "critical" && (
                                    <XCircle className="h-3.5 w-3.5 shrink-0 text-destructive" />
                                  )}
                                </div>
                              )}
                              <div className="mt-1 flex flex-wrap gap-1">
                                {p.is_default && (
                                  <Badge tone="secondary">{t.profiles.defaultBadge}</Badge>
                                )}
                                {p.has_env && <Badge tone="outline">{t.profiles.hasEnv}</Badge>}
                                <Badge tone="outline">{t.profiles.skills}: {p.skill_count}</Badge>
                              </div>
                              {isRenaming &&
                                (() => {
                                  const trimmed = renameTo.trim();
                                  const invalid =
                                    trimmed !== "" &&
                                    trimmed !== p.name &&
                                    !PROFILE_NAME_RE.test(trimmed);
                                  return (
                                    <p
                                      className={cn(
                                        "mt-1 text-xs",
                                        invalid ? "text-destructive" : "text-muted-foreground",
                                      )}
                                    >
                                      {invalid
                                        ? `${t.profiles.invalidName}: ${t.profiles.nameRule}`
                                        : t.profiles.nameRule}
                                    </p>
                                  );
                                })()}
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3 font-mono text-xs">
                          {displayRuntimeValue(p.model)}
                        </td>
                        <td
                          className={cn(
                            "px-4 py-3 font-mono text-xs",
                            usesAnthropicProvider(p) && "font-semibold text-destructive",
                          )}
                        >
                          {displayRuntimeValue(p.provider)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-col gap-1">
                            <span className="text-xs">{authLabel}</span>
                            {globalFallback && (
                              <span className="inline-flex w-fit items-center gap-1 text-xs font-medium text-yellow-700 dark:text-yellow-400">
                                <AlertTriangle className="h-3 w-3" />
                                {profileLabels.globalFallback}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 font-mono text-xs">
                          {displayRuntimeValue(p.reasoning_effort)}
                        </td>
                        <td className="px-4 py-3">
                          <div
                            className={cn(
                              "inline-flex items-center gap-1 text-xs font-medium",
                              p.gateway_running ? "text-emerald-600" : "text-muted-foreground",
                            )}
                          >
                            <span
                              className={cn(
                                "h-2 w-2 rounded-full",
                                p.gateway_running ? "bg-emerald-500" : "bg-muted-foreground/40",
                              )}
                            />
                            {p.gateway_running ? profileLabels.running : profileLabels.stopped}
                            {p.gateway_pid ? ` / PID ${p.gateway_pid}` : ""}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex max-w-[22rem] flex-col gap-1 text-xs">
                            {hasOpusModel(p) && (
                              <span className="inline-flex items-center gap-1 font-semibold text-destructive">
                                <XCircle className="h-3 w-3" />
                                Opus model
                              </span>
                            )}
                            {usesAnthropicProvider(p) && (
                              <span className="inline-flex items-center gap-1 font-semibold text-destructive">
                                <XCircle className="h-3 w-3" />
                                Anthropic provider
                              </span>
                            )}
                            {globalFallback && (
                              <span className="inline-flex items-center gap-1 font-medium text-yellow-700 dark:text-yellow-400">
                                <AlertTriangle className="h-3 w-3" />
                                {profileLabels.globalFallback}
                              </span>
                            )}
                            {drift.length === 0 ? (
                              <span className="inline-flex items-center gap-1 text-emerald-600">
                                <CheckCircle2 className="h-3 w-3" />
                                {profileLabels.noDrift}
                              </span>
                            ) : (
                              drift.map((item) => (
                                <span key={item.key} className="text-muted-foreground">
                                  <span className="font-medium text-foreground">
                                    {profileLabels[item.key]}:
                                  </span>{" "}
                                  <span className="font-mono">{item.current}</span>
                                  {" -> "}
                                  <span className="font-mono text-foreground">
                                    {item.expected}
                                  </span>
                                </span>
                              ))
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            {isRenaming ? (
                              <>
                                <Button size="sm" onClick={handleRenameSubmit}>
                                  {t.common.save}
                                </Button>
                                <Button size="sm" ghost onClick={() => setRenamingFrom(null)}>
                                  {t.common.cancel}
                                </Button>
                              </>
                            ) : (
                              <>
                                <Button
                                  ghost
                                  size="icon"
                                  title={t.profiles.editSoul}
                                  aria-label={t.profiles.editSoul}
                                  onClick={() => openSoulEditor(p.name)}
                                >
                                  {isEditingSoul ? (
                                    <ChevronDown className="h-4 w-4" />
                                  ) : (
                                    <Pencil className="h-4 w-4" />
                                  )}
                                </Button>
                                <Button
                                  ghost
                                  size="icon"
                                  title={t.profiles.openInTerminal}
                                  aria-label={t.profiles.openInTerminal}
                                  onClick={() => handleCopyTerminalCommand(p.name)}
                                >
                                  <Terminal className="h-4 w-4" />
                                </Button>
                                {!p.is_default && (
                                  <Button
                                    ghost
                                    size="icon"
                                    title={t.profiles.rename}
                                    aria-label={t.profiles.rename}
                                    onClick={() => {
                                      setRenamingFrom(p.name);
                                      setRenameTo(p.name);
                                    }}
                                  >
                                    <Pencil className="h-4 w-4" />
                                  </Button>
                                )}
                                {!p.is_default && (
                                  <Button
                                    ghost
                                    size="icon"
                                    title={t.common.delete}
                                    aria-label={t.common.delete}
                                    onClick={() => profileDelete.requestDelete(p.name)}
                                  >
                                    <Trash2 className="h-4 w-4 text-destructive" />
                                  </Button>
                                )}
                              </>
                            )}
                          </div>
                        </td>
                      </tr>

                      {isExpanded && (
                        <tr className="border-b border-border bg-muted/10">
                          <td colSpan={8} className="px-4 py-4">
                            <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
                              <div className="grid gap-3">
                                <div className="text-xs font-medium uppercase text-muted-foreground">
                                  {profileLabels.settings}
                                </div>
                                <dl className="grid gap-2 text-xs">
                                  {[
                                    {
                                      label: profileLabels.config,
                                      value: p.config_path,
                                      action: profileLabels.copyConfigPath,
                                    },
                                    {
                                      label: profileLabels.env,
                                      value: p.env_path,
                                      action: profileLabels.copyEnvPath,
                                    },
                                    {
                                      label: profileLabels.path,
                                      value: p.path,
                                      action: profileLabels.copyProfilePath,
                                    },
                                    {
                                      label: "SOUL.md",
                                      value: soulPath,
                                      action: `${profileLabels.copy} SOUL.md`,
                                    },
                                  ].map((row) => (
                                    <div
                                      key={row.label}
                                      className="grid grid-cols-[7rem_minmax(0,1fr)_2rem] items-center gap-2"
                                    >
                                      <dt className="text-muted-foreground">{row.label}</dt>
                                      <dd className="min-w-0 truncate font-mono">
                                        {displayRuntimeValue(row.value)}
                                      </dd>
                                      <Button
                                        ghost
                                        size="icon"
                                        className="h-7 w-7"
                                        title={row.action}
                                        aria-label={row.action}
                                        disabled={!row.value}
                                        onClick={() => copyText(row.action, row.value)}
                                      >
                                        <Copy className="h-3.5 w-3.5" />
                                      </Button>
                                    </div>
                                  ))}
                                  <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-2">
                                    <dt className="text-muted-foreground">
                                      {profileLabels.authSource}
                                    </dt>
                                    <dd className="min-w-0 break-words font-mono">
                                      {authSources}
                                    </dd>
                                  </div>
                                  <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-2">
                                    <dt className="text-muted-foreground">
                                      {profileLabels.subagents}
                                    </dt>
                                    <dd className="min-w-0 break-words font-mono">
                                      {subagentReasoning}
                                      {subagentModel ? ` / ${subagentModel}` : ""}
                                    </dd>
                                  </div>
                                  <div className="grid grid-cols-[7rem_minmax(0,1fr)] gap-2">
                                    <dt className="text-muted-foreground">
                                      {profileLabels.expected}
                                    </dt>
                                    <dd className="font-mono">{profileLabels.expectedRuntime}</dd>
                                  </div>
                                </dl>
                              </div>

                              <div className="grid gap-3">
                                <div className="flex items-center justify-between gap-2">
                                  <div className="text-xs font-medium uppercase text-muted-foreground">
                                    {profileLabels.harness}
                                  </div>
                                  {!isEditingSoul && (
                                    <Button size="sm" ghost onClick={() => openSoulEditor(p.name)}>
                                      <Pencil className="h-3.5 w-3.5" />
                                      {t.profiles.editSoul}
                                    </Button>
                                  )}
                                </div>

                                {isEditingSoul ? (
                                  <div className="flex flex-col gap-2">
                                    <Label
                                      htmlFor={`soul-editor-${p.name}`}
                                      className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground"
                                    >
                                      {t.profiles.soulSection}
                                    </Label>
                                    <textarea
                                      id={`soul-editor-${p.name}`}
                                      className="flex min-h-[220px] w-full border border-input bg-background/40 px-3 py-2 text-sm font-mono shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                      placeholder={t.profiles.soulPlaceholder}
                                      value={soulText}
                                      onChange={(e) => setSoulText(e.target.value)}
                                    />
                                    <div className="flex justify-end">
                                      <Button
                                        size="sm"
                                        onClick={() => handleSaveSoul(p.name)}
                                        disabled={soulSaving}
                                      >
                                        {soulSaving ? t.common.saving : t.profiles.saveSoul}
                                      </Button>
                                    </div>
                                  </div>
                                ) : (
                                  <div className="border border-border bg-background/30 p-3 text-xs text-muted-foreground">
                                    <div className="font-mono text-foreground">{soulPath}</div>
                                    <div className="mt-2">
                                      {profileLabels.harness}: SOUL.md / {profileLabels.config}: config.yaml
                                    </div>
                                  </div>
                                )}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
