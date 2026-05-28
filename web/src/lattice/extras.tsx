// extras.tsx — search palette, dropdowns, secondary modals, message actions
import React, { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { cn, Tooltip, Modal } from './primitives';

// ── MenuItem type ────────────────────────────────────────────────────────────
export interface MenuItem {
  label?: string;
  kbd?: string;
  icon?: React.ReactNode;
  active?: boolean;
  danger?: boolean;
  divider?: boolean;
  section?: string;
  check?: boolean;
  onClick?: () => void;
}

// ── Generic dropdown menu ─────────────────────────────────────────────────────
interface MenuProps {
  open: boolean;
  onClose: () => void;
  anchorRect: DOMRect | null | undefined;
  items: MenuItem[];
  width?: number;
  align?: 'right' | 'left';
}

export function Menu({ open, onClose, anchorRect, items, width = 220, align = 'right' }: MenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0, ready: false });

  useLayoutEffect(() => {
    if (!open || !anchorRect) return;
    const el = menuRef.current;
    const h = el ? el.offsetHeight : 0;
    const margin = 8;
    const vh = window.innerHeight;
    const vw = window.innerWidth;

    let top = anchorRect.bottom + 6;
    if (top + h + margin > vh && anchorRect.top - h - 6 >= margin) {
      top = anchorRect.top - h - 6;
    }
    top = Math.min(Math.max(margin, top), Math.max(margin, vh - h - margin));

    let left = align === 'right'
      ? anchorRect.right - width
      : anchorRect.left;
    left = Math.min(Math.max(margin, left), vw - width - margin);

    setPos({ top, left, ready: true });
  }, [open, anchorRect, items.length, width, align]);

  if (!open || !anchorRect) return null;

  return (
    <div className="menu-layer" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={menuRef}
           className="menu"
           style={{ top: pos.top, left: pos.left, width, visibility: pos.ready ? 'visible' : 'hidden' }}
           onMouseDown={(e) => e.stopPropagation()}>
        {items.map((it, i) => it.divider ? (
          <div key={i} className="menu-divider" />
        ) : it.section ? (
          <div key={i} className="menu-section">{it.section}</div>
        ) : (
          <button key={i}
            className={cn('menu-item', it.active && 'is-active', it.danger && 'is-danger')}
            onClick={() => { it.onClick?.(); onClose(); }}>
            {it.icon && <span className="menu-icon">{it.icon}</span>}
            <span className="menu-label">{it.label}</span>
            {it.kbd && <span className="menu-kbd mono">{it.kbd}</span>}
            {it.check && <span className="menu-check">✓</span>}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Search palette ────────────────────────────────────────────────────────────
interface Convo {
  id: string;
  title: string;
  project: { root: string; path: string | null };
  [key: string]: any;
}

interface SearchPaletteProps {
  open: boolean;
  onClose: () => void;
  convos: Convo[];
  onPick: (id: string) => void;
}

export function SearchPalette({ open, onClose, convos, onPick }: SearchPaletteProps) {
  const [q, setQ] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQ('');
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const ql = q.trim().toLowerCase();
  const matches = ql
    ? convos.filter((c) =>
        c.title.toLowerCase().includes(ql) ||
        c.project.root.toLowerCase().includes(ql) ||
        (c.project.path || '').toLowerCase().includes(ql))
    : convos.slice(0, 6);

  const commands = ql ? [
    { id: 'new', label: 'Start new chat', kbd: '⌘N',
      icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M8 3v10M3 8h10"/></svg> },
    { id: 'settings', label: 'Open settings', kbd: '⌘,',
      icon: <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"><circle cx="8" cy="8" r="2"/><path d="M13 8.5l-.6-.3v-1l.6-.3-.6-1-.6.2-1-.6-.1-.7H8.3L8.2 5l-1 .6-.6-.2-.6 1 .6.3v1l-.6.3.6 1 .6-.2 1 .6.1.7h2.4l.1-.7 1-.6.6.2z" strokeLinejoin="round"/></svg> },
  ] : [];

  return (
    <div className="palette-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="palette">
        <div className="palette-input">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" className="palette-search-icon">
            <circle cx="7" cy="7" r="4.5"/><path d="M13.5 13.5L10.5 10.5" strokeLinecap="round"/>
          </svg>
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search conversations, projects, actions…"
          />
          <kbd className="palette-esc mono">esc</kbd>
        </div>

        <div className="palette-results">
          {matches.length > 0 && (
            <>
              <div className="palette-section">Conversations</div>
              {matches.map((c) => (
                <button key={c.id} className="palette-item"
                        onClick={() => { onPick(c.id); onClose(); }}>
                  <span className="palette-icon">
                    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"><path d="M3 4h7l3 3v5a1 1 0 01-1 1H3a1 1 0 01-1-1V5a1 1 0 011-1z"/></svg>
                  </span>
                  <span className="palette-meta">
                    <span className="palette-title">{c.title}</span>
                    <span className="palette-sub mono">{c.project.root}{c.project.path ? ` / ${c.project.path}` : ''}</span>
                  </span>
                  <span className="palette-tag mono">{c.id === 'new' ? 'draft' : 'chat'}</span>
                </button>
              ))}
            </>
          )}
          {commands.length > 0 && (
            <>
              <div className="palette-section">Actions</div>
              {commands.map((cmd) => (
                <button key={cmd.id} className="palette-item">
                  <span className="palette-icon">{cmd.icon}</span>
                  <span className="palette-meta">
                    <span className="palette-title">{cmd.label}</span>
                  </span>
                  <span className="palette-kbd mono">{cmd.kbd}</span>
                </button>
              ))}
            </>
          )}
          {!matches.length && !commands.length && (
            <div className="palette-empty">No matches for &quot;{q}&quot;</div>
          )}
        </div>

        <div className="palette-foot">
          <span className="mono"><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
          <span className="mono"><kbd>↵</kbd> select</span>
          <span className="mono"><kbd>esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}

// ── Sample Projects / Knowledge data ─────────────────────────────────────────
const SAMPLE_PROJECTS = [
  { id: 'paperclip-master', name: 'paperclip-master', chats: 14, updated: '2m',  desc: 'Verification gate + tool governance' },
  { id: 'marketing',        name: 'marketing',        chats: 6,  updated: '2h',  desc: 'Hero copy, pricing, blog drafts' },
  { id: 'planning',         name: 'planning',         chats: 9,  updated: '8h',  desc: 'Q3 OKRs, roadmap discussions' },
  { id: 'lattice-core',     name: 'lattice-core',     chats: 21, updated: '1d',  desc: 'Types, migrations, schema work' },
  { id: 'personal',         name: 'personal',         chats: 4,  updated: '3d',  desc: 'Notes, drafts, scratch' },
];

const SAMPLE_KNOWLEDGE = [
  { id: 'k1', name: 'Brand voice guidelines',   type: 'Doc',      size: '18 KB', updated: 'Mar 12' },
  { id: 'k2', name: 'Q2 retrospective notes',   type: 'Doc',      size: '42 KB', updated: 'Apr 04' },
  { id: 'k3', name: 'API reference (internal)', type: 'Markdown', size: '121 KB', updated: 'May 18' },
  { id: 'k4', name: 'Engineering handbook',     type: 'Doc',      size: '330 KB', updated: 'May 22' },
  { id: 'k5', name: 'Customer interviews',      type: 'Folder',   size: '12 items', updated: 'Today' },
];

interface ProjectsModalProps {
  open: boolean;
  onClose: () => void;
}

export function ProjectsModal({ open, onClose }: ProjectsModalProps) {
  return (
    <Modal open={open} onClose={onClose} title="Projects" width={640}>
      <div className="proj-list">
        {SAMPLE_PROJECTS.map((p) => (
          <button key={p.id} className="proj-row">
            <span className="proj-icon">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"><path d="M2 4.5A1.5 1.5 0 013.5 3h2.7l1.3 1.3h5A1.5 1.5 0 0114 5.8v5.7A1.5 1.5 0 0112.5 13h-9A1.5 1.5 0 012 11.5v-7z"/></svg>
            </span>
            <span className="proj-meta">
              <span className="proj-name">{p.name}</span>
              <span className="proj-desc">{p.desc}</span>
            </span>
            <span className="proj-stats mono">
              <span>{p.chats} chats</span>
              <span className="muted">· {p.updated}</span>
            </span>
          </button>
        ))}
      </div>
      <div className="proj-foot">
        <button className="btn primary">+ New project</button>
      </div>
    </Modal>
  );
}

interface KnowledgeModalProps {
  open: boolean;
  onClose: () => void;
}

export function KnowledgeModal({ open, onClose }: KnowledgeModalProps) {
  return (
    <Modal open={open} onClose={onClose} title="Knowledge" width={640}>
      <div className="kn-list">
        {SAMPLE_KNOWLEDGE.map((k) => (
          <button key={k.id} className="kn-row">
            <span className="kn-icon">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round">
                {k.type === 'Folder'
                  ? <path d="M2 4.5A1.5 1.5 0 013.5 3h2.7l1.3 1.3h5A1.5 1.5 0 0114 5.8v5.7A1.5 1.5 0 0112.5 13h-9A1.5 1.5 0 012 11.5v-7z"/>
                  : <><path d="M4 2h5l3 3v9a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M9 2v3h3M5.5 8h5M5.5 10.5h5M5.5 6h2"/></>}
              </svg>
            </span>
            <span className="kn-meta">
              <span className="kn-name">{k.name}</span>
              <span className="kn-sub mono">{k.type} · {k.size}</span>
            </span>
            <span className="kn-updated mono">{k.updated}</span>
          </button>
        ))}
      </div>
      <div className="proj-foot">
        <button className="btn">Add source</button>
        <button className="btn primary">+ Upload</button>
      </div>
    </Modal>
  );
}

// ── Message actions row ───────────────────────────────────────────────────────
interface MsgActionsProps {
  onCopy: () => Promise<void>;
  onRegen: () => void;
  onLike?: () => void;
  onDislike?: () => void;
}

export function MsgActions({ onCopy, onRegen, onLike, onDislike }: MsgActionsProps) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="msg-actions">
      <Tooltip label={copied ? 'Copied!' : 'Copy'} side="bottom" delay={150}>
        <button className="msg-act" onClick={async () => {
          try {
            await onCopy();
            setCopied(true);
            setTimeout(() => setCopied(false), 1400);
          } catch (_) {}
        }}>
          {copied ? (
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 8.5L6.5 12 13 4.5"/>
            </svg>
          ) : (
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round">
              <rect x="5" y="2" width="9" height="11" rx="1.5"/><path d="M11 13v1a1 1 0 01-1 1H3a1 1 0 01-1-1V6a1 1 0 011-1h1"/>
            </svg>
          )}
        </button>
      </Tooltip>
      <Tooltip label="Regenerate" side="bottom" delay={150}>
        <button className="msg-act" onClick={onRegen}>
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M13 8a5 5 0 11-1.5-3.5"/><path d="M13 2v3h-3"/>
          </svg>
        </button>
      </Tooltip>
      <Tooltip label="Good response" side="bottom" delay={150}>
        <button className="msg-act" onClick={onLike}>
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round">
            <path d="M6 7l2.5-4c.4 0 1 .4 1 1.5L9 7h3.5a1 1 0 011 1.2l-.8 4a1.5 1.5 0 01-1.5 1.3H6"/><rect x="3" y="7" width="3" height="6.5" rx=".5"/>
          </svg>
        </button>
      </Tooltip>
      <Tooltip label="Bad response" side="bottom" delay={150}>
        <button className="msg-act" onClick={onDislike}>
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round">
            <path d="M10 9l-2.5 4c-.4 0-1-.4-1-1.5L7 9H3.5a1 1 0 01-1-1.2l.8-4a1.5 1.5 0 011.5-1.3H10"/><rect x="10" y="2.5" width="3" height="6.5" rx=".5"/>
          </svg>
        </button>
      </Tooltip>
    </div>
  );
}

// ── useAnchoredMenu ───────────────────────────────────────────────────────────
export function useAnchoredMenu() {
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const openMenu = () => {
    if (triggerRef.current) setRect(triggerRef.current.getBoundingClientRect());
    setOpen(true);
  };
  return { open, setOpen, openMenu, rect, triggerRef };
}
