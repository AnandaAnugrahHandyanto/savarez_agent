import { Badge } from "@nous-research/ui/ui/components/badge";
import { Button } from "@nous-research/ui/ui/components/button";
import { Spinner } from "@nous-research/ui/ui/components/spinner";
import {
  Archive,
  Check,
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
  FolderPlus,
  MessageSquarePlus,
  MoreHorizontal,
  Pencil,
  Pin,
  PinOff,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type {
  PaginatedSessions,
  SessionInfo,
  SessionOrganizationResponse,
  SessionProject,
} from "@/lib/api";
import { cn, timeAgo } from "@/lib/utils";

const GENERAL_PROJECT_ID = "__general__";
const TREE_SESSION_LIMIT = 12;
const GENERAL_SESSION_VISIBLE_LIMIT = 2;
const GENERAL_SESSION_EXPANDED_STEP = 5;
const NON_RESUMABLE_SESSION_SOURCES = new Set(["codex", "tool"]);
const MENU_ITEM_CLASS =
  "flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm normal-case text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground disabled:pointer-events-none disabled:opacity-45";

const EMPTY_ORGANIZATION: SessionOrganizationResponse = {
  version: 1,
  updated_at: 0,
  projects: [],
  assignments: {},
};

function sessionTitle(session: SessionInfo): string {
  const title = session.title?.trim();
  if (title) return title;

  const preview = session.preview?.trim();
  if (preview) return preview.slice(0, 80);

  return "Untitled chat";
}

function projectSubLabel(project: SessionProject): string | undefined {
  if (!project.workspace_path) return undefined;
  const parts = project.workspace_path.split(/[\\/]+/).filter(Boolean);
  return parts.at(-1);
}

function nextBlankProjectName(projects: SessionProject[]): string {
  const existingNames = new Set(projects.map((project) => project.name));
  for (let index = projects.length + 1; index < projects.length + 200; index += 1) {
    const candidate = `New project ${index}`;
    if (!existingNames.has(candidate)) return candidate;
  }
  return `New project ${Date.now().toString(36)}`;
}

function projectNameFromPath(path: string, fallback: string): string {
  const parts = path.split(/[\\/]+/).filter(Boolean);
  return parts.at(-1)?.trim() || fallback;
}

function compareProjects(a: SessionProject, b: SessionProject): number {
  const aPinned = Boolean(a.pinned_at);
  const bPinned = Boolean(b.pinned_at);
  if (aPinned !== bPinned) return aPinned ? -1 : 1;

  const aTime = Number(a.pinned_at ?? a.updated_at ?? a.created_at ?? 0);
  const bTime = Number(b.pinned_at ?? b.updated_at ?? b.created_at ?? 0);
  return bTime - aTime;
}

function sessionMatchesQuery(session: SessionInfo, query: string): boolean {
  if (!query) return true;
  const haystack = [
    session.title,
    session.preview,
    session.model,
    session.source,
    session.id,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return haystack.includes(query.toLowerCase());
}

function canResumeSessionInChat(session: SessionInfo): boolean {
  const source = (session.source ?? "").trim().toLowerCase();
  if (NON_RESUMABLE_SESSION_SOURCES.has(source)) return false;
  if ((session.end_reason ?? "").trim().toLowerCase() === "codex_mirror") {
    return false;
  }
  return session.message_count >= 2;
}

function RenameField({
  initialValue,
  ariaLabel,
  saving,
  onSave,
  onCancel,
}: {
  initialValue: string;
  ariaLabel: string;
  saving: boolean;
  onSave: (value: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState(initialValue);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraft(initialValue);
    setError(null);
  }, [initialValue]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const nextValue = draft.trim();
    if (!nextValue) {
      setError("Name cannot be empty");
      return;
    }

    try {
      setError(null);
      await onSave(nextValue);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rename failed");
    }
  };

  return (
    <form onSubmit={(event) => void submit(event)} className="min-w-0 flex-1">
      <div className="flex min-w-0 items-center gap-1.5">
        <Input
          autoFocus
          aria-label={ariaLabel}
          disabled={saving}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              onCancel();
            }
          }}
          className="h-8 min-w-0 flex-1 rounded-md px-2 text-sm"
        />
        <button
          type="submit"
          disabled={saving}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground disabled:opacity-45"
          aria-label="Save name"
        >
          <Check className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          disabled={saving}
          onClick={onCancel}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground disabled:opacity-45"
          aria-label="Cancel rename"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
      {error && (
        <div className="mt-1 truncate text-xs text-destructive" title={error}>
          {error}
        </div>
      )}
    </form>
  );
}

function SessionActionMenu({
  session,
  onRename,
  onTogglePinned,
  onToggleArchived,
}: {
  session: SessionInfo;
  onRename: () => void;
  onTogglePinned: (session: SessionInfo, pinned: boolean) => void;
  onToggleArchived: (session: SessionInfo, archived: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const pinned = Boolean(session.pinned_at);
  const archived = Boolean(session.archived_at);

  const runAction = (action: () => void) => {
    setOpen(false);
    action();
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="mr-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-md opacity-0 transition-opacity hover:bg-background/30 group-hover:opacity-80 focus:opacity-100"
        aria-label={`Session actions for ${sessionTitle(session)}`}
        aria-haspopup="menu"
        aria-expanded={open}
        title="会话操作"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-9 z-40 w-48 rounded-xl border border-border/70 bg-background/95 p-1.5 shadow-xl shadow-black/20 backdrop-blur"
        >
          <button
            type="button"
            role="menuitem"
            className={MENU_ITEM_CLASS}
            onClick={() => runAction(() => onTogglePinned(session, !pinned))}
          >
            {pinned ? <PinOff className="h-4 w-4" /> : <Pin className="h-4 w-4" />}
            {pinned ? "取消置顶会话" : "置顶会话"}
          </button>

          <button
            type="button"
            role="menuitem"
            className={MENU_ITEM_CLASS}
            onClick={() => runAction(onRename)}
          >
            <Pencil className="h-4 w-4" />
            重命名对话
          </button>

          <button
            type="button"
            role="menuitem"
            className={MENU_ITEM_CLASS}
            onClick={() => runAction(() => onToggleArchived(session, !archived))}
          >
            <Archive className="h-4 w-4" />
            {archived ? "取消归档对话" : "归档对话"}
          </button>
        </div>
      )}
    </div>
  );
}

function SessionRow({
  session,
  active,
  onSelect,
  onRename,
  onTogglePinned,
  onToggleArchived,
}: {
  session: SessionInfo;
  active: boolean;
  onSelect: () => void;
  onRename: (sessionId: string, title: string) => Promise<void>;
  onTogglePinned: (session: SessionInfo, pinned: boolean) => void;
  onToggleArchived: (session: SessionInfo, archived: boolean) => void;
}) {
  const title = sessionTitle(session);
  const model = (session.model ?? "unknown").split("/").pop() ?? "unknown";
  const timestamp = timeAgo(session.last_active);
  const needsAttention = Boolean(session.needs_attention);
  const isProcessing = Boolean(session.is_active);
  const [renaming, setRenaming] = useState(false);
  const [saving, setSaving] = useState(false);

  if (renaming) {
    return (
      <div className="rounded-lg bg-secondary/25 px-2 py-2">
        <RenameField
          initialValue={title}
          ariaLabel="Rename session"
          saving={saving}
          onCancel={() => setRenaming(false)}
          onSave={async (nextTitle) => {
            setSaving(true);
            try {
              await onRename(session.id, nextTitle);
              setRenaming(false);
            } finally {
              setSaving(false);
            }
          }}
        />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "group relative flex w-full min-w-0 items-center gap-1 rounded-lg border transition-colors",
        active
          ? "border-success/55 bg-success/10 text-foreground shadow-[0_0_0_1px_rgba(120,255,180,0.14)]"
          : "border-transparent text-muted-foreground hover:bg-secondary/45 hover:text-foreground",
      )}
    >
      {active && (
        <span
          aria-label="当前选中会话"
          className="absolute left-1 top-1/2 h-2.5 w-2.5 -translate-y-1/2 rounded-full bg-success shadow-[0_0_0_3px_rgba(120,255,180,0.14)]"
        />
      )}
      <button
        type="button"
        onClick={onSelect}
        aria-current={active ? "page" : undefined}
        className={cn(
          "flex min-w-0 flex-1 items-center gap-2 py-2.5 pr-3 text-left normal-case",
          active ? "pl-5" : "pl-3",
        )}
      >
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <span className="min-w-0 flex-1 truncate text-[0.95rem] leading-5">
              {title}
            </span>
            {needsAttention && (
              <span
                aria-label="有新的 Hermes 回复"
                className="h-2 w-2 shrink-0 rounded-full bg-sky-400 shadow-[0_0_0_2px_rgba(56,189,248,0.18)]"
              />
            )}
            {session.pinned_at && (
              <Pin className="h-3.5 w-3.5 shrink-0 opacity-60" />
            )}
            {isProcessing &&
              (active ? (
                <RefreshCw
                  aria-label="正在处理"
                  className="h-3.5 w-3.5 shrink-0 animate-spin text-success"
                />
              ) : (
                <span
                  aria-label="处理中"
                  className="h-2 w-2 shrink-0 rounded-full bg-success"
                />
              ))}
          </div>

          <div className="mt-0.5 flex min-w-0 items-center gap-1.5 text-xs opacity-60">
            <span className="truncate">{model}</span>
            <span className="shrink-0">/</span>
            <span className="shrink-0">{session.message_count} msg</span>
          </div>
        </div>

        <span className="ml-1 shrink-0 text-xs tabular-nums opacity-65">
          {timestamp}
        </span>
      </button>

      <SessionActionMenu
        session={session}
        onRename={() => setRenaming(true)}
        onTogglePinned={onTogglePinned}
        onToggleArchived={onToggleArchived}
      />
    </div>
  );
}

function ProjectActionMenu({
  project,
  onNewChat,
  onRename,
  onTogglePinned,
  onToggleArchived,
  onOpenFolder,
  onRemove,
}: {
  project: SessionProject;
  onNewChat: (project: SessionProject) => void;
  onRename: () => void;
  onTogglePinned: (project: SessionProject, pinned: boolean) => void;
  onToggleArchived: (project: SessionProject, archived: boolean) => void;
  onOpenFolder: (project: SessionProject) => void;
  onRemove: (project: SessionProject) => void;
}) {
  const [open, setOpen] = useState(false);
  const pinned = Boolean(project.pinned_at);
  const archived = Boolean(project.archived_at);
  const itemClass = MENU_ITEM_CLASS;

  const runAction = (action: () => void) => {
    setOpen(false);
    action();
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-0 transition-opacity hover:bg-secondary/45 hover:text-foreground group-hover:opacity-80 focus:opacity-100"
        aria-label={`项目操作：${project.name}`}
        aria-haspopup="menu"
        aria-expanded={open}
        title="项目操作"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-9 z-30 w-56 rounded-xl border border-border/70 bg-background/95 p-1.5 shadow-xl shadow-black/20 backdrop-blur"
        >
          <button
            type="button"
            role="menuitem"
            className={itemClass}
            onClick={() => runAction(() => onNewChat(project))}
          >
            <MessageSquarePlus className="h-4 w-4" />
            新增对话
          </button>

          <button
            type="button"
            role="menuitem"
            className={itemClass}
            onClick={() => runAction(() => onTogglePinned(project, !pinned))}
          >
            {pinned ? <PinOff className="h-4 w-4" /> : <Pin className="h-4 w-4" />}
            {pinned ? "取消置顶项目" : "置顶项目"}
          </button>

          <button
            type="button"
            role="menuitem"
            className={itemClass}
            disabled={!project.workspace_path}
            onClick={() => runAction(() => onOpenFolder(project))}
          >
            <FolderOpen className="h-4 w-4" />
            在资源管理器中打开
          </button>

          <button
            type="button"
            role="menuitem"
            className={itemClass}
            onClick={() => runAction(onRename)}
          >
            <Pencil className="h-4 w-4" />
            重命名项目
          </button>

          <button
            type="button"
            role="menuitem"
            className={itemClass}
            onClick={() => runAction(() => onToggleArchived(project, !archived))}
          >
            <Archive className="h-4 w-4" />
            {archived ? "恢复项目" : "归档项目"}
          </button>

          <button
            type="button"
            role="menuitem"
            className={cn(itemClass, "text-destructive hover:text-destructive")}
            onClick={() => runAction(() => onRemove(project))}
          >
            <Trash2 className="h-4 w-4" />
            移除项目
          </button>
        </div>
      )}
    </div>
  );
}

function GeneralActionMenu({
  onNewChat,
  onOpenAll,
}: {
  onNewChat: () => void;
  onOpenAll: () => void;
}) {
  const [open, setOpen] = useState(false);

  const runAction = (action: () => void) => {
    setOpen(false);
    action();
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-0 transition-opacity hover:bg-secondary/45 hover:text-foreground group-hover:opacity-80 focus:opacity-100"
        aria-label="General chat actions"
        aria-haspopup="menu"
        aria-expanded={open}
        title="普通会话操作"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-9 z-30 w-56 rounded-xl border border-border/70 bg-background/95 p-1.5 shadow-xl shadow-black/20 backdrop-blur"
        >
          <button
            type="button"
            role="menuitem"
            className={MENU_ITEM_CLASS}
            onClick={() => runAction(onNewChat)}
          >
            <MessageSquarePlus className="h-4 w-4" />
            新增对话
          </button>

          <button
            type="button"
            role="menuitem"
            className={MENU_ITEM_CLASS}
            onClick={() => runAction(onOpenAll)}
          >
            <FolderOpen className="h-4 w-4" />
            打开全部普通会话
          </button>

          <button
            type="button"
            role="menuitem"
            className={MENU_ITEM_CLASS}
            disabled
            title="普通会话是系统分组，不能置顶或移除"
          >
            <Pin className="h-4 w-4" />
            置顶项目
          </button>

          <button
            type="button"
            role="menuitem"
            className={MENU_ITEM_CLASS}
            disabled
            title="普通会话是系统分组，不能重命名"
          >
            <Pencil className="h-4 w-4" />
            重命名项目
          </button>

          <button
            type="button"
            role="menuitem"
            className={MENU_ITEM_CLASS}
            disabled
            title="普通会话是系统分组，不能归档"
          >
            <Archive className="h-4 w-4" />
            归档项目
          </button>

          <button
            type="button"
            role="menuitem"
            className={cn(MENU_ITEM_CLASS, "text-destructive hover:text-destructive")}
            disabled
            title="普通会话是系统分组，不能移除"
          >
            <Trash2 className="h-4 w-4" />
            移除项目
          </button>
        </div>
      )}
    </div>
  );
}

function SessionGroup({
  id,
  name,
  subLabel,
  project,
  count,
  sessions,
  expanded,
  activeSessionId,
  query,
  onToggle,
  onOpenAll,
  onStartNewChat,
  onStartProjectChat,
  onOpenSession,
  onRenameProject,
  onRenameSession,
  onToggleSessionPinned,
  onToggleSessionArchived,
  onToggleProjectPinned,
  onToggleProjectArchived,
  onOpenProjectFolder,
  onRemoveProject,
}: {
  id: string;
  name: string;
  subLabel?: string;
  project?: SessionProject;
  count: number;
  sessions: SessionInfo[];
  expanded: boolean;
  activeSessionId: string | null;
  query: string;
  onToggle: () => void;
  onOpenAll: () => void;
  onStartNewChat: () => void;
  onStartProjectChat: (project: SessionProject) => void;
  onOpenSession: (session: SessionInfo) => void;
  onRenameProject: (projectId: string, name: string) => Promise<void>;
  onRenameSession: (sessionId: string, title: string) => Promise<void>;
  onToggleSessionPinned: (session: SessionInfo, pinned: boolean) => void;
  onToggleSessionArchived: (session: SessionInfo, archived: boolean) => void;
  onToggleProjectPinned: (project: SessionProject, pinned: boolean) => void;
  onToggleProjectArchived: (project: SessionProject, archived: boolean) => void;
  onOpenProjectFolder: (project: SessionProject) => void;
  onRemoveProject: (project: SessionProject) => void;
}) {
  const isGeneral = id === GENERAL_PROJECT_ID;
  const [renamingProject, setRenamingProject] = useState(false);
  const [savingProject, setSavingProject] = useState(false);
  const [generalExpandedOnce, setGeneralExpandedOnce] = useState(false);
  const visibleSessions = sessions.filter((session) =>
    sessionMatchesQuery(session, query),
  );
  const generalSessionLimit = generalExpandedOnce
    ? GENERAL_SESSION_VISIBLE_LIMIT + GENERAL_SESSION_EXPANDED_STEP
    : GENERAL_SESSION_VISIBLE_LIMIT;
  const displayedSessions =
    isGeneral && !query
      ? visibleSessions.slice(0, generalSessionLimit)
      : visibleSessions;
  const hiddenGeneralCount =
    isGeneral && !query
      ? Math.max(count - generalSessionLimit, 0)
      : 0;
  const hiddenFetchedCount =
    !isGeneral && !query ? Math.max(count - sessions.length, 0) : 0;

  useEffect(() => {
    if (query) setGeneralExpandedOnce(false);
  }, [query]);

  return (
    <div className="py-1">
      <div className="group flex min-w-0 items-center gap-1">
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          className="flex h-9 w-7 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary/45 hover:text-foreground"
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </button>

        {renamingProject ? (
          <div className="flex h-10 min-w-0 flex-1 items-center gap-2 rounded-lg px-2.5 text-muted-foreground">
            <Folder className="h-4 w-4 shrink-0" />
            <RenameField
              initialValue={name}
              ariaLabel="Rename project"
              saving={savingProject}
              onCancel={() => setRenamingProject(false)}
              onSave={async (nextName) => {
                setSavingProject(true);
                try {
                  await onRenameProject(id, nextName);
                  setRenamingProject(false);
                } finally {
                  setSavingProject(false);
                }
              }}
            />
          </div>
        ) : (
          <>
            <button
              type="button"
              onClick={onOpenAll}
              className="flex h-10 min-w-0 flex-1 items-center gap-2 rounded-lg px-2.5 text-left text-muted-foreground transition-colors hover:bg-secondary/45 hover:text-foreground"
            >
              <Folder className="h-4 w-4 shrink-0" />
              <span className="min-w-0 flex-1 truncate text-[0.95rem]">
                {name}
              </span>
              {project?.pinned_at && (
                <Pin className="h-3.5 w-3.5 shrink-0 opacity-60" />
              )}
              {project?.archived_at && (
                <span className="shrink-0 rounded border border-border/50 px-1.5 py-0.5 text-[0.65rem] uppercase tracking-[0.12em] opacity-55">
                  archived
                </span>
              )}
              {subLabel && (
                <span className="max-w-[7.5rem] shrink truncate text-sm opacity-45">
                  {subLabel}
                </span>
              )}
              <span className="shrink-0 text-sm tabular-nums opacity-60">
                {count}
              </span>
            </button>

            {isGeneral ? (
              <GeneralActionMenu
                onNewChat={onStartNewChat}
                onOpenAll={onOpenAll}
              />
            ) : project ? (
              <ProjectActionMenu
                project={project}
                onNewChat={onStartProjectChat}
                onRename={() => setRenamingProject(true)}
                onTogglePinned={onToggleProjectPinned}
                onToggleArchived={onToggleProjectArchived}
                onOpenFolder={onOpenProjectFolder}
                onRemove={onRemoveProject}
              />
            ) : null}
          </>
        )}
      </div>

      {expanded && (
        <div className="mt-1 flex flex-col gap-0.5 pl-8">
          {displayedSessions.length > 0 ? (
            <>
              {displayedSessions.map((session) => (
                <SessionRow
                  key={session.id}
                  session={session}
                  active={activeSessionId === session.id}
                  onSelect={() => onOpenSession(session)}
                  onRename={onRenameSession}
                  onTogglePinned={onToggleSessionPinned}
                  onToggleArchived={onToggleSessionArchived}
                />
              ))}
              {hiddenGeneralCount > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    if (!generalExpandedOnce) {
                      setGeneralExpandedOnce(true);
                      return;
                    }
                    onOpenAll();
                  }}
                  className="rounded-lg px-3 py-2 text-left text-sm text-muted-foreground/75 transition-colors hover:bg-secondary/35 hover:text-foreground"
                >
                  更多普通会话 ({hiddenGeneralCount})
                </button>
              )}
              {hiddenFetchedCount > 0 && (
                <button
                  type="button"
                  onClick={onOpenAll}
                  className="rounded-lg px-3 py-2 text-left text-sm text-muted-foreground/70 transition-colors hover:bg-secondary/35 hover:text-foreground"
                >
                  View all sessions
                </button>
              )}
            </>
          ) : (
            <div className="px-3 py-2 text-sm text-muted-foreground/65">
              {query ? "No matching sessions" : "No sessions yet"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface ChatSessionNavigatorProps {
  activeSessionId?: string | null;
  className?: string;
}

export function ChatSessionNavigator({
  activeSessionId = null,
  className,
}: ChatSessionNavigatorProps) {
  const navigate = useNavigate();
  const [organization, setOrganization] =
    useState<SessionOrganizationResponse>(EMPTY_ORGANIZATION);
  const [sessionsByGroup, setSessionsByGroup] = useState<
    Record<string, SessionInfo[]>
  >({});
  const [totalsByGroup, setTotalsByGroup] = useState<Record<string, number>>(
    {},
  );
  const [expandedGroupIds, setExpandedGroupIds] = useState<Set<string>>(
    () => new Set([GENERAL_PROJECT_ID]),
  );
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newMenuOpen, setNewMenuOpen] = useState(false);
  const [showArchivedProjects, setShowArchivedProjects] = useState(false);

  const archivedProjectCount = useMemo(
    () =>
      organization.projects.filter((project) => Boolean(project.archived_at))
        .length,
    [organization.projects],
  );

  const visibleProjects = useMemo(
    () =>
      [...organization.projects]
        .filter((project) => showArchivedProjects || !project.archived_at)
        .sort(compareProjects),
    [organization.projects, showArchivedProjects],
  );

  const groups = useMemo<Array<{
    id: string;
    name: string;
    subLabel?: string;
    project?: SessionProject;
  }>>(
    () => [
      {
        id: GENERAL_PROJECT_ID,
        name: "General chats",
        subLabel: "Unassigned sessions",
      },
      ...visibleProjects.map((project) => ({
        id: project.id,
        name: project.name,
        subLabel: projectSubLabel(project),
        project,
      })),
    ],
    [visibleProjects],
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const nextOrganization = await api
        .getSessionOrganization()
        .catch(() => EMPTY_ORGANIZATION);
      const entries = [
        { id: GENERAL_PROJECT_ID, projectId: GENERAL_PROJECT_ID },
        ...nextOrganization.projects.map((project) => ({
          id: project.id,
          projectId: project.id,
        })),
      ];
      const results = await Promise.all(
        entries.map(async (entry) => {
          const resp = await api.getSessions(
            TREE_SESSION_LIMIT,
            0,
            entry.projectId,
          );
          return [entry.id, resp] as const;
        }),
      );
      const nextSessions: Record<string, SessionInfo[]> = {};
      const nextTotals: Record<string, number> = {};
      for (const [id, resp] of results) {
        const page: PaginatedSessions = resp;
        nextSessions[id] = page.sessions;
        nextTotals[id] = page.total;
      }

      setOrganization(nextOrganization);
      setSessionsByGroup(nextSessions);
      setTotalsByGroup(nextTotals);
      setExpandedGroupIds((prev) => {
        const next = new Set(prev);
        next.add(GENERAL_PROJECT_ID);
        for (const project of nextOrganization.projects) {
          next.add(project.id);
        }
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load sessions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void refresh();
    }, 0);
    return () => window.clearTimeout(id);
  }, [refresh]);

  const toggleGroup = useCallback((groupId: string) => {
    setExpandedGroupIds((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) {
        next.delete(groupId);
      } else {
        next.add(groupId);
      }
      return next;
    });
  }, []);

  const openAllSessions = useCallback(() => {
    navigate("/sessions");
  }, [navigate]);

  const openSession = useCallback(
    (session: SessionInfo) => {
      void api
        .updateSessionOrganizationMeta(session.id, { seen: true })
        .catch(() => undefined);
      if (!canResumeSessionInChat(session)) {
        navigate("/chat");
        return;
      }
      navigate(`/chat?resume=${encodeURIComponent(session.id)}`);
    },
    [navigate],
  );

  const startNewChat = useCallback(() => {
    navigate("/chat");
  }, [navigate]);

  const startProjectChat = useCallback(
    (project: SessionProject) => {
      navigate(`/chat?project=${encodeURIComponent(project.id)}`);
    },
    [navigate],
  );

  const createBlankProject = useCallback(async () => {
    const defaultName = nextBlankProjectName(organization.projects);
    const nextName = window.prompt("项目名称", defaultName)?.trim();
    if (!nextName) return;

    setLoading(true);
    setError(null);
    try {
      const response = await api.createSessionProject({ name: nextName });
      await refresh();
      setExpandedGroupIds((prev) => {
        const next = new Set(prev);
        next.add(response.project.id);
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create project");
    } finally {
      setLoading(false);
    }
  }, [organization.projects, refresh]);

  const createProjectFromFolder = useCallback(async () => {
    const workspacePath = window.prompt("现有文件夹路径")?.trim();
    if (!workspacePath) return;

    const fallbackName = nextBlankProjectName(organization.projects);
    const defaultName = projectNameFromPath(workspacePath, fallbackName);
    const nextName = window.prompt("项目名称", defaultName)?.trim();
    if (!nextName) return;

    setLoading(true);
    setError(null);
    try {
      const response = await api.createSessionProject({
        name: nextName,
        workspace_path: workspacePath,
      });
      await refresh();
      setExpandedGroupIds((prev) => {
        const next = new Set(prev);
        next.add(response.project.id);
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to create project");
    } finally {
      setLoading(false);
    }
  }, [organization.projects, refresh]);

  const renameSession = useCallback(
    async (sessionId: string, title: string) => {
      await api.updateSessionTitle(sessionId, title);
      await refresh();
    },
    [refresh],
  );

  const toggleSessionPinned = useCallback(
    async (session: SessionInfo, pinned: boolean) => {
      try {
        await api.updateSessionOrganizationMeta(session.id, { pinned });
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unable to update session");
      }
    },
    [refresh],
  );

  const toggleSessionArchived = useCallback(
    async (session: SessionInfo, archived: boolean) => {
      try {
        await api.updateSessionOrganizationMeta(session.id, { archived });
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unable to update session");
      }
    },
    [refresh],
  );

  const renameProject = useCallback(
    async (projectId: string, name: string) => {
      await api.updateSessionProject(projectId, { name });
      await refresh();
    },
    [refresh],
  );

  const toggleProjectPinned = useCallback(
    async (project: SessionProject, pinned: boolean) => {
      try {
        await api.updateSessionProject(project.id, { pinned });
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unable to update project");
      }
    },
    [refresh],
  );

  const toggleProjectArchived = useCallback(
    async (project: SessionProject, archived: boolean) => {
      try {
        await api.updateSessionProject(project.id, { archived });
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unable to update project");
      }
    },
    [refresh],
  );

  const openProjectFolder = useCallback(async (project: SessionProject) => {
    try {
      await api.openSessionProject(project.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to open project folder");
    }
  }, []);

  const removeProject = useCallback(
    async (project: SessionProject) => {
      const confirmed = window.confirm(
        `从侧栏移除“${project.name}”？会话仍保留在 Hermes，并回到普通会话。`,
      );
      if (!confirmed) return;

      try {
        await api.deleteSessionProject(project.id);
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unable to remove project");
      }
    },
    [refresh],
  );

  return (
    <Card
      className={cn(
        "flex min-h-0 flex-1 flex-col overflow-hidden px-0 py-0 font-sans",
        className,
      )}
    >
      <div className="flex items-center gap-2 px-4 pb-3 pt-4">
        <div className="min-w-0 flex-1">
          <div className="text-xs uppercase tracking-[0.14em] text-muted-foreground">
            sessions
          </div>
          <div className="truncate text-base font-medium">Conversation map</div>
        </div>

        {loading && <Spinner className="h-3.5 w-3.5" />}

        <Button
          ghost
          size="icon"
          onClick={() => void refresh()}
          title="Refresh sessions"
          aria-label="Refresh sessions"
          className="h-8 w-8 text-muted-foreground hover:text-foreground"
        >
          <RefreshCw className="h-4 w-4" />
        </Button>

        <div className="relative">
          <Button
            ghost
            size="icon"
            onClick={() => setNewMenuOpen((value) => !value)}
            title="新建"
            aria-label="新建"
            aria-haspopup="menu"
            aria-expanded={newMenuOpen}
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
          >
            <MessageSquarePlus className="h-4 w-4" />
          </Button>

          {newMenuOpen && (
            <div
              role="menu"
              className="absolute right-0 top-9 z-30 w-56 rounded-xl border border-border/70 bg-background/95 p-1.5 shadow-xl shadow-black/20 backdrop-blur"
            >
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setNewMenuOpen(false);
                  startNewChat();
                }}
                className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm normal-case text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground"
              >
                <MessageSquarePlus className="h-4 w-4" />
                新聊天
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setNewMenuOpen(false);
                  void createBlankProject();
                }}
                className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm normal-case text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground"
              >
                <FolderPlus className="h-4 w-4" />
                新建空白项目
              </button>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setNewMenuOpen(false);
                  void createProjectFromFolder();
                }}
                className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm normal-case text-muted-foreground transition-colors hover:bg-secondary/60 hover:text-foreground"
              >
                <FolderOpen className="h-4 w-4" />
                使用现有文件夹
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="px-4 pb-3">
        <Button
          ghost
          onClick={startNewChat}
          className="mb-2 flex h-10 w-full justify-start gap-2 rounded-lg px-3 text-base normal-case text-muted-foreground hover:bg-secondary/45 hover:text-foreground"
        >
          <MessageSquarePlus className="h-4 w-4 shrink-0" />
          新聊天
        </Button>

        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/70" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search sessions"
            className="h-10 rounded-lg pl-9 text-base"
          />
        </div>
      </div>

      {error && (
        <div className="mx-4 mb-3 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          <div className="font-medium">Session map unavailable</div>
          <div className="mt-0.5 truncate text-xs opacity-75" title={error}>
            {error}
          </div>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-2">
        {groups.map((group) => (
          <SessionGroup
            key={group.id}
            id={group.id}
            name={group.name}
            subLabel={group.subLabel}
            project={group.project}
            count={totalsByGroup[group.id] ?? 0}
            sessions={sessionsByGroup[group.id] ?? []}
            expanded={expandedGroupIds.has(group.id)}
            activeSessionId={activeSessionId}
            query={query.trim()}
            onToggle={() => toggleGroup(group.id)}
            onOpenAll={openAllSessions}
            onStartNewChat={startNewChat}
            onStartProjectChat={startProjectChat}
            onOpenSession={openSession}
            onRenameProject={renameProject}
            onRenameSession={renameSession}
            onToggleSessionPinned={(session, pinned) =>
              void toggleSessionPinned(session, pinned)
            }
            onToggleSessionArchived={(session, archived) =>
              void toggleSessionArchived(session, archived)
            }
            onToggleProjectPinned={(project, pinned) =>
              void toggleProjectPinned(project, pinned)
            }
            onToggleProjectArchived={(project, archived) =>
              void toggleProjectArchived(project, archived)
            }
            onOpenProjectFolder={(project) => void openProjectFolder(project)}
            onRemoveProject={(project) => void removeProject(project)}
          />
        ))}

        {!loading &&
          groups.length === 1 &&
          (totalsByGroup[GENERAL_PROJECT_ID] ?? 0) === 0 && (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground/65">
              No chats have been indexed yet.
            </div>
          )}
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-border/50 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <Badge tone="secondary" className="shrink-0 px-2 py-1 text-xs">
            {visibleProjects.length} projects
          </Badge>
          {archivedProjectCount > 0 && (
            <Button
              ghost
              size="sm"
              onClick={() => setShowArchivedProjects((value) => !value)}
              className="h-8 px-2 py-0 text-xs normal-case text-muted-foreground hover:text-foreground"
            >
              {showArchivedProjects ? "隐藏归档项目" : `归档项目 ${archivedProjectCount}`}
            </Button>
          )}
        </div>
        <Button
          ghost
          size="sm"
          onClick={openAllSessions}
          className="h-8 px-2 py-0 text-sm normal-case text-muted-foreground hover:text-foreground"
        >
          Open sessions
        </Button>
      </div>
    </Card>
  );
}
