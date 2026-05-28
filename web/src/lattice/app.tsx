// app.tsx — Lattice desktop AI workspace
import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { cn, Tooltip } from './primitives';
import { useTweaks, TweaksPanel, TweakSection, TweakToggle, TweakColor, TweakRadio } from './tweaks-panel';
import { Composer } from './composer';
import { Menu, SearchPalette, ProjectsModal, KnowledgeModal, MsgActions } from './extras';
import { ArtifactPanel, ArtifactCard, ARTIFACTS_SAMPLE } from './artifact-panel';
import { ProjectsView, ProjectDetailView, KnowledgeView, HistoryView, FileViewerPanel } from './views';
import { ConnectorsView } from './connectors';
import { SkillsView } from './skills';
import { MyAccountModal, MyAccountView, SettingsModal, SettingsView } from './modals';

// ── Icons ─────────────────────────────────────────────────────────────────────
const Icon = {
  Plus: () => <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M8 3v10M3 8h10"/></svg>,
  Search: () => <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M13.5 13.5L10.5 10.5" strokeLinecap="round"/></svg>,
  Folder: () => <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"><path d="M2 4.5A1.5 1.5 0 013.5 3h2.7l1.3 1.3h5A1.5 1.5 0 0114 5.8v5.7A1.5 1.5 0 0112.5 13h-9A1.5 1.5 0 012 11.5v-7z"/></svg>,
  Chev: () => <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M6 4l4 4-4 4"/></svg>,
  ChevDown: () => <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M4 6l4 4 4-4"/></svg>,
  Clock: () => <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><circle cx="8" cy="8" r="6"/><path d="M8 4.5V8l2.5 1.5"/></svg>,
  Panel: () => <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"><rect x="2" y="3" width="12" height="10" rx="1.5"/><path d="M10 3v10"/></svg>,
  PanelLeft: () => <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"><rect x="2" y="3" width="12" height="10" rx="1.5"/><path d="M6 3v10"/></svg>,
};

// ── Sample data ───────────────────────────────────────────────────────────────
const NOW = Date.now();
const min = (m: number) => NOW - m * 60_000;
const hr  = (h: number) => NOW - h * 3_600_000;

const initialConvos: any[] = [
  {
    id: "paperclip",
    title: "Work analysis",
    project: { root: "paperclip-master", path: "Work analysis" },
    updatedAt: min(0.2),
    pinned: true,
    messages: [
      { id: "u1", role: "user",
        text: "Confirm the embedded PG harness applies our migrations. I need the issue_work_products columns visible to the gate." },
      { id: "a1", role: "assistant", blocks: [
        { kind: "text", text: "Looking at the harness setup — it boots Postgres through `applyPendingMigrations`, which runs the full migration list. That means `work_products`, `issue_approvals`, `approvals`, and `cost_events` all exist before the gate evaluates." },
        { kind: "artifact", artifactId: "art-counter" },
        { kind: "tool", tag: "Bash", title: "Run shared verification-gate tests",
          meta: "0.8s · 19/19 ✓",
          body: "$ pnpm test packages/server/verification-gate\n\n  ✓ blocks low-confidence advisory (84ms)\n  ✓ allows passthrough on bypass-by-board (61ms)\n  ✓ rejects mismatched actor on update (44ms)\n  ✓ enforces tool-governance allowlist (52ms)\n  …\n  Tests:  19 passed, 19 total\n  Time:   0.812 s",
          open: true },
        { kind: "tool", tag: "Read", title: "issue_work_products.ts",
          meta: "143 lines · 1 file",
          body: " 18  export const issueWorkProducts = pgTable(\n 19    'issue_work_products',\n 20    {\n 21      id:        uuid('id').primaryKey(),\n 22      companyId: uuid('company_id').notNull(),\n 23      issueId:   uuid('issue_id').notNull(),\n 24      type:      workProductType('type').notNull(),\n 25      provider:  text('provider').notNull(),\n 26      title:     text('title').notNull(),\n 27      status:    workProductStatus('status').notNull(),\n 28      …",
          open: false },
        { kind: "text", text: "Required fields on a work product: `companyId`, `issueId`, `type`, `provider`, `title`, `status`. I'll write the enforcement integration test with three cases — *advisory*, *block*, *bypass-no-block* — and one passthrough." },
        { kind: "tool", tag: "Edit", title: "verification-gate.integration.test.ts",
          meta: "+84 −0",
          body: " 1  + import { describe, it, expect } from 'vitest';\n 2  + import { applyPendingMigrations } from '../harness/pg';\n 3  + import { evaluateGate } from '../verification-gate';\n 4  +\n 5  + describe('verification-gate (integration, PG)', () => {\n 6  +   beforeAll(applyPendingMigrations);\n 7  +\n 8  +   it('blocks low-confidence advisory', async () => {\n 9  +     const result = await evaluateGate({ …\n10  +     expect(result.decision).toBe('block');\n11  +   });\n12  +   …",
          open: false },
        { kind: "text", text: "Stage 21 is closed. Moving to stage 12 — the envelope is declared in the prompt but the real enforcement lives in `toolGovernanceService.evaluate`. The gate should consult `allowedTools` from the run envelope and reject anything outside it. Want me to start there?" },
      ]},
    ],
    tasks: [
      { id: "t1", name: "Run enforcement test from server dir",           tool: "Bash", status: "done",    time: "0.6s" },
      { id: "t2", name: "Run verification-gate enforcement integration",   tool: "Bash", status: "done",    time: "1.2s" },
      { id: "t3", name: "Run issues-service integration (embedded PG)",    tool: "Bash", status: "done",    time: "2.8s" },
      { id: "t4", name: "Run shared verification-gate tests",              tool: "Bash", status: "done",    time: "0.8s" },
      { id: "t5", name: "Typecheck server package",                        tool: "Bash", status: "error",   time: "—", error: "exit 2" },
      { id: "t6", name: "Check skills / global existence and references",  tool: "Grep", status: "done",    time: "0.2s" },
      { id: "t7", name: "Run intake classifier and model tests",           tool: "Bash", status: "running", time: "—" },
      { id: "t8", name: "Run planner unit tests",                          tool: "Bash", status: "queued",  time: "—" },
    ],
  },
  {
    id: "landing",
    title: "Landing copy refresh",
    project: { root: "marketing", path: "homepage / hero" },
    updatedAt: hr(2),
    pinned: false,
    messages: [
      { id: "u1", role: "user",
        text: "Three hero variants for the homepage. Audience is engineering leaders evaluating Lattice for the first time. Keep it under 10 words each." },
      { id: "a1", role: "assistant", blocks: [
        { kind: "text", text: "Three angles — outcome, contrast, and craft:\n\n**1. Outcome.** *Ship the work, not just the chat.*\n**2. Contrast.** *A workspace your agent actually inhabits.*\n**3. Craft.** *Where careful thought meets keyboard speed.*\n\nWant me to tighten one, or push further on a specific angle? I can also draft a supporting subhead for each." },
        { kind: "artifact", artifactId: "art-hero" },
      ]},
    ],
    tasks: [
      { id: "t1", name: "Read brand voice guidelines", tool: "Read", status: "done", time: "0.1s" },
      { id: "t2", name: "Scan competitor hero copy",   tool: "Web",  status: "done", time: "2.1s" },
    ],
  },
  {
    id: "okr",
    title: "Q3 OKR brainstorm",
    project: { root: "planning", path: "q3 / objectives" },
    updatedAt: hr(8),
    pinned: false,
    messages: [
      { id: "u1", role: "user", text: "Help me draft three Q3 objectives focused on reducing time-to-value for new teams." },
      { id: "a1", role: "assistant", blocks: [
        { kind: "text", text: "Before drafting — what's your current TTV baseline? If it's measured in days vs. weeks vs. minutes, the objectives shape very differently. I'll assume *days from signup to first useful output* and propose three:" },
        { kind: "artifact", artifactId: "art-notes" },
      ]},
    ],
    tasks: [
      { id: "t1", name: "Pull Q2 activation funnel", tool: "Query", status: "done", time: "0.9s" },
    ],
  },
  {
    id: "types",
    title: "Type system migration plan",
    project: { root: "lattice-core", path: "types / migration" },
    updatedAt: hr(26),
    pinned: false,
    messages: [
      { id: "u1", role: "user", text: "Walk me through migrating our generated types from the old codegen to TypeBox without breaking the public API." },
      { id: "a1", role: "assistant", blocks: [
        { kind: "text", text: "Three-phase plan. The hard constraint is that the public types in `@lattice/types` must remain structurally identical at the type level, even as the generator changes underneath." },
        { kind: "tool", tag: "Read", title: "Survey codegen call sites",
          meta: "42 matches · 18 files",
          body: " packages/server/src/handlers/issue.ts:14\n packages/server/src/handlers/work.ts:22\n packages/web/src/lib/api.ts:8\n packages/cli/src/commands/run.ts:31\n …",
          open: false },
      ]},
    ],
    tasks: [
      { id: "t1", name: "Survey codegen call sites",   tool: "Grep", status: "done", time: "0.3s" },
      { id: "t2", name: "Read existing typebox schemas", tool: "Read", status: "done", time: "0.1s" },
    ],
  },
  {
    id: "new",
    title: "New chat",
    project: { root: "personal", path: null },
    updatedAt: NOW,
    pinned: false,
    fresh: true,
    messages: [],
    tasks: [],
  },
];

const RECENT_GROUPS = [
  { label: "Pinned",   match: (c: any) => c.pinned && !c.archived },
  { label: "Today",    match: (c: any) => !c.pinned && !c.archived && c.updatedAt > hr(20) },
  { label: "Earlier",  match: (c: any) => !c.pinned && !c.archived && c.updatedAt <= hr(20) },
  { label: "Archived", match: (c: any) => c.archived },
];

function relTime(ts: number) {
  const d = Math.max(1, Math.round((NOW - ts) / 60_000));
  if (d < 60) return `${d}m`;
  const h = Math.round(d / 60);
  if (h < 24) return `${h}h`;
  return `${Math.round(h / 24)}d`;
}

// ── ConvoRow ──────────────────────────────────────────────────────────────────
function ConvoRow({ c, active, editing, onSelect, onMenu, onStartEdit, onSaveEdit, onCancelEdit }: {
  c: any; active: boolean; editing: boolean;
  onSelect: () => void;
  onMenu: (rect: any) => void;
  onStartEdit: () => void;
  onSaveEdit: (t: string) => void;
  onCancelEdit: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState(c.title);
  useEffect(() => {
    if (editing) {
      setDraft(c.title);
      setTimeout(() => { inputRef.current?.focus(); inputRef.current?.select(); }, 0);
    }
  }, [editing, c.title]);

  if (editing) {
    return (
      <div className={`convo${active ? " active" : ""}`}>
        <input
          ref={inputRef}
          className="convo-edit"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={() => onSaveEdit(draft.trim() || c.title)}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); onSaveEdit(draft.trim() || c.title); }
            else if (e.key === "Escape") { onCancelEdit(); }
          }}
        />
      </div>
    );
  }

  return (
    <div
      className={`convo${active ? " active" : ""}${c.pinned ? " pinned" : ""}${c.archived ? " archived" : ""}`}
      onClick={onSelect}
      onDoubleClick={(e) => { e.stopPropagation(); onStartEdit(); }}
      onContextMenu={(e) => {
        e.preventDefault();
        onMenu({ left: e.clientX, top: e.clientY, right: e.clientX, bottom: e.clientY, width: 0, height: 0, x: e.clientX, y: e.clientY, toJSON: () => ({}) });
      }}>
      <span className="convo-title">{c.title}</span>
      <button
        className="convo-more"
        aria-label="Conversation options"
        onClick={(e) => { e.stopPropagation(); onMenu(e.currentTarget.getBoundingClientRect()); }}>
        <svg viewBox="0 0 16 16" fill="currentColor"><circle cx="3.5" cy="8" r="1.2"/><circle cx="8" cy="8" r="1.2"/><circle cx="12.5" cy="8" r="1.2"/></svg>
      </button>
      <span className="convo-meta">{relTime(c.updatedAt)}</span>
    </div>
  );
}

// ── Sidebar ───────────────────────────────────────────────────────────────────
function Sidebar({ convos, activeId, onSelect, onNew, sidebarOpen, onToggleSidebar, onOpenSearch, onOpenProjects, onOpenHistory, currentView, onOpenAccountMenu, onConvoMenu, onRenameConvo, editingId, setEditingId, account }: any) {
  const collapsed = !sidebarOpen;
  const isV = (k: string) => currentView === k;
  return (
    <aside className={cn("sidebar", collapsed && "is-collapsed")}>
      <div className="sb-top">
        <Tooltip label={collapsed ? "Expand sidebar" : "Collapse sidebar"} side={collapsed ? "right" : "bottom"}>
          <button className="icon-btn sb-toggle" onClick={onToggleSidebar} aria-label="Toggle sidebar">
            <Icon.PanelLeft />
          </button>
        </Tooltip>
      </div>

      <div className="sb-actions">
        <Tooltip label="New chat  ⌘N" side="right" delay={collapsed ? 250 : 600}>
          <button className="sb-act primary" onClick={onNew}>
            <Icon.Plus /> <span className="sb-label">New chat</span>
            <span className="kbd">⌘N</span>
          </button>
        </Tooltip>
        <Tooltip label="Search  ⌘K" side="right" delay={collapsed ? 250 : 600}>
          <button className="sb-act" onClick={onOpenSearch}>
            <Icon.Search /> <span className="sb-label">Search</span>
            <span className="kbd">⌘K</span>
          </button>
        </Tooltip>
        <Tooltip label="Projects" side="right" delay={collapsed ? 250 : 600}>
          <button className={cn("sb-act", (isV("projects") || isV("project")) && "is-active")} onClick={onOpenProjects}>
            <Icon.Folder /> <span className="sb-label">Projects</span>
          </button>
        </Tooltip>
        <Tooltip label="History" side="right" delay={collapsed ? 250 : 600}>
          <button className={cn("sb-act", isV("history") && "is-active")} onClick={onOpenHistory}>
            <Icon.Clock /> <span className="sb-label">History</span>
          </button>
        </Tooltip>
      </div>

      <div className="sb-list">
        {RECENT_GROUPS.map((g) => {
          const items = convos.filter(g.match);
          if (!items.length) return null;
          return (
            <div key={g.label}>
              <div className="sb-section">
                <span>{g.label}</span>
                <span className="count">{String(items.length).padStart(2, "0")}</span>
              </div>
              {items.map((c: any) => (
                <ConvoRow key={c.id} c={c} active={c.id === activeId}
                          editing={editingId === c.id}
                          onSelect={() => onSelect(c.id)}
                          onMenu={(rect: any) => onConvoMenu?.(c.id, rect)}
                          onStartEdit={() => setEditingId(c.id)}
                          onSaveEdit={(t: string) => { onRenameConvo?.(c.id, t); setEditingId(null); }}
                          onCancelEdit={() => setEditingId(null)} />
              ))}
            </div>
          );
        })}
      </div>

      <div className="sb-foot"
           onClick={(e) => onOpenAccountMenu?.(e.currentTarget.getBoundingClientRect())}
           style={{ cursor: "default" }}>
        <div className="avatar">{account?.initials || "ja"}</div>
        <div className="sb-who" style={{ flex: 1, minWidth: 0 }}>
          <div className="who">{account?.name || ""}</div>
          <div className="plan">{account?.plan || ""}</div>
        </div>
        <button className="icon-btn sb-foot-chev"
                onClick={(e) => { e.stopPropagation(); onOpenAccountMenu?.(e.currentTarget.getBoundingClientRect()); }}>
          <Icon.ChevDown />
        </button>
      </div>
    </aside>
  );
}

// ── Breadcrumb ────────────────────────────────────────────────────────────────
function Breadcrumb({ convo, onToggleSidebar, onToggleTasks, tasksOpen, onOpenProjectMenu }: any) {
  return (
    <div className="topbar">
      <button className="icon-btn topbar-menu" onClick={onToggleSidebar} aria-label="Toggle sidebar">
        <Icon.PanelLeft />
      </button>
      <button className="crumbs crumbs-btn"
              onClick={(e) => onOpenProjectMenu?.(e.currentTarget.getBoundingClientRect())}>
        <span className="ic"><Icon.Folder /></span>
        <span className="root">{convo.project.root}</span>
        {convo.project.path && (
          <>
            <span className="sep">/</span>
            <span className="leaf">{convo.project.path}</span>
          </>
        )}
        <span className="chev"><Icon.ChevDown /></span>
      </button>
      <div className="top-right">
        <span className="top-pill">
          <span className="dot"></span>
          <span>connected</span>
        </span>
        <button className="icon-btn panel-toggle" onClick={onToggleTasks} title={tasksOpen ? "Hide tasks  ⌘J" : "Show tasks  ⌘J"}>
          <Icon.Panel />
        </button>
      </div>
    </div>
  );
}

// ── ToolCard ──────────────────────────────────────────────────────────────────
function ToolCard({ block }: { block: any }) {
  const [open, setOpen] = useState(!!block.open);
  return (
    <div className={`tool${open ? " open" : ""}`}>
      <div className="tool-hd" onClick={() => setOpen((o) => !o)}>
        <span className={`tool-tag ${block.tag.toLowerCase()}`}>{block.tag}</span>
        <span className="tool-title">{block.title}</span>
        <span className="tool-meta">{block.meta}</span>
        <span className="tool-chev"><Icon.Chev /></span>
      </div>
      {open && <div className="tool-body">{block.body}</div>}
    </div>
  );
}

// ── TextBlock ─────────────────────────────────────────────────────────────────
function renderInline(text: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
  let last = 0, m: RegExpExecArray | null, k = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<strong key={k++}>{tok.slice(2, -2)}</strong>);
    else if (tok.startsWith("`")) out.push(<code key={k++}>{tok.slice(1, -1)}</code>);
    else out.push(<em key={k++}>{tok.slice(1, -1)}</em>);
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function TextBlock({ text, streaming }: { text: string; streaming?: boolean }) {
  const paras = text.split(/\n\n+/);
  return (
    <div className="msg-text">
      {paras.map((p, i) => (
        <p key={i}>
          {p.split("\n").map((line, j) => (
            <React.Fragment key={j}>
              {j > 0 && <br />}
              {renderInline(line)}
            </React.Fragment>
          ))}
          {streaming && i === paras.length - 1 && <span className="caret" />}
        </p>
      ))}
    </div>
  );
}

// ── Message ───────────────────────────────────────────────────────────────────
function Message({ m, streaming, onRegen, onOpenArtifact }: { m: any; streaming?: boolean; onRegen: () => void; onOpenArtifact: (id: string) => void }) {
  if (m.role === "user") return <div className="msg-user">{m.text}</div>;
  return (
    <div className="msg-assist">
      {m.blocks.map((b: any, i: number) => {
        if (b.kind === "text") {
          const isLast = i === m.blocks.length - 1;
          return <TextBlock key={i} text={b.text} streaming={streaming && isLast} />;
        }
        if (b.kind === "artifact") {
          const a = ARTIFACTS_SAMPLE[b.artifactId as keyof typeof ARTIFACTS_SAMPLE];
          if (!a) return null;
          return <ArtifactCard key={i} artifact={a} onOpen={onOpenArtifact} />;
        }
        return <ToolCard key={i} block={b} />;
      })}
      {!streaming && m.blocks.length > 0 && (
        <MsgActions
          onCopy={async () => {
            const text = m.blocks
              .map((b: any) => b.kind === "text" ? b.text : `[${b.tag}] ${b.title}\n${b.body || ""}`)
              .join("\n\n");
            try { await navigator.clipboard.writeText(text); }
            catch {
              const ta = document.createElement("textarea");
              ta.value = text; document.body.appendChild(ta);
              ta.select(); document.execCommand("copy"); ta.remove();
            }
          }}
          onRegen={onRegen}
          onLike={() => {}}
          onDislike={() => {}}
        />
      )}
    </div>
  );
}

// ── EmptyHome ─────────────────────────────────────────────────────────────────
const QUICK_CHIPS = [
  { id: "code",     label: "Código",      prompt: "Escreva código para ", icon: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M5 5L2 8l3 3M11 5l3 3-3 3M9.5 3l-3 10" />
    </svg>) },
  { id: "strat",    label: "Estratégias", prompt: "Me ajude a planejar uma estratégia para ", icon: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 12l4-4 3 3 5-6" /><path d="M11 5h2v2" />
    </svg>) },
  { id: "drive",    label: "Do Drive",    prompt: "Encontre no meu Drive ", icon: (
    <svg viewBox="0 0 16 16">
      <path d="M5.5 1.5h3l4 7h-3z" fill="#FFC107"/>
      <path d="M2 10.5l3-5 3 5z" fill="#1FA463"/>
      <path d="M5.5 10.5h7l-1.5 3h-4z" fill="#4285F4"/>
    </svg>) },
  { id: "calendar", label: "Do Calendar", prompt: "No meu calendário, ", icon: (
    <svg viewBox="0 0 16 16">
      <rect x="2" y="3" width="12" height="11" rx="1.5" fill="#fff" stroke="#dadce0" strokeWidth=".5"/>
      <rect x="2" y="3" width="12" height="3" fill="#4285F4"/>
      <text x="8" y="12.4" fontSize="6" fontWeight="700" fill="#4285F4" textAnchor="middle" fontFamily="sans-serif">27</text>
    </svg>) },
  { id: "gmail",    label: "Do Gmail",    prompt: "No meu Gmail, ", icon: (
    <svg viewBox="0 0 16 16">
      <path d="M2 4.5v8a.5.5 0 00.5.5H4V8L2 4.5z" fill="#4285F4"/>
      <path d="M12 13h1.5a.5.5 0 00.5-.5v-8L12 8z" fill="#34A853"/>
      <path d="M2 4.5L8 9l6-4.5V4a1 1 0 00-1-1H3a1 1 0 00-1 1z" fill="#EA4335"/>
      <path d="M4 8v5h8V8L8 11z" fill="#FBBC04"/>
    </svg>) },
];

function EmptyHome({ children, onPick }: { children?: React.ReactNode; onPick?: (p: string) => void }) {
  return (
    <div className="empty-home">
      {children}
      <div className="quick-chips">
        {QUICK_CHIPS.map((c) => (
          <button key={c.id} className="quick-chip" onClick={() => onPick?.(c.prompt)}>
            <span className="quick-chip-icon">{c.icon}</span>
            <span>{c.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ── TasksPanel ────────────────────────────────────────────────────────────────
function TasksPanel({ tasks, onClear, onRetry, onStop, tasksOpen }: any) {
  if (!tasksOpen) return null;
  const [width, setWidth] = useState(() => {
    const saved = +(localStorage.getItem("lattice.tasks.w") || "0");
    return saved && saved >= 280 && saved <= 720 ? saved : 340;
  });
  useEffect(() => {
    document.documentElement.style.setProperty("--tasks-w", width + "px");
    localStorage.setItem("lattice.tasks.w", String(width));
  }, [width]);

  const onMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;
    const onMove = (ev: MouseEvent) => {
      const next = Math.max(280, Math.min(720, startW + (startX - ev.clientX)));
      setWidth(next);
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  };

  const running = tasks.filter((t: any) => t.status === "running");
  const queued  = tasks.filter((t: any) => t.status === "queued");
  const errored = tasks.filter((t: any) => t.status === "error");
  const done    = tasks.filter((t: any) => t.status === "done");

  const group = (label: string, list: any[]) => list.length ? (
    <React.Fragment key={label}>
      <div className="tasks-section">
        <span>{label}</span>
        <span className="line" />
        <span className="mono" style={{ color: "var(--muted-2)" }}>{String(list.length).padStart(2, "0")}</span>
      </div>
      {list.map((t: any) => (
        <div key={t.id} className="task" data-status={t.status}>
          <span className="task-dot" />
          <div>
            <div className="task-name">{t.name}</div>
            <div className="task-sub">
              <span className="task-tool">{t.tool}</span>
              {t.status === "running" && (
                <>
                  <span>running…</span>
                  <button className="task-stop" onClick={() => onStop?.(t.id)} aria-label="Stop task">
                    <svg viewBox="0 0 16 16" fill="currentColor"><rect x="4" y="4" width="8" height="8" rx="1.2"/></svg>
                    <span>stop</span>
                  </button>
                </>
              )}
              {t.status === "queued" && (
                <>
                  <span>queued</span>
                  <button className="task-stop" onClick={() => onStop?.(t.id)} aria-label="Cancel task">cancel</button>
                </>
              )}
              {t.status === "done"  && <span>done · {t.time}</span>}
              {t.status === "error" && (
                <>
                  <span style={{ color: "var(--err)" }}>error · {t.error || "failed"}</span>
                  <button className="retry" onClick={() => onRetry?.(t.id)}>retry</button>
                </>
              )}
            </div>
          </div>
        </div>
      ))}
    </React.Fragment>
  ) : null;

  return (
    <aside className="tasks">
      <div className="tasks-resize"
           onMouseDown={onMouseDown}
           onDoubleClick={() => setWidth(340)}
           title="Arraste para redimensionar · duplo-clique para resetar"
           aria-label="Resize tasks panel" />
      <div className="tasks-hd">
        <h3>Background tasks</h3>
        <button className="clear" onClick={onClear}>Clear</button>
      </div>
      <div className="tasks-list">
        {group("Running", running)}
        {group("Queued",  queued)}
        {group("Errors",  errored)}
        {group("Done",    done)}
        {!tasks.length && (
          <div style={{ padding: "24px 12px", color: "var(--muted)", fontSize: 12.5, textAlign: "center" }}>
            No background tasks.<br />They appear here as the agent works.
          </div>
        )}
      </div>
    </aside>
  );
}

// ── Streaming reply ───────────────────────────────────────────────────────────
function buildReply(prompt: string) {
  return [
    { kind: "text", text: "Working through this — let me start by laying out the shape of what you're asking, then walk through the steps." },
    { kind: "tool", tag: "Search", title: `Searched workspace for "${prompt.slice(0, 32)}${prompt.length > 32 ? "…" : ""}"`,
      meta: "12 results", body: "lattice-core/notes/2024-…\nlattice-core/handbook/…\nteam/decisions/…",
      open: false },
    { kind: "text", text: "Here's the gist: I can take this from your prompt and turn it into a working draft, or I can ask one clarifying question first — whichever moves faster for you. **Say the word** and I'll go." },
  ];
}

const TASK_TEMPLATES = [
  { name: "Read project context",         tool: "Read" },
  { name: "Search workspace for matches", tool: "Grep" },
  { name: "Draft response outline",       tool: "Plan" },
];

// ── App ───────────────────────────────────────────────────────────────────────
const TWEAK_DEFAULTS = { dark: false, accent: "#2563eb", density: "regular" };

const INITIAL_ACCOUNT = {
  initials: "ja",
  name: "João Almeida",
  email: "joao@latticelabs.dev",
  workspace: "Lattice Labs",
  plan: "team · pro",
  memberSince: "Mar 2025",
  tz: "America/Sao_Paulo",
  model: "lattice-1 · pro",
  usage: { used: 184_320, cap: 500_000 },
};

const INITIAL_APP_SETTINGS = {
  language: "en",
  soundEnabled: true,
  notificationsEnabled: true,
  autoSave: true,
  model: "lattice-1 · pro",
  creativity: 45,
  maxTokens: 8192,
  showTools: true,
  dark: false,
  compact: false,
  accent: "#2563eb",
};

export function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [convos, setConvos] = useState<any[]>(initialConvos);
  const [activeId, setActiveId] = useState("paperclip");
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(() => typeof window !== "undefined" ? window.innerWidth >= 900 : true);
  const [tasksOpen, setTasksOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [accountMenuRect, setAccountMenuRect] = useState<DOMRect | null>(null);
  const [modelMenuRect, setModelMenuRect] = useState<DOMRect | null>(null);
  const [projMenuRect, setProjMenuRect] = useState<DOMRect | null>(null);
  const [account, setAccount] = useState(INITIAL_ACCOUNT);
  const [appSettings, setAppSettings] = useState(INITIAL_APP_SETTINGS);
  const [artifactId, setArtifactId] = useState<string | null>(null);
  const [view, setView] = useState<{ kind: string; projectId?: string }>({ kind: "chat" });
  const [filePreview, setFilePreview] = useState<any>(null);
  const [convoMenu, setConvoMenu] = useState<{ id: string; rect: DOMRect } | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const threadRef = useRef<HTMLDivElement>(null);

  const active = convos.find((c) => c.id === activeId) || convos[0];

  useEffect(() => {
    document.documentElement.dataset.theme = t.dark ? "dark" : "light";
    document.documentElement.style.setProperty("--accent", t.accent);
  }, [t.dark, t.accent]);

  useEffect(() => {
    if (appSettings.dark !== t.dark) setTweak('dark', appSettings.dark);
    if (appSettings.accent !== t.accent) setTweak('accent', appSettings.accent);
    if (appSettings.compact && t.density !== 'compact') setTweak('density', 'compact');
    if (!appSettings.compact && t.density === 'compact') setTweak('density', 'regular');
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appSettings.dark, appSettings.accent, appSettings.compact]);

  useEffect(() => {
    const ds = t.density === "compact" ? "13px" : t.density === "comfy" ? "15px" : "14px";
    document.body.style.fontSize = ds;
  }, [t.density]);

  useEffect(() => {
    const el = threadRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [active?.messages?.length, streaming]);

  const updateActive = useCallback((patch: (c: any) => any) => {
    setConvos((cs) => cs.map((c) => c.id === activeId ? { ...c, ...patch(c) } : c));
  }, [activeId]);

  const newChat = () => {
    const id = "new-" + Date.now();
    setConvos((cs) => [
      { id, title: "New chat", project: { root: "personal", path: null },
        updatedAt: Date.now(), pinned: false, fresh: true, messages: [], tasks: [] },
      ...cs.filter((c) => c.id !== "new" || c.messages.length > 0),
    ]);
    setActiveId(id);
    setDraft("");
  };

  const send = (payload?: any) => {
    if (payload && payload.stop) { setStreaming(false); return; }
    const text = draft.trim();
    if (!text || streaming) return;

    const userMsg = { id: "u-" + Date.now(), role: "user", text };
    const assistId = "a-" + Date.now();
    const assistMsg = { id: assistId, role: "assistant", blocks: [], streaming: true };
    const t1Id = "tk-" + Date.now() + "-1";
    const t2Id = "tk-" + Date.now() + "-2";
    const t3Id = "tk-" + Date.now() + "-3";

    updateActive((c) => ({
      messages: [...c.messages, userMsg, assistMsg],
      title: c.fresh ? text.slice(0, 38) : c.title,
      fresh: false,
      updatedAt: Date.now(),
      tasks: [
        { id: t1Id, name: TASK_TEMPLATES[0].name, tool: TASK_TEMPLATES[0].tool, status: "running", time: "—" },
        { id: t2Id, name: TASK_TEMPLATES[1].name, tool: TASK_TEMPLATES[1].tool, status: "queued",  time: "—" },
        { id: t3Id, name: TASK_TEMPLATES[2].name, tool: TASK_TEMPLATES[2].tool, status: "queued",  time: "—" },
        ...c.tasks,
      ],
    }));

    setDraft("");
    setStreaming(true);
    const targetConvoId = activeId;
    const reply = buildReply(text);

    let i = 0;
    const tick = () => {
      if (i >= reply.length) {
        setConvos((cs) => cs.map((c) => {
          if (c.id !== targetConvoId) return c;
          return {
            ...c,
            messages: c.messages.map((m: any) => m.id === assistId ? { ...m, streaming: false } : m),
            tasks: c.tasks.map((tk: any) =>
              tk.id === t1Id ? { ...tk, status: "done", time: "0.4s" } :
              tk.id === t2Id ? { ...tk, status: "done", time: "0.7s" } :
              tk.id === t3Id ? { ...tk, status: "done", time: "0.3s" } : tk),
          };
        }));
        setStreaming(false);
        return;
      }
      const block = reply[i++];
      setConvos((cs) => cs.map((c) => {
        if (c.id !== targetConvoId) return c;
        return {
          ...c,
          messages: c.messages.map((m: any) =>
            m.id === assistId ? { ...m, blocks: [...m.blocks, block] } : m),
          tasks: c.tasks.map((tk: any) => {
            if (tk.id === t1Id && i === 1) return { ...tk, status: "done", time: "0.4s" };
            if (tk.id === t2Id && i === 1) return { ...tk, status: "running" };
            if (tk.id === t2Id && i === 2) return { ...tk, status: "done", time: "0.7s" };
            if (tk.id === t3Id && i === 2) return { ...tk, status: "running" };
            return tk;
          }),
        };
      }));
      setTimeout(tick, 700 + Math.random() * 500);
    };
    setTimeout(tick, 450);
  };

  const onClearTasks = () => updateActive(() => ({ tasks: [] }));

  const renameConvo = (id: string, title: string) => {
    setConvos((cs) => cs.map((c) => c.id === id ? { ...c, title } : c));
  };
  const archiveConvo = (id: string) => {
    setConvos((cs) => cs.map((c) => c.id === id ? { ...c, archived: !c.archived, pinned: false } : c));
    if (id === activeId) {
      const next = convos.find((c) => c.id !== id && !c.archived);
      if (next) setActiveId(next.id);
    }
  };
  const togglePin = (id: string) => {
    setConvos((cs) => cs.map((c) => c.id === id ? { ...c, pinned: !c.pinned, archived: false } : c));
  };
  const deleteConvo = (id: string) => {
    setConvos((cs) => {
      const next = cs.filter((c) => c.id !== id);
      if (id === activeId && next.length) setActiveId(next[0].id);
      return next;
    });
  };
  const onRetryTask = (taskId: string) => {
    updateActive((c) => ({
      tasks: c.tasks.map((tk: any) => tk.id === taskId ? { ...tk, status: "running", error: undefined } : tk),
    }));
    setTimeout(() => {
      updateActive((c) => ({
        tasks: c.tasks.map((tk: any) => tk.id === taskId ? { ...tk, status: "done", time: "1.1s" } : tk),
      }));
    }, 1200);
  };
  const onStopTask = (taskId: string) => {
    updateActive((c) => ({
      tasks: c.tasks.map((tk: any) => tk.id === taskId
        ? { ...tk, status: "error", error: "stopped", time: "—" }
        : tk),
    }));
  };

  const openAccount  = () => { setAccountOpen(false); setView({ kind: "account" }); };
  const openSettings = () => { setAccountOpen(false); setView({ kind: "settings" }); };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      if (!mod) return;
      if (e.key === "k" || e.key === "K") { e.preventDefault(); setSearchOpen((v) => !v); }
      else if (e.key === "n" || e.key === "N") { e.preventDefault(); newChat(); }
      else if (e.key === ",")               { e.preventDefault(); openSettings(); }
      else if (e.key === "b" || e.key === "B") { e.preventDefault(); setSidebarOpen((v) => !v); }
      else if (e.key === "j" || e.key === "J") { e.preventDefault(); setTasksOpen((v) => !v); }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const tokens = useMemo(() => {
    if (!active) return "0";
    const total = active.messages.reduce((n: number, m: any) => {
      if (m.role === "user") return n + (m.text?.length || 0);
      return n + (m.blocks || []).reduce((nn: number, b: any) => nn + (b.text || b.body || "").length, 0);
    }, 0);
    return (total / 4).toFixed(0) || "0";
  }, [active?.messages]);

  return (
    <div className="app"
         data-sidebar={sidebarOpen ? "open" : "closed"}
         data-tasks={tasksOpen ? "open" : "closed"}
         data-art={(artifactId || filePreview) ? "open" : "closed"}
         data-screen-label="Lattice Desktop">
      <Sidebar
        convos={convos}
        activeId={activeId}
        onSelect={(id: string) => { setActiveId(id); setView({ kind: "chat" }); if (window.innerWidth < 900) setSidebarOpen(false); }}
        onNew={() => { newChat(); setView({ kind: "chat" }); if (window.innerWidth < 900) setSidebarOpen(false); }}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
        onOpenAccount={openAccount}
        onOpenSettings={openSettings}
        onOpenSearch={() => setSearchOpen(true)}
        onOpenProjects={() => setView({ kind: "projects" })}
        onOpenKnowledge={() => setView({ kind: "knowledge" })}
        onOpenHistory={() => setView({ kind: "history" })}
        onOpenArchive={() => setView({ kind: "archive" })}
        onOpenConnectors={() => setView({ kind: "connectors" })}
        currentView={view.kind}
        onOpenAccountMenu={setAccountMenuRect}
        onConvoMenu={(id: string, rect: DOMRect) => setConvoMenu({ id, rect })}
        onRenameConvo={renameConvo}
        editingId={editingId}
        setEditingId={setEditingId}
        account={account}
      />
      <div className="mobile-backdrop"
           onClick={() => { setSidebarOpen(false); setTasksOpen(false); setArtifactId(null); }} />

      <main className="main">
        {view.kind !== "chat" ? (
          <>
            {view.kind === "projects" && (
              <ProjectsView
                convos={convos}
                onOpenProject={(id: string) => setView({ kind: "project", projectId: id })}
                onNewProject={() => {}}
              />
            )}
            {view.kind === "project" && (
              <ProjectDetailView
                projectId={view.projectId ?? ''}
                convos={convos}
                onBack={() => setView({ kind: "projects" })}
                onOpenChat={(id: string) => { setActiveId(id); setView({ kind: "chat" }); }}
                onOpenFile={(fr: any) => setFilePreview(fr)}
              />
            )}
            {view.kind === "knowledge" && (
              <KnowledgeView onOpenFile={(fr: any) => setFilePreview(fr)} />
            )}
            {view.kind === "history" && (
              <HistoryView
                convos={convos}
                onOpenChat={(id: string) => { setActiveId(id); setView({ kind: "chat" }); }}
                onArchive={archiveConvo}
                onDelete={deleteConvo}
              />
            )}
            {view.kind === "archive" && (
              <HistoryView
                convos={convos}
                archivedOnly={true}
                onOpenChat={(id: string) => { setActiveId(id); setView({ kind: "chat" }); }}
                onArchive={archiveConvo}
                onDelete={deleteConvo}
              />
            )}
            {view.kind === "connectors" && (
              <ConnectorsView onOpenSettings={openSettings} />
            )}
            {view.kind === "skills" && (
              <SkillsView />
            )}
            {view.kind === "settings" && (
              <SettingsView
                settings={appSettings}
                onChange={(patch) => setAppSettings((s) => ({ ...s, ...patch }))}
              />
            )}
            {view.kind === "account" && (
              <MyAccountView
                account={account}
                onChange={(patch) => setAccount((a) => ({ ...a, ...patch }))}
              />
            )}
          </>
        ) : (
          <>
            <Breadcrumb
              convo={active}
              onToggleSidebar={() => setSidebarOpen((v) => !v)}
              onToggleTasks={() => setTasksOpen((v) => !v)}
              sidebarOpen={sidebarOpen}
              tasksOpen={tasksOpen}
              onOpenProjectMenu={setProjMenuRect}
            />

            {active.messages.length === 0 ? (
              <div className="empty-shell">
                <EmptyHome onPick={(p: string) => setDraft(p)}>
                  <Composer
                    value={draft}
                    onChange={setDraft}
                    onSend={() => send()}
                    disabled={streaming}
                    tokens={tokens}
                    model={appSettings.model}
                    onPickModel={setModelMenuRect}
                    rotatePlaceholder={true}
                  />
                </EmptyHome>
              </div>
            ) : (
              <>
                <div className="thread" ref={threadRef}>
                  <div className="thread-inner">
                    {active.messages.map((m: any) => (
                      <Message key={m.id} m={m} streaming={m.streaming}
                               onRegen={() => {}}
                               onOpenArtifact={(id: string) => setArtifactId(id)} />
                    ))}
                  </div>
                </div>
                <Composer
                  value={draft}
                  onChange={setDraft}
                  onSend={() => send()}
                  disabled={streaming}
                  tokens={tokens}
                  model={appSettings.model}
                  onPickModel={setModelMenuRect}
                  rotatePlaceholder={false}
                  staticPlaceholder="Reply…"
                />
              </>
            )}
          </>
        )}
      </main>

      <TasksPanel tasks={active?.tasks || []} onClear={onClearTasks} onRetry={onRetryTask} onStop={onStopTask}
                  tasksOpen={tasksOpen && !artifactId && !filePreview && view.kind === "chat"} />

      {artifactId && (
        <ArtifactPanel
          artifact={ARTIFACTS_SAMPLE[artifactId as keyof typeof ARTIFACTS_SAMPLE]}
          onClose={() => setArtifactId(null)}
        />
      )}

      {filePreview && (
        <FileViewerPanel
          file={filePreview}
          onClose={() => setFilePreview(null)}
        />
      )}

      <MyAccountModal
        open={accountOpen}
        onClose={() => setAccountOpen(false)}
        account={account}
        onChange={(patch) => setAccount((a) => ({ ...a, ...patch }))}
      />
      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={appSettings}
        onChange={(patch) => setAppSettings((s) => ({ ...s, ...patch }))}
      />
      <SearchPalette
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        convos={convos}
        onPick={(id: string) => { setActiveId(id); setView({ kind: "chat" }); }}
      />
      <ProjectsModal open={false} onClose={() => {}} />
      <KnowledgeModal open={false} onClose={() => {}} />

      <Menu
        open={!!convoMenu}
        onClose={() => setConvoMenu(null)}
        anchorRect={convoMenu?.rect}
        width={210}
        align="left"
        items={convoMenu ? (() => {
          const c = convos.find((cv) => cv.id === convoMenu.id);
          if (!c) return [];
          return [
            { label: "Rename", kbd: "↵",
              icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"><path d="M11 2l3 3-8 8H3v-3l8-8z"/></svg>,
              onClick: () => setEditingId(c.id) },
            { label: c.pinned ? "Unpin" : "Pin",
              icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M8 14v-4M5 10h6M6 3l4 0 .5 7h-5z"/></svg>,
              onClick: () => togglePin(c.id) },
            { label: c.archived ? "Unarchive" : "Archive",
              icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"><rect x="2" y="3" width="12" height="3" rx=".5"/><path d="M3 6v7a1 1 0 001 1h8a1 1 0 001-1V6M6.5 9h3"/></svg>,
              onClick: () => archiveConvo(c.id) },
            { divider: true },
            { label: "Delete", danger: true,
              icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round"><path d="M3 4h10M6 4V2.5h4V4M5 4l.5 9.5a1 1 0 001 1h3a1 1 0 001-1L11 4M7 7v5M9 7v5"/></svg>,
              onClick: () => {
                if (confirm(`Delete "${c.title}"? This can't be undone.`)) deleteConvo(c.id);
              } },
          ];
        })() : []}
      />

      <Menu
        open={!!accountMenuRect}
        onClose={() => setAccountMenuRect(null)}
        anchorRect={accountMenuRect}
        width={240}
        items={[
          { section: account.email },
          { label: "Minha conta", onClick: openAccount,
            icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><circle cx="8" cy="6" r="2.5"/><path d="M3 13a5 5 0 0110 0"/></svg> },
          { label: "Archive", onClick: () => setView({ kind: "archive" }),
            icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"><rect x="2" y="3" width="12" height="3" rx=".5"/><path d="M3 6v7a1 1 0 001 1h8a1 1 0 001-1V6M6.5 9h3" strokeLinecap="round"/></svg> },
          { label: "Connectors", onClick: () => setView({ kind: "connectors" }),
            icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M6 2v3M10 2v3M4 5h8v3a4 4 0 01-8 0V5zM8 12v2"/></svg> },
          { label: "Skills", onClick: () => setView({ kind: "skills" }),
            icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M8 2l1.8 3.6 4 .6-2.9 2.8.7 4-3.6-1.9-3.6 1.9.7-4L2.2 6.2l4-.6z"/></svg> },
          { label: "Configurações", kbd: "⇧⌃,", onClick: openSettings,
            icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"><circle cx="8" cy="8" r="2"/><path d="M8 2v1.5M8 12.5V14M2 8h1.5M12.5 8H14M4.4 4.4l1.1 1.1M10.5 10.5l1.1 1.1M11.6 4.4l-1.1 1.1M5.5 10.5l-1.1 1.1" strokeLinecap="round"/></svg> },
          { divider: true },
          { label: "Sair", danger: true,
            icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M10 4V3a1 1 0 00-1-1H3a1 1 0 00-1 1v10a1 1 0 001 1h6a1 1 0 001-1v-1"/><path d="M14 8H6m8 0l-2.5-2.5M14 8l-2.5 2.5"/></svg> },
        ]}
      />

      <Menu
        open={!!modelMenuRect}
        onClose={() => setModelMenuRect(null)}
        anchorRect={modelMenuRect}
        width={260}
        items={[
          { section: "Model" },
          ...["lattice-1 · fast", "lattice-1 · pro", "lattice-1 · max"].map((m) => ({
            label: m, check: appSettings.model === m,
            onClick: () => setAppSettings((s) => ({ ...s, model: m })),
          })),
          { divider: true },
          { label: "More settings…", kbd: "⌘,", onClick: openSettings },
        ]}
      />

      <Menu
        open={!!projMenuRect}
        onClose={() => setProjMenuRect(null)}
        anchorRect={projMenuRect}
        width={260}
        align="left"
        items={[
          { section: "Project" },
          ...convos.slice(0, 5).map((c) => ({
            label: c.project.root + (c.project.path ? ` / ${c.project.path}` : ""),
            check: c.id === activeId,
            onClick: () => setActiveId(c.id),
            icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"><path d="M2 4.5A1.5 1.5 0 013.5 3h2.7l1.3 1.3h5A1.5 1.5 0 0114 5.8v5.7A1.5 1.5 0 0112.5 13h-9A1.5 1.5 0 012 11.5v-7z"/></svg>,
          })),
          { divider: true },
          { label: "All projects", onClick: () => setView({ kind: "projects" }) },
        ]}
      />

      <TweaksPanel>
        <TweakSection label="Appearance" />
        <TweakToggle label="Dark mode" value={t.dark} onChange={(v: boolean) => setTweak('dark', v)} />
        <TweakColor
          label="Accent"
          value={t.accent}
          options={['#2563eb', '#16a34a', '#9333ea', '#dc2626', '#0d9488', '#ea580c']}
          onChange={(v: string | string[]) => setTweak('accent', v as string)}
        />
        <TweakSection label="Layout" />
        <TweakRadio
          label="Density"
          value={t.density}
          options={['compact', 'regular', 'comfy']}
          onChange={(v: string) => setTweak('density', v)}
        />
        <TweakToggle label="Sidebar" value={sidebarOpen} onChange={setSidebarOpen} />
        <TweakToggle label="Tasks panel" value={tasksOpen} onChange={setTasksOpen} />
      </TweaksPanel>
    </div>
  );
}
