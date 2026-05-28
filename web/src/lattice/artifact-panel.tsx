// artifact-panel.tsx — side preview panel (Preview/Code tabs) + ArtifactCard
import React, { useState, useRef, useEffect } from 'react';
import { cn, Tooltip } from './primitives';

// ── Sample artifacts ──────────────────────────────────────────────────────────
export interface Artifact {
  id: string;
  title: string;
  kind: string;
  language?: string;
  content: string;
}

export const ARTIFACTS_SAMPLE: Record<string, Artifact> = {
  'art-hero': {
    id: 'art-hero',
    title: 'Landing hero',
    kind: 'html',
    language: 'html',
    content: `<!doctype html>
<html><head><meta charset="utf-8">
<style>
  body { margin:0; font-family: ui-sans-serif, system-ui; background: #fafaf9; color: #18181b; }
  .hero { min-height: 100vh; display: grid; place-items: center; padding: 40px 24px; }
  .card { max-width: 640px; text-align: center; }
  .eyebrow { font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: #2563eb; margin-bottom: 16px; }
  h1 { font-size: clamp(36px, 6vw, 56px); margin: 0 0 16px; letter-spacing: -.02em; line-height: 1.05; }
  p { font-size: 18px; color: #52525b; margin: 0 auto 28px; max-width: 520px; line-height: 1.5; }
  .row { display: inline-flex; gap: 10px; }
  .btn { font: inherit; padding: 11px 18px; border-radius: 10px; border: 1px solid #e4e4e7; background: #fff; cursor: pointer; }
  .btn.primary { background: #18181b; color: #fff; border-color: #18181b; }
</style></head>
<body>
  <div class="hero">
    <div class="card">
      <div class="eyebrow">Lattice · v0.4</div>
      <h1>Ship the work, not just the chat.</h1>
      <p>A quiet workspace where careful thought meets keyboard speed — and your agent actually inhabits the rooms you build in.</p>
      <div class="row">
        <button class="btn primary">Start free trial</button>
        <button class="btn">Watch demo</button>
      </div>
    </div>
  </div>
</body></html>`,
  },
  'art-notes': {
    id: 'art-notes',
    title: 'Q3 OKR draft',
    kind: 'markdown',
    language: 'markdown',
    content: `# Q3 Objectives

Three objectives focused on reducing time-to-value for new teams.

## O1 — Halve median time-to-first-output
**KR1.** New signups produce a useful agent output within 8 minutes (p50).
**KR2.** First-session completion rate above **62%** (currently 41%).
**KR3.** Onboarding drop-off below **15%** at the "first prompt" step.

## O2 — Day-30 power-user parity
**KR1.** Day-30 actives use *Projects* and *Background tasks* at parity with 90-day actives.
**KR2.** Median tasks-per-session ≥ 3 by day 14.
**KR3.** Manual help-desk tickets per active user down **40%**.

## O3 — Earn permission to live in the workflow
**KR1.** Week-2 retention above **48%** (currently 31%).
**KR2.** Connector adoption (Drive / Calendar / Gmail) ≥ 2 per active.
**KR3.** Weekly active conversation count per user ≥ 10.

> Notes: assume TTV measured in *days from signup to first useful output*.
> Revisit O3 if W2 retention exceeds target — there's likely headroom on W4.`,
  },
  'art-counter': {
    id: 'art-counter',
    title: 'Throttled counter',
    kind: 'code',
    language: 'javascript',
    content: `// Tiny throttled counter — leading + trailing edge.
function throttle(fn, wait) {
  let last = 0, t = null, lastArgs;
  return function (...args) {
    const now = Date.now();
    const remaining = wait - (now - last);
    lastArgs = args;
    if (remaining <= 0) {
      if (t) { clearTimeout(t); t = null; }
      last = now;
      fn.apply(this, args);
    } else if (!t) {
      t = setTimeout(() => {
        last = Date.now();
        t = null;
        fn.apply(this, lastArgs);
      }, remaining);
    }
  };
}

const log = throttle((n) => console.log('tick', n), 250);
let n = 0; setInterval(() => log(++n), 40);`,
  },
};

// ── ArtifactCard ──────────────────────────────────────────────────────────────
interface ArtifactCardProps {
  artifact: Artifact;
  onOpen: (id: string) => void;
}

export function ArtifactCard({ artifact, onOpen }: ArtifactCardProps) {
  const a = artifact;
  const kindLabel = ({
    html: 'Web preview',
    markdown: 'Markdown',
    code: 'Code',
    react: 'React app',
  } as Record<string, string>)[a.kind] || 'Artifact';
  return (
    <button className="artifact-card" onClick={() => onOpen(a.id)}>
      <span className="artifact-thumb" data-kind={a.kind}>
        {a.kind === 'html' && (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M7 6.5h.5M9.5 6.5h.5M12 6.5h.5"/>
          </svg>
        )}
        {a.kind === 'markdown' && (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round">
            <path d="M5 4h11l3 3v13a1 1 0 01-1 1H5a1 1 0 01-1-1V5a1 1 0 011-1z"/>
            <path d="M16 4v3h3M8 12h2l1 2 1-2h2v5M8 12v5"/>
          </svg>
        )}
        {a.kind === 'code' && (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M7 8l-4 4 4 4M17 8l4 4-4 4M14 5l-4 14"/>
          </svg>
        )}
        {a.kind === 'react' && (
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4">
            <ellipse cx="12" cy="12" rx="10" ry="4"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/>
          </svg>
        )}
      </span>
      <span className="artifact-meta">
        <span className="artifact-title">{a.title}</span>
        <span className="artifact-sub">
          <span className="artifact-kind">{kindLabel}</span>
          <span className="artifact-sep">·</span>
          <span className="mono">{a.content.split('\n').length} lines</span>
        </span>
      </span>
      <span className="artifact-open">
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M6 4l4 4-4 4"/>
        </svg>
      </span>
    </button>
  );
}

// ── Tiny markdown render ──────────────────────────────────────────────────────
function renderMarkdown(src: string): React.ReactNode[] {
  const lines = src.split('\n');
  const out: React.ReactNode[] = [];
  let listBuf: React.ReactNode[] | null = null;

  const flushList = () => {
    if (listBuf) { out.push(<ul key={'ul-' + out.length}>{listBuf}</ul>); listBuf = null; }
  };
  const inline = (s: string) =>
    s.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g).map((tok, i) => {
      if (tok.startsWith('**')) return <strong key={i}>{tok.slice(2, -2)}</strong>;
      if (tok.startsWith('*') && tok.endsWith('*') && tok.length > 1) return <em key={i}>{tok.slice(1, -1)}</em>;
      if (tok.startsWith('`')) return <code key={i}>{tok.slice(1, -1)}</code>;
      return tok;
    });

  lines.forEach((line, i) => {
    const trimmed = line.trim();
    if (!trimmed) { flushList(); return; }
    if (/^#\s/.test(trimmed))       { flushList(); out.push(<h1 key={i}>{inline(trimmed.slice(2))}</h1>); }
    else if (/^##\s/.test(trimmed))  { flushList(); out.push(<h2 key={i}>{inline(trimmed.slice(3))}</h2>); }
    else if (/^###\s/.test(trimmed)) { flushList(); out.push(<h3 key={i}>{inline(trimmed.slice(4))}</h3>); }
    else if (/^>\s/.test(trimmed))   { flushList(); out.push(<blockquote key={i}>{inline(trimmed.slice(2))}</blockquote>); }
    else if (/^[-*]\s/.test(trimmed)) {
      if (!listBuf) listBuf = [];
      listBuf.push(<li key={i}>{inline(trimmed.slice(2))}</li>);
    } else {
      flushList();
      out.push(<p key={i}>{inline(trimmed)}</p>);
    }
  });
  flushList();
  return out;
}

// ── Code highlight ────────────────────────────────────────────────────────────
function highlightCode(src: string, lang?: string): string {
  if (!lang || lang === 'markdown') return src;
  const tokens = [
    { re: /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)/g, cls: 'tk-comment' },
    { re: /(['"`])(?:\\.|(?!\1)[^\\])*\1/g, cls: 'tk-string' },
    { re: /\b(const|let|var|function|return|if|else|for|while|new|class|import|export|from|as|this|true|false|null|undefined|async|await|try|catch|throw)\b/g, cls: 'tk-kw' },
    { re: /\b(\d+(?:\.\d+)?)\b/g, cls: 'tk-num' },
  ];
  let result = src;
  const stash: string[] = [];
  tokens.forEach((t) => {
    result = result.replace(t.re, (m) => {
      const id = `__T${stash.length}__`;
      const escaped = m.replace(/[&<>]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c] || c));
      stash.push(`<span class="${t.cls}">${escaped}</span>`);
      return id;
    });
  });
  result = result.replace(/[&<>]/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c] || c));
  stash.forEach((html, i) => {
    result = result.replace(new RegExp(`__T${i}__`), html);
  });
  return result;
}

// ── ArtifactPanel ─────────────────────────────────────────────────────────────
interface ArtifactPanelProps {
  artifact: Artifact | null;
  onClose: () => void;
}

export function ArtifactPanel({ artifact, onClose }: ArtifactPanelProps) {
  const [tab, setTab] = useState('preview');
  const [copied, setCopied] = useState(false);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const [width, setWidth] = useState(() => {
    try {
      const saved = +localStorage.getItem('lattice.art.w')!;
      return saved && saved >= 380 && saved <= 1100 ? saved : 580;
    } catch { return 580; }
  });

  useEffect(() => {
    document.documentElement.style.setProperty('--art-w', width + 'px');
    try { localStorage.setItem('lattice.art.w', String(width)); } catch (_) {}
  }, [width]);

  const onResizeDown = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;
    const onMove = (ev: MouseEvent) => {
      const next = Math.max(380, Math.min(1100, startW + (startX - ev.clientX)));
      setWidth(next);
    };
    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };
  const onResizeDouble = () => setWidth(580);

  useEffect(() => { setTab('preview'); }, [artifact?.id]);

  useEffect(() => {
    if (!artifact) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [artifact, onClose]);

  if (!artifact) return null;

  const copy = async () => {
    try { await navigator.clipboard.writeText(artifact.content); }
    catch {
      const ta = document.createElement('textarea');
      ta.value = artifact.content;
      document.body.appendChild(ta); ta.select();
      document.execCommand('copy'); ta.remove();
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };

  const download = () => {
    const ext = ({html:'html', markdown:'md', javascript:'js', typescript:'ts', code:'txt'} as Record<string, string>)[artifact.language || ''] || 'txt';
    const blob = new Blob([artifact.content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${artifact.title.replace(/\s+/g, '-').toLowerCase()}.${ext}`;
    a.click(); URL.revokeObjectURL(url);
  };

  const canPreview = artifact.kind === 'html' || artifact.kind === 'markdown';

  return (
    <aside className="art-panel">
      <div className="art-resize"
           onMouseDown={onResizeDown}
           onDoubleClick={onResizeDouble}
           title="Drag to resize · double-click to reset"
           aria-label="Resize preview panel" />
      <div className="art-hd">
        <div className="art-hd-meta">
          <span className="art-hd-title">{artifact.title}</span>
          <span className="art-hd-sub mono">{artifact.language || artifact.kind}</span>
        </div>
        <div className="art-hd-actions">
          {canPreview && (
            <div className="art-tabs">
              <button className={cn('art-tab', tab === 'preview' && 'is-active')}
                      onClick={() => setTab('preview')}>Preview</button>
              <button className={cn('art-tab', tab === 'code' && 'is-active')}
                      onClick={() => setTab('code')}>Code</button>
            </div>
          )}
          <Tooltip label={copied ? 'Copied!' : 'Copy'} side="bottom" delay={150}>
            <button className="icon-btn" onClick={copy} aria-label="Copy">
              {copied ? (
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3 8.5L6.5 12 13 4.5"/></svg>
              ) : (
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"><rect x="5" y="2" width="9" height="11" rx="1.5"/><path d="M11 13v1a1 1 0 01-1 1H3a1 1 0 01-1-1V6a1 1 0 011-1h1"/></svg>
              )}
            </button>
          </Tooltip>
          <Tooltip label="Download" side="bottom" delay={150}>
            <button className="icon-btn" onClick={download} aria-label="Download">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M8 2v8M5 7l3 3 3-3M3 13h10"/></svg>
            </button>
          </Tooltip>
          <Tooltip label="Close  Esc" side="bottom" delay={150}>
            <button className="icon-btn" onClick={onClose} aria-label="Close">
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"><path d="M4 4l8 8M12 4l-8 8"/></svg>
            </button>
          </Tooltip>
        </div>
      </div>

      <div className="art-body">
        {tab === 'preview' && artifact.kind === 'html' && (
          <iframe
            ref={iframeRef}
            title={artifact.title}
            className="art-iframe"
            sandbox="allow-scripts allow-same-origin"
            srcDoc={artifact.content}
          />
        )}
        {tab === 'preview' && artifact.kind === 'markdown' && (
          <div className="art-md">{renderMarkdown(artifact.content)}</div>
        )}
        {(tab === 'code' || !canPreview) && (
          <pre className="art-code"><code
            className={`lang-${artifact.language || 'text'}`}
            dangerouslySetInnerHTML={{ __html: highlightCode(artifact.content, artifact.language) }}
          /></pre>
        )}
      </div>

      <div className="art-foot">
        <span className="mono muted">
          {artifact.content.length.toLocaleString()} chars · {artifact.content.split('\n').length} lines
        </span>
      </div>
    </aside>
  );
}
