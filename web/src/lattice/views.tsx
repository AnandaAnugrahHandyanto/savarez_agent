// views.tsx — full-screen views inside <main>: Projects, ProjectDetail, Knowledge, History, Archive
import React, { useState, useEffect, useMemo } from 'react';
import { cn, InlineEditable, Tooltip } from './primitives';

// ── Shared chrome ─────────────────────────────────────────────────────────────
interface ViewHeaderProps {
  icon?: React.ReactNode;
  title: React.ReactNode;
  subtitle?: string;
  actions?: React.ReactNode;
  children?: React.ReactNode;
}

export function ViewHeader({ icon, title, subtitle, actions, children }: ViewHeaderProps) {
  return (
    <div className="view-hd">
      <div className="view-hd-main">
        {icon && <span className="view-hd-icon">{icon}</span>}
        <div className="view-hd-meta">
          <div className="view-hd-title">{title}</div>
          {subtitle && <div className="view-hd-sub">{subtitle}</div>}
        </div>
      </div>
      {actions && <div className="view-hd-actions">{actions}</div>}
      {children}
    </div>
  );
}

interface ViewTabItem {
  id: string;
  label: string;
  count?: number;
}

interface ViewTabsProps {
  tabs: ViewTabItem[];
  active: string;
  onChange: (id: string) => void;
}

export function ViewTabs({ tabs, active, onChange }: ViewTabsProps) {
  return (
    <div className="view-tabs">
      {tabs.map((t) => (
        <button key={t.id}
                className={cn('view-tab', active === t.id && 'is-active')}
                onClick={() => onChange(t.id)}>
          {t.label}
          {t.count != null && <span className="view-tab-count mono">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

// ── Sample knowledge per project ──────────────────────────────────────────────
export const PROJECT_KNOWLEDGE: Record<string, Array<{id: string; name: string; kind: string; size: string; updated: string; status: string}>> = {
  'paperclip-master': [
    { id: 'k1', name: 'Verification gate RFC.pdf',     kind: 'pdf',  size: '182 KB', updated: '2d ago', status: 'indexed' },
    { id: 'k2', name: 'Tool governance spec.md',        kind: 'md',   size: '14 KB',  updated: '5h ago', status: 'indexed' },
    { id: 'k3', name: 'Migration runbook.docx',         kind: 'doc',  size: '32 KB',  updated: '1w ago', status: 'indexed' },
    { id: 'k4', name: 'Architecture diagram.png',       kind: 'img',  size: '412 KB', updated: '3d ago', status: 'indexed' },
    { id: 'k5', name: 'Postgres harness notes.txt',     kind: 'txt',  size: '4 KB',   updated: '12h ago', status: 'indexed' },
    { id: 'k6', name: 'API errors.csv',                  kind: 'doc',  size: '8 KB',   updated: '1h ago', status: 'indexing' },
  ],
  'marketing': [
    { id: 'k1', name: 'Brand voice guidelines.pdf',     kind: 'pdf',  size: '1.2 MB', updated: '2w ago', status: 'indexed' },
    { id: 'k2', name: 'Competitor scan.md',             kind: 'md',   size: '22 KB',  updated: '5d ago', status: 'indexed' },
    { id: 'k3', name: 'Pricing experiment Q2.csv',      kind: 'doc',  size: '11 KB',  updated: '1w ago', status: 'indexed' },
  ],
  'planning':      [{ id: 'k1', name: 'Q2 retrospective.md', kind: 'md', size: '8 KB',  updated: '3d ago', status: 'indexed' }],
  'lattice-core':  [{ id: 'k1', name: 'Typebox migration plan.md', kind: 'md', size: '12 KB', updated: 'Today', status: 'indexed' }],
  'personal':      [],
};

export const PROJECT_META: Record<string, { name: string; desc: string; color: string; icon: string }> = {
  'paperclip-master': { name: 'paperclip-master', desc: 'Verification gate + tool governance',     color: '#5B8CFF', icon: '🛡' },
  'marketing':        { name: 'marketing',        desc: 'Hero copy, pricing, blog drafts',         color: '#D94A6B', icon: '✦'  },
  'planning':         { name: 'planning',         desc: 'Q3 OKRs, roadmap discussions',            color: '#E08658', icon: '◐'  },
  'lattice-core':     { name: 'lattice-core',     desc: 'Types, migrations, schema work',          color: '#2EA47A', icon: '▣'  },
  'personal':         { name: 'personal',         desc: 'Notes, drafts, scratch',                  color: '#8B5CF6', icon: '•'  },
};

function projectInstructionsDefault(id: string): string {
  return ({
    'paperclip-master': 'You are a senior backend engineer reviewing changes against the verification-gate envelope. Always cite the exact stage and tool when reasoning. Prefer integration tests over unit. Default to TypeScript + Drizzle.',
    'marketing':        'You are a senior copywriter for a technical product. Keep headlines under 8 words. Avoid jargon, hype, and emoji. When asked for variants, give three angles (outcome, contrast, craft).',
    'planning':         'You help structure quarterly objectives. Always ask for the baseline metric before proposing an OKR. Prefer 3 objectives with 2-3 KRs each.',
    'lattice-core':     'You are a careful TypeScript engineer. Preserve public API shapes structurally. Prefer codegen and schema-first patterns.',
    'personal':         'You are a thoughtful assistant for personal notes, drafts, and scratch work. Be concise.',
  } as Record<string, string>)[id] || '';
}

function fileIcon(kind: string) {
  const c: Record<string, { tint: string; path: React.ReactNode }> = {
    pdf: { tint: '#D94A6B', path: <><path d="M5 2h6l3 3v9a1 1 0 01-1 1H5a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M11 2v3h3"/></> },
    md:  { tint: '#2EA47A', path: <><path d="M5 2h6l3 3v9a1 1 0 01-1 1H5a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M11 2v3h3M6 8v3M6 8l1 1.5L8 8M9.5 8v3M9.5 11l1-1 1 1"/></> },
    doc: { tint: '#5B8CFF', path: <><path d="M5 2h6l3 3v9a1 1 0 01-1 1H5a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M11 2v3h3M6 8h5M6 10h5M6 12h3"/></> },
    txt: { tint: '#8B5CF6', path: <><path d="M5 2h6l3 3v9a1 1 0 01-1 1H5a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M11 2v3h3M6 8h5M6 10h5M6 12h3"/></> },
    img: { tint: '#E08658', path: <><rect x="3" y="3" width="11" height="11" rx="1"/><circle cx="6.5" cy="6.5" r="1.2"/><path d="M3 11l3-3 3 2.5L11 9l3 3"/></> },
  };
  const item = c[kind] || { tint: '#9CA3AF', path: <path d="M5 2h6l3 3v9a1 1 0 01-1 1H5a1 1 0 01-1-1V3a1 1 0 011-1z"/> };
  return (
    <span className="file-icon" style={{ color: item.tint }}>
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round">{item.path}</svg>
    </span>
  );
}

// ── ProjectsView ──────────────────────────────────────────────────────────────
interface Convo {
  id: string;
  title: string;
  project: { root: string; path: string | null };
  updatedAt: number;
  archived?: boolean;
  messages?: any[];
  [key: string]: any;
}

interface ProjectsViewProps {
  convos: Convo[];
  onOpenProject: (id: string) => void;
  onNewProject: () => void;
}

export function ProjectsView({ convos, onOpenProject, onNewProject }: ProjectsViewProps) {
  const projectStats = useMemo(() => {
    const m: Record<string, { chats: number; updated: number }> = {};
    convos.forEach((c) => {
      const k = c.project.root;
      m[k] = m[k] || { chats: 0, updated: 0 };
      m[k].chats++;
      m[k].updated = Math.max(m[k].updated, c.updatedAt);
    });
    return m;
  }, [convos]);

  return (
    <div className="view">
      <ViewHeader
        title="Projects"
        subtitle="Lugares onde você trabalha"
        actions={
          <button className="btn primary btn-sm" onClick={onNewProject}>
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><path d="M8 3v10M3 8h10"/></svg>
            <span>New project</span>
          </button>
        }
      />
      <div className="view-body view-body-scroll">
        <div className="proj-grid">
          {Object.entries(PROJECT_META).map(([id, p]) => {
            const stats = projectStats[id] || { chats: 0, updated: 0 };
            return (
              <button key={id} className="proj-card" onClick={() => onOpenProject(id)}>
                <span className="proj-card-meta">
                  <span className="proj-card-name">{p.name}</span>
                  <span className="proj-card-desc">{p.desc}</span>
                </span>
                <span className="proj-card-stats mono">
                  <span>{stats.chats} chats</span>
                  <span className="muted">· {PROJECT_KNOWLEDGE[id]?.length || 0} sources</span>
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── ProjectDetailView ─────────────────────────────────────────────────────────
interface ProjectDetailViewProps {
  projectId: string;
  convos: Convo[];
  onBack: () => void;
  onOpenChat: (id: string) => void;
  onOpenFile: (fr: { projectId: string; fileId: string }) => void;
}

export function ProjectDetailView({ projectId, convos, onBack, onOpenChat, onOpenFile }: ProjectDetailViewProps) {
  const [tab, setTab] = useState('chats');
  const [instructions, setInstructions] = useState(projectInstructionsDefault(projectId));
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const p = PROJECT_META[projectId];
  if (!p) return null;
  const chats = convos.filter((c) => c.project.root === projectId && !c.archived);
  const knowledge = PROJECT_KNOWLEDGE[projectId] || [];

  const saveInstructions = (val: string) => {
    setInstructions(val);
    setSavedAt(new Date());
  };

  return (
    <div className="view">
      <ViewHeader
        title={<InlineEditable value={p.name} onChange={() => {}} />}
        subtitle={p.desc}
        actions={
          <button className="btn btn-sm" onClick={onBack} style={{ position: 'absolute', right: 32, top: 18 }}>
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M10 4l-4 4 4 4"/></svg>
            <span>Back</span>
          </button>
        }
      >
        <ViewTabs
          tabs={[
            { id: 'chats',        label: 'Chats',        count: chats.length },
            { id: 'knowledge',    label: 'Knowledge',    count: knowledge.length },
            { id: 'instructions', label: 'Instructions' },
            { id: 'settings',     label: 'Settings' },
          ]}
          active={tab}
          onChange={setTab}
        />
      </ViewHeader>

      <div className="view-body view-body-scroll">
        {tab === 'chats' && (
          <div className="proj-chats">
            {chats.length === 0 ? (
              <div className="view-empty">
                <h3>No chats yet in this project</h3>
                <p>Start a new chat scoped to <strong>{p.name}</strong>. All knowledge and instructions will apply automatically.</p>
                <button className="btn primary btn-sm">+ New chat in {p.name}</button>
              </div>
            ) : (
              <ul className="proj-chat-list">
                {chats.map((c) => (
                  <li key={c.id}>
                    <button className="proj-chat-row" onClick={() => onOpenChat(c.id)}>
                      <span className="proj-chat-title">{c.title}</span>
                      <span className="proj-chat-snip">{(c.messages?.[0]?.text || '').slice(0, 84)}{(c.messages?.[0]?.text?.length || 0) > 84 ? '…' : ''}</span>
                      <span className="proj-chat-time mono">{relTimeShort(c.updatedAt)}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {tab === 'knowledge' && (
          <KnowledgeInline projectId={projectId} onOpenFile={onOpenFile} />
        )}

        {tab === 'instructions' && (
          <div className="proj-instructions">
            <p className="proj-instructions-help">
              These instructions are sent at the start of every chat in this project. Use them to define the agent&apos;s role, voice, and constraints.
            </p>
            <textarea
              className="proj-instructions-input"
              value={instructions}
              onChange={(e) => saveInstructions(e.target.value)}
              placeholder="You are a senior engineer reviewing changes against…"
            />
            <div className="proj-instructions-foot mono">
              {savedAt ? `Saved · ${savedAt.toLocaleTimeString()}` : 'Auto-saves as you type'}
              <span className="muted"> · {instructions.length} chars</span>
            </div>
          </div>
        )}

        {tab === 'settings' && (
          <div className="proj-settings">
            <div className="set-row"><div><div className="set-label">Default model</div><div className="set-hint">Used when no override per chat.</div></div>
              <select className="set-select" defaultValue="lattice-1 · pro">
                <option>lattice-1 · fast</option><option>lattice-1 · pro</option><option>lattice-1 · max</option>
              </select>
            </div>
            <div className="set-row"><div><div className="set-label">Auto-archive after</div><div className="set-hint">Chats with no activity are archived.</div></div>
              <select className="set-select" defaultValue="30">
                <option value="0">Never</option><option value="7">7 days</option><option value="30">30 days</option><option value="90">90 days</option>
              </select>
            </div>
            <div className="set-row"><div><div className="set-label">Share with workspace</div><div className="set-hint">Everyone can view chats in this project.</div></div>
              <button className="switch" aria-checked={false} role="switch"><span className="thumb"/></button>
            </div>
            <div className="set-row danger-row">
              <div><div className="set-label" style={{ color: 'var(--err)' }}>Delete project</div><div className="set-hint">Removes all chats and knowledge. Cannot be undone.</div></div>
              <button className="btn btn-sm danger">Delete project</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── KnowledgeInline ───────────────────────────────────────────────────────────
interface KnowledgeInlineProps {
  projectId: string;
  onOpenFile?: (fr: { projectId: string; fileId: string }) => void;
  allowUpload?: boolean;
}

export function KnowledgeInline({ projectId, onOpenFile, allowUpload = true }: KnowledgeInlineProps) {
  const items = PROJECT_KNOWLEDGE[projectId] || [];
  const [dragOver, setDragOver] = useState(false);

  return (
    <div className="kn-pane">
      {allowUpload && (
        <div className={cn('kn-drop', dragOver && 'is-over')}
             onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
             onDragLeave={() => setDragOver(false)}
             onDrop={(e) => { e.preventDefault(); setDragOver(false); }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 4v10M8 8l4-4 4 4M5 19h14"/>
          </svg>
          <div>
            <div className="kn-drop-title">Drag files here to index</div>
            <div className="kn-drop-sub">PDF, DOCX, MD, TXT, CSV, PNG/JPG · up to 25 MB each · or <button className="link">select</button></div>
          </div>
        </div>
      )}
      {items.length === 0 ? (
        <div className="view-empty"><h3>No sources</h3><p>Add a file to get started.</p></div>
      ) : (
        <ul className="kn-files">
          {items.map((f) => (
            <li key={f.id}>
              <button className="kn-file" onClick={() => onOpenFile?.({ projectId, fileId: f.id })}>
                {fileIcon(f.kind)}
                <span className="kn-file-meta">
                  <span className="kn-file-name">{f.name}</span>
                  <span className="kn-file-sub mono">{f.size} · {f.updated}</span>
                </span>
                {f.status === 'indexing' ? (
                  <span className="kn-status indexing">indexing…</span>
                ) : (
                  <span className="kn-status indexed">indexed</span>
                )}
                <span className="kn-file-actions">
                  <button className="icon-btn" aria-label="Re-sync"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M3 8a5 5 0 019-3M13 8a5 5 0 01-9 3M11 5h2V3M5 11H3v2"/></svg></button>
                  <button className="icon-btn" aria-label="More"><svg viewBox="0 0 16 16" fill="currentColor"><circle cx="3.5" cy="8" r="1.2"/><circle cx="8" cy="8" r="1.2"/><circle cx="12.5" cy="8" r="1.2"/></svg></button>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ── KnowledgeView ─────────────────────────────────────────────────────────────
interface KnowledgeViewProps {
  onOpenFile?: (fr: { projectId: string; fileId: string }) => void;
}

export function KnowledgeView({ onOpenFile }: KnowledgeViewProps) {
  const all = useMemo(() => {
    const list: Array<{id: string; name: string; kind: string; size: string; updated: string; status: string; projectId: string}> = [];
    Object.entries(PROJECT_KNOWLEDGE).forEach(([pid, items]) => {
      items.forEach((f) => list.push({ ...f, projectId: pid }));
    });
    return list.sort((a, b) => a.name.localeCompare(b.name));
  }, []);
  const [q, setQ] = useState('');
  const filtered = q ? all.filter((f) => f.name.toLowerCase().includes(q.toLowerCase())) : all;

  return (
    <div className="view">
      <ViewHeader
        title="Knowledge"
        subtitle={`${all.length} sources in ${Object.keys(PROJECT_KNOWLEDGE).length} projects`}
        actions={<button className="btn primary btn-sm">+ Upload</button>}
      >
        <div className="view-search">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M13.5 13.5L10.5 10.5" strokeLinecap="round"/></svg>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search files…" />
        </div>
      </ViewHeader>
      <div className="view-body view-body-scroll">
        <ul className="kn-files">
          {filtered.map((f) => (
            <li key={f.projectId + f.id}>
              <button className="kn-file" onClick={() => onOpenFile?.({ projectId: f.projectId, fileId: f.id })}>
                {fileIcon(f.kind)}
                <span className="kn-file-meta">
                  <span className="kn-file-name">{f.name}</span>
                  <span className="kn-file-sub mono">{PROJECT_META[f.projectId]?.name} · {f.size} · {f.updated}</span>
                </span>
                <span className="kn-status indexed">indexed</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

// ── FileViewerPanel ───────────────────────────────────────────────────────────
interface FileViewerPanelProps {
  file: { projectId: string; fileId: string } | null;
  onClose: () => void;
}

export function FileViewerPanel({ file, onClose }: FileViewerPanelProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  if (!file) return null;
  const meta = PROJECT_KNOWLEDGE[file.projectId]?.find((f) => f.id === file.fileId);
  if (!meta) return null;

  return (
    <aside className="art-panel file-viewer">
      <div className="art-hd">
        <div className="art-hd-meta">
          <span className="art-hd-title">{meta.name}</span>
          <span className="art-hd-sub mono">{meta.size} · {meta.updated}</span>
        </div>
        <div className="art-hd-actions">
          <Tooltip label="Download" side="bottom"><button className="icon-btn"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M8 2v8M5 7l3 3 3-3M3 13h10"/></svg></button></Tooltip>
          <Tooltip label="Re-sync" side="bottom"><button className="icon-btn"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M3 8a5 5 0 019-3M13 8a5 5 0 01-9 3M11 5h2V3M5 11H3v2"/></svg></button></Tooltip>
          <Tooltip label="Close  Esc" side="bottom"><button className="icon-btn" onClick={onClose}><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><path d="M4 4l8 8M12 4l-8 8"/></svg></button></Tooltip>
        </div>
      </div>
      <div className="art-body">
        {meta.kind === 'pdf' && (
          <div className="fv-placeholder">
            <div className="fv-page">
              <div className="fv-page-h1">{meta.name.replace(/\.\w+$/, '')}</div>
              <div className="fv-page-line" style={{ width: '82%' }} />
              <div className="fv-page-line" style={{ width: '94%' }} />
              <div className="fv-page-line" style={{ width: '76%' }} />
              <div className="fv-page-line" style={{ width: '88%' }} />
              <div className="fv-page-line" style={{ width: '60%' }} />
              <div className="fv-page-h2">Section 1</div>
              <div className="fv-page-line" style={{ width: '90%' }} />
              <div className="fv-page-line" style={{ width: '78%' }} />
              <div className="fv-page-line" style={{ width: '84%' }} />
              <div className="fv-page-line" style={{ width: '70%' }} />
            </div>
          </div>
        )}
        {meta.kind === 'md' && (
          <div className="art-md">
            <h1>{meta.name.replace(/\.\w+$/, '')}</h1>
            <p>This is a preview of <em>{meta.name}</em>. In a real build, the markdown source would be rendered here with full formatting.</p>
            <h2>Overview</h2>
            <p>The agent has indexed this file and can reference it when answering questions within this project.</p>
            <blockquote>Indexed · {meta.size} · last updated {meta.updated}</blockquote>
          </div>
        )}
        {meta.kind === 'txt' && (
          <pre className="art-code">{`# ${meta.name}\n\n(plain text preview)\n\nThis file is indexed and searchable within the project.\nDrop in changes anytime — the agent will pick them up on next sync.`}</pre>
        )}
        {meta.kind === 'img' && (
          <div className="fv-image">
            <div className="fv-image-placeholder" style={{ background: `linear-gradient(135deg, ${PROJECT_META[file.projectId]?.color || '#5B8CFF'} 0%, #ffffff 100%)` }}>
              {meta.name}
            </div>
          </div>
        )}
        {meta.kind === 'doc' && (
          <div className="fv-placeholder"><div className="fv-page">
            <div className="fv-page-h1">{meta.name}</div>
            <div className="fv-page-table">
              {Array.from({ length: 6 }).map((_, r) => (
                <div key={r} className="fv-page-row">
                  {Array.from({ length: 4 }).map((__, c) => <span key={c} className="fv-page-cell" />)}
                </div>
              ))}
            </div>
          </div></div>
        )}
      </div>
      <div className="art-foot">
        <span className="mono muted">{meta.kind.toUpperCase()} · {meta.status}</span>
        <span className="mono muted">{PROJECT_META[file.projectId]?.name}</span>
      </div>
    </aside>
  );
}

// ── HistoryView ───────────────────────────────────────────────────────────────
function relTimeShort(ts: number): string {
  const NOW = Date.now();
  const d = Math.max(1, Math.round((NOW - ts) / 60_000));
  if (d < 60) return `${d}m`;
  const h = Math.round(d / 60);
  if (h < 24) return `${h}h`;
  const days = Math.round(h / 24);
  if (days < 30) return `${days}d`;
  return `${Math.round(days/30)}mo`;
}

interface HistoryViewProps {
  convos: Convo[];
  onOpenChat: (id: string) => void;
  onArchive: (id: string) => void;
  onDelete: (id: string) => void;
  archivedOnly?: boolean;
}

export function HistoryView({ convos, onOpenChat, onArchive, onDelete, archivedOnly = false }: HistoryViewProps) {
  const [q, setQ] = useState('');
  const [projectFilter, setProjectFilter] = useState('');
  const [range, setRange] = useState('all');
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [hasArt, setHasArt] = useState(false);

  const NOW = Date.now();
  const cutoff = range === 'today' ? NOW - 24*3600_000
              : range === 'week'  ? NOW - 7*24*3600_000
              : range === 'month' ? NOW - 30*24*3600_000
              : 0;

  const rows = useMemo(() => convos.filter((c) => {
    if (archivedOnly ? !c.archived : c.archived) return false;
    if (q && !c.title.toLowerCase().includes(q.toLowerCase())) return false;
    if (projectFilter && c.project.root !== projectFilter) return false;
    if (cutoff && c.updatedAt < cutoff) return false;
    if (hasArt && !c.messages?.some((m: any) => m.blocks?.some?.((b: any) => b.kind === 'artifact'))) return false;
    return true;
  }).sort((a, b) => b.updatedAt - a.updatedAt), [convos, q, projectFilter, cutoff, hasArt, archivedOnly]);

  const toggle = (id: string) => {
    setSelected((s) => {
      const n = new Set(s);
      n.has(id) ? n.delete(id) : n.add(id);
      return n;
    });
  };
  const toggleAll = () => {
    setSelected((s) => s.size === rows.length ? new Set() : new Set(rows.map((r) => r.id)));
  };

  const projects = Object.keys(PROJECT_META);

  return (
    <div className="view">
      <ViewHeader
        title={archivedOnly ? 'Archive' : 'History'}
        subtitle={archivedOnly ? 'Archived conversations — restore or delete' : 'All of your conversations'}
        actions={null}
      >
        <div className="view-filters">
          <div className="view-search">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M13.5 13.5L10.5 10.5" strokeLinecap="round"/></svg>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search title…" />
          </div>
          <select className="set-select" value={projectFilter} onChange={(e) => setProjectFilter(e.target.value)}>
            <option value="">All projects</option>
            {projects.map((p) => <option key={p} value={p}>{PROJECT_META[p].name}</option>)}
          </select>
          <select className="set-select" value={range} onChange={(e) => setRange(e.target.value)}>
            <option value="all">Any date</option>
            <option value="today">Last 24h</option>
            <option value="week">Last week</option>
            <option value="month">Last month</option>
          </select>
          <label className="view-checkbox">
            <input type="checkbox" checked={hasArt} onChange={(e) => setHasArt(e.target.checked)} />
            <span>With preview</span>
          </label>
        </div>
      </ViewHeader>

      {selected.size > 0 && (
        <div className="bulk-bar">
          <span><strong>{selected.size}</strong> selected{selected.size > 1 ? '' : ''}</span>
          {!archivedOnly && (
            <button className="btn btn-sm" onClick={() => { selected.forEach(onArchive); setSelected(new Set()); }}>
              Archive
            </button>
          )}
          {archivedOnly && (
            <button className="btn btn-sm" onClick={() => { selected.forEach(onArchive); setSelected(new Set()); }}>
              Restore
            </button>
          )}
          <button className="btn btn-sm danger" onClick={() => { selected.forEach(onDelete); setSelected(new Set()); }}>
            Delete
          </button>
          <button className="btn btn-sm" onClick={() => setSelected(new Set())}>Cancel</button>
        </div>
      )}

      <div className="view-body view-body-scroll">
        {rows.length === 0 ? (
          <div className="view-empty">
            <h3>{archivedOnly ? 'Nothing archived' : 'No conversations match'}</h3>
            <p>{archivedOnly ? 'When you archive a conversation, it appears here.' : 'Adjust filters to see more.'}</p>
          </div>
        ) : (
          <table className="hist-table">
            <thead>
              <tr>
                <th className="hist-check"><input type="checkbox" checked={selected.size === rows.length && rows.length > 0} onChange={toggleAll} /></th>
                <th className="hist-title">Title</th>
                <th className="hist-project">Project</th>
                <th className="hist-flags">Flags</th>
                <th className="hist-time">Updated</th>
                <th className="hist-actions" />
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => {
                const hasArtifact = c.messages?.some((m: any) => m.blocks?.some?.((b: any) => b.kind === 'artifact'));
                return (
                  <tr key={c.id} className={cn(selected.has(c.id) && 'is-selected')}>
                    <td className="hist-check" onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" checked={selected.has(c.id)} onChange={() => toggle(c.id)} />
                    </td>
                    <td className="hist-title" onClick={() => onOpenChat(c.id)}>
                      <span className="hist-title-text">{c.title}</span>
                      {c.pinned && <span className="hist-pin" title="Pinned">▸</span>}
                    </td>
                    <td className="hist-project">
                      <span className="hist-project-pill" style={{ '--p': PROJECT_META[c.project.root]?.color || 'var(--muted-2)' } as any}>
                        {PROJECT_META[c.project.root]?.name || c.project.root}
                      </span>
                    </td>
                    <td className="hist-flags">
                      {hasArtifact && <span className="flag" title="Has preview">◉</span>}
                    </td>
                    <td className="hist-time mono">{relTimeShort(c.updatedAt)} ago</td>
                    <td className="hist-actions" onClick={(e) => e.stopPropagation()}>
                      {archivedOnly ? (
                        <>
                          <button className="btn btn-sm" onClick={() => onArchive(c.id)}>Restore</button>
                          <button className="btn btn-sm danger" onClick={() => onDelete(c.id)}>Delete</button>
                        </>
                      ) : (
                        <>
                          <button className="btn btn-sm" onClick={() => onArchive(c.id)}>Archive</button>
                          <button className="btn btn-sm danger" onClick={() => onDelete(c.id)}>Delete</button>
                        </>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
