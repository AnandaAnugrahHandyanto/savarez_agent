// connectors.tsx — Connectors hub view + ConnectorModal (OAuth mock) + permissions audit
import React, { useState, useMemo } from 'react';
import { Modal } from './primitives';
import { ViewHeader } from './views';

// ── Logos ────────────────────────────────────────────────────────────────────
const ConnLogo: Record<string, React.FC<{ size?: number }>> = {
  drive: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <path d="M8 3l-5 9 3 5h12l3-5L16 3z" fill="#1FA463"/>
      <path d="M8 3l3 5h13L16 3z" fill="#FFC107"/>
      <path d="M6 17h12l-3-5H3z" fill="#4285F4"/>
    </svg>
  ),
  gmail: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <rect x="2" y="5" width="20" height="14" rx="2" fill="#EA4335"/>
      <path d="M2 7l10 7 10-7v12H2z" fill="#fff"/>
      <path d="M2 7l10 7L2 19z" fill="#4285F4"/>
      <path d="M22 7L12 14l10 5z" fill="#34A853"/>
    </svg>
  ),
  calendar: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <rect x="3" y="5" width="18" height="16" rx="2" fill="#fff" stroke="#dadce0"/>
      <rect x="3" y="5" width="18" height="4" fill="#4285F4"/>
      <text x="12" y="18" fontSize="9" fontWeight="700" fill="#4285F4" textAnchor="middle" fontFamily="sans-serif">27</text>
    </svg>
  ),
  github: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <circle cx="12" cy="12" r="11" fill="#181717"/>
      <path d="M12 6c-3.3 0-6 2.7-6 6 0 2.7 1.7 4.9 4.1 5.7.3 0 .4-.1.4-.3v-1.2c-1.6.4-2-.8-2-.8-.3-.7-.7-.9-.7-.9-.6-.4 0-.4 0-.4.7 0 1 .7 1 .7.6 1 1.5.7 1.9.6.1-.4.2-.7.4-.9-1.3-.1-2.7-.7-2.7-3 0-.7.2-1.2.6-1.6 0-.2-.3-.8.1-1.7 0 0 .5-.2 1.7.6.5-.1 1-.2 1.6-.2.5 0 1.1.1 1.6.2 1.2-.8 1.7-.6 1.7-.6.3.9.1 1.5.1 1.7.4.4.6.9.6 1.6 0 2.3-1.4 2.9-2.7 3 .2.2.4.6.4 1.2v1.8c0 .2.1.4.4.3 2.4-.8 4.1-3 4.1-5.7 0-3.3-2.7-6-6-6z" fill="#fff"/>
    </svg>
  ),
  slack: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <rect x="5" y="10" width="3" height="9" rx="1.5" fill="#E01E5A"/>
      <rect x="5" y="5" width="9" height="3" rx="1.5" fill="#36C5F0"/>
      <rect x="16" y="5" width="3" height="9" rx="1.5" fill="#2EB67D"/>
      <rect x="10" y="16" width="9" height="3" rx="1.5" fill="#ECB22E"/>
    </svg>
  ),
  notion: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <rect x="3" y="3" width="18" height="18" rx="3" fill="#fff" stroke="#000" strokeWidth="1.5"/>
      <path d="M8 8v8M8 8l5 8V8" stroke="#000" strokeWidth="1.5" fill="none" strokeLinejoin="round"/>
    </svg>
  ),
  linear: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <rect x="2" y="2" width="20" height="20" rx="5" fill="#5E6AD2"/>
      <path d="M5 13l6 6M5 9l10 10M7 5l12 12M11 5l8 8M16 5l3 3" stroke="#fff" strokeWidth="1.4" strokeLinecap="round" opacity=".9"/>
    </svg>
  ),
  jira: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <path d="M11 3l8 8-8 8-1.5-1.5 3.5-3.5H4v-2h9l-3.5-3.5z" fill="#2684FF"/>
    </svg>
  ),
  canva: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <defs>
        <linearGradient id="cg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#7D2AE7"/>
          <stop offset="50%" stopColor="#00C4CC"/>
          <stop offset="100%" stopColor="#01F1A9"/>
        </linearGradient>
      </defs>
      <circle cx="12" cy="12" r="11" fill="url(#cg)"/>
      <path d="M8 14a4 4 0 016-3.5" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round"/>
    </svg>
  ),
  rovo: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <rect x="2" y="2" width="20" height="20" rx="5" fill="#0052CC"/>
      <path d="M7 17l5-10 5 10M9.5 13h5" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  monday: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <rect x="2" y="2" width="20" height="20" rx="5" fill="#fff" stroke="#e5e7eb"/>
      <rect x="4.5" y="9" width="3.5" height="6" rx="1.75" fill="#FF3D57"/>
      <rect x="10.25" y="9" width="3.5" height="6" rx="1.75" fill="#FFCB00"/>
      <rect x="16" y="9" width="3.5" height="6" rx="1.75" fill="#00CA72"/>
    </svg>
  ),
  asana: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <circle cx="12" cy="7" r="3.5" fill="#F06A6A"/>
      <circle cx="7" cy="15" r="3.5" fill="#F06A6A"/>
      <circle cx="17" cy="15" r="3.5" fill="#F06A6A"/>
    </svg>
  ),
  miro: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <rect x="2" y="2" width="20" height="20" rx="4" fill="#FFD02F"/>
      <path d="M8 5l-2 14M11.5 5l-1.5 14M15 5l-1 14M18.5 5l-.5 14" stroke="#050038" strokeWidth="1.6" strokeLinecap="round"/>
    </svg>
  ),
  mslearn: ({ size = 28 }) => (
    <svg viewBox="0 0 24 24" width={size} height={size}>
      <rect x="2" y="2" width="9.5" height="9.5" fill="#F25022"/>
      <rect x="12.5" y="2" width="9.5" height="9.5" fill="#7FBA00"/>
      <rect x="2" y="12.5" width="9.5" height="9.5" fill="#00A4EF"/>
      <rect x="12.5" y="12.5" width="9.5" height="9.5" fill="#FFB900"/>
    </svg>
  ),
};

export { ConnLogo };

// ── Connectors registry ──────────────────────────────────────────────────────
export const CONNECTORS = [
  { id: "drive",    name: "Google Drive",     blurb: "Acesse documentos e planilhas no Drive",  scopes: ["Read files", "Read metadata"] },
  { id: "gmail",    name: "Gmail",            blurb: "Resuma threads e rascunhe respostas",      scopes: ["Read messages", "Send drafts"] },
  { id: "calendar", name: "Google Calendar",  blurb: "Veja eventos e crie rascunhos de reunião", scopes: ["Read events", "Create events"] },
  { id: "github",   name: "GitHub",           blurb: "Indexe repositórios e abra issues/PRs",    scopes: ["Read code", "Issues", "Pull requests"] },
  { id: "slack",    name: "Slack",            blurb: "Busque mensagens e poste em canais",       scopes: ["Read messages", "Post messages"] },
  { id: "notion",   name: "Notion",           blurb: "Acesse páginas e bancos do workspace",     scopes: ["Read pages", "Read databases"] },
  { id: "linear",   name: "Linear",           blurb: "Veja tickets e mude status",               scopes: ["Read issues", "Update issues"] },
  { id: "jira",     name: "Jira",             blurb: "Acompanhe sprints e tickets",              scopes: ["Read issues", "Transition"] },
  { id: "canva",    name: "Canva",            blurb: "Acesse designs e crie rascunhos visuais",  scopes: ["Read designs", "Create designs"] },
  { id: "rovo",     name: "Atlassian Rovo",   blurb: "Busque conhecimento em Jira, Confluence",  scopes: ["Read content", "Run search"] },
  { id: "monday",   name: "monday.com",       blurb: "Veja boards e atualize itens de status",   scopes: ["Read boards", "Update items"] },
  { id: "asana",    name: "Asana",            blurb: "Veja tarefas e atualize status",           scopes: ["Read tasks", "Update tasks"] },
  { id: "miro",     name: "Miro",             blurb: "Acesse boards e crie post-its colaborativos", scopes: ["Read boards", "Create items"] },
  { id: "mslearn",  name: "Microsoft Learn",  blurb: "Consulte documentação técnica oficial",    scopes: ["Read modules", "Read paths"] },
];

const INITIAL_CONNECTOR_STATE: Record<string, { status: string; account: string | null; lastSync: string | null }> = {
  drive:    { status: "connected",    account: "joao@latticelabs.dev",   lastSync: "2m ago"   },
  gmail:    { status: "connected",    account: "joao@latticelabs.dev",   lastSync: "12m ago"  },
  calendar: { status: "expired",      account: "joao@latticelabs.dev",   lastSync: "3d ago"   },
  github:   { status: "connected",    account: "joaoalmeida",            lastSync: "Just now" },
  slack:    { status: "disconnected", account: null,                     lastSync: null       },
  notion:   { status: "disconnected", account: null,                     lastSync: null       },
  linear:   { status: "disconnected", account: null,                     lastSync: null       },
  jira:     { status: "disconnected", account: null,                     lastSync: null       },
  canva:    { status: "disconnected", account: null,                     lastSync: null       },
  rovo:     { status: "disconnected", account: null,                     lastSync: null       },
  monday:   { status: "disconnected", account: null,                     lastSync: null       },
  asana:    { status: "disconnected", account: null,                     lastSync: null       },
  miro:     { status: "disconnected", account: null,                     lastSync: null       },
  mslearn:  { status: "disconnected", account: null,                     lastSync: null       },
};

export const AUDIT_LOG = [
  { id: "a1", ts: "Today, 14:22",  actor: "João Almeida", action: "Connected",     target: "GitHub",   scopes: "Read code, Issues" },
  { id: "a2", ts: "Today, 11:08",  actor: "agent",        action: "Used",          target: "Drive",    scopes: "Read files" },
  { id: "a3", ts: "Yesterday",     actor: "João Almeida", action: "Token expired", target: "Calendar", scopes: "—" },
  { id: "a4", ts: "Yesterday",     actor: "agent",        action: "Used",          target: "Gmail",    scopes: "Read messages" },
  { id: "a5", ts: "2 days ago",    actor: "João Almeida", action: "Connected",     target: "Gmail",    scopes: "Read, Send drafts" },
];

// ── ConnectorModal ────────────────────────────────────────────────────────────
interface ConnectorModalProps {
  connector: typeof CONNECTORS[0] | null | undefined;
  state: { status: string; account: string | null; lastSync: string | null } | null;
  onClose: () => void;
  onConnect: (id: string) => void;
  onDisconnect: (id: string) => void;
}

export function ConnectorModal({ connector, state, onClose, onConnect, onDisconnect }: ConnectorModalProps) {
  const [phase, setPhase] = useState<"idle" | "consent" | "connecting" | "success">("idle");
  const [enabledScopes, setEnabledScopes] = useState<Set<string>>(() => new Set(connector?.scopes || []));

  React.useEffect(() => { setPhase("idle"); }, [connector?.id]);

  if (!connector || !state) return null;
  const Logo = ConnLogo[connector.id];

  const goConsent = () => setPhase("consent");
  const goConnect = () => {
    setPhase("connecting");
    setTimeout(() => {
      setPhase("success");
      onConnect(connector.id);
    }, 1300);
  };

  const toggleScope = (s: string) => {
    setEnabledScopes((cur) => {
      const n = new Set(cur);
      n.has(s) ? n.delete(s) : n.add(s);
      return n;
    });
  };

  return (
    <Modal open={!!connector} onClose={onClose} title={connector.name} width={480}>
      {phase === "idle" && state.status === "connected" && (
        <>
          <div className="conn-modal-hd">
            {Logo && <Logo size={48} />}
            <div>
              <div className="conn-modal-account">{state.account}</div>
              <div className="conn-modal-sub mono">Connected · last sync {state.lastSync}</div>
            </div>
          </div>
          <div className="conn-scopes">
            <div className="conn-scopes-label">Permissions</div>
            {connector.scopes.map((s) => (
              <label key={s} className="conn-scope">
                <input type="checkbox" checked={enabledScopes.has(s)} onChange={() => toggleScope(s)} />
                <span>{s}</span>
              </label>
            ))}
          </div>
          <div className="modal-foot">
            <button className="btn btn-sm danger" onClick={() => { onDisconnect(connector.id); onClose(); }}>Disconnect</button>
            <button className="btn btn-sm" onClick={onClose}>Done</button>
          </div>
        </>
      )}

      {phase === "idle" && state.status === "expired" && (
        <>
          <div className="conn-modal-hd">
            {Logo && <Logo size={48} />}
            <div>
              <div className="conn-modal-account">{state.account}</div>
              <div className="conn-modal-sub mono" style={{ color: "var(--err)" }}>Token expired · last sync {state.lastSync}</div>
            </div>
          </div>
          <p className="conn-modal-help">Sua autorização expirou. Reconecte para continuar sincronizando.</p>
          <div className="modal-foot">
            <button className="btn btn-sm" onClick={onClose}>Cancel</button>
            <button className="btn btn-sm primary" onClick={goConsent}>Reconnect</button>
          </div>
        </>
      )}

      {phase === "idle" && state.status === "disconnected" && (
        <>
          <div className="conn-modal-hd">
            {Logo && <Logo size={48} />}
            <div>
              <div className="conn-modal-account">{connector.name}</div>
              <div className="conn-modal-sub">{connector.blurb}</div>
            </div>
          </div>
          <div className="conn-scopes">
            <div className="conn-scopes-label">Lattice irá solicitar:</div>
            {connector.scopes.map((s) => (
              <div key={s} className="conn-scope conn-scope-read">
                <span className="conn-scope-dot" />
                <span>{s}</span>
              </div>
            ))}
          </div>
          <div className="modal-foot">
            <button className="btn btn-sm" onClick={onClose}>Cancel</button>
            <button className="btn btn-sm primary" onClick={goConsent}>Continue</button>
          </div>
        </>
      )}

      {phase === "consent" && (
        <div className="conn-consent">
          {Logo && <Logo size={56} />}
          <h3>Authorize Lattice to access {connector.name}</h3>
          <p>Você será redirecionado para concluir a autorização. Lattice nunca armazena suas credenciais.</p>
          <ul className="conn-consent-list">
            {connector.scopes.map((s) => (
              <li key={s}>
                <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3 8.5L6.5 12 13 4.5"/></svg>
                <span>{s}</span>
              </li>
            ))}
          </ul>
          <div className="modal-foot">
            <button className="btn btn-sm" onClick={() => setPhase("idle")}>Back</button>
            <button className="btn btn-sm primary" onClick={goConnect}>Authorize</button>
          </div>
        </div>
      )}

      {phase === "connecting" && (
        <div className="conn-loading">
          <div className="conn-spinner" />
          <div>Conectando ao {connector.name}…</div>
        </div>
      )}

      {phase === "success" && (
        <div className="conn-success">
          <div className="conn-check">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 8.5L6.5 12 13 4.5"/></svg>
          </div>
          <h3>Conectado</h3>
          <p>{connector.name} agora está disponível para o agente.</p>
          <div className="modal-foot">
            <button className="btn btn-sm primary" onClick={onClose}>Done</button>
          </div>
        </div>
      )}
    </Modal>
  );
}

// ── StatusPill ────────────────────────────────────────────────────────────────
export function StatusPill({ status }: { status: string }) {
  const m: Record<string, { label: string; cls: string }> = {
    connected:    { label: "connected",    cls: "ok"   },
    expired:      { label: "token expired", cls: "warn" },
    disconnected: { label: "not connected", cls: "off"  },
    connecting:   { label: "connecting…",   cls: "warn" },
  };
  const info = m[status] || { label: status, cls: "off" };
  return <span className={`conn-pill conn-pill-${info.cls} mono`}>{info.label}</span>;
}

// ── ConnectorsView ────────────────────────────────────────────────────────────
interface ConnectorsViewProps {
  onOpenSettings?: () => void;
}

export function ConnectorsView({ onOpenSettings: _onOpenSettings }: ConnectorsViewProps) {
  const [state, setState] = useState(INITIAL_CONNECTOR_STATE);
  const [modalId, setModalId] = useState<string | null>(null);

  const connect    = (id: string) => setState((s) => ({ ...s, [id]: { ...s[id], status: "connected", account: s[id]?.account || "joao@latticelabs.dev", lastSync: "Just now" } }));
  const disconnect = (id: string) => setState((s) => ({ ...s, [id]: { status: "disconnected", account: null, lastSync: null } }));

  const counts = useMemo(() => {
    const c: Record<string, number> = { connected: 0, expired: 0, disconnected: 0 };
    Object.values(state).forEach((s) => { c[s.status] = (c[s.status] || 0) + 1; });
    return c;
  }, [state]);

  const modalConn = CONNECTORS.find((c) => c.id === modalId);

  return (
    <div className="view">
      <ViewHeader
        title="Connectors"
        subtitle={`${counts.connected} conectado${counts.connected !== 1 ? "s" : ""} · ${counts.expired} com token expirado · ${counts.disconnected} disponíve${counts.disconnected !== 1 ? "is" : "l"}`}
      />

      <div className="view-body view-body-scroll">
        <div className="conn-grid">
          {CONNECTORS.map((c) => {
            const s = state[c.id] || { status: "disconnected", account: null, lastSync: null };
            const Logo = ConnLogo[c.id];
            return (
              <button key={c.id} className="conn-card" onClick={() => setModalId(c.id)}>
                <div className="conn-card-hd">
                  {Logo && <Logo size={28} />}
                  <StatusPill status={s.status} />
                </div>
                <div className="conn-card-meta">
                  <div className="conn-card-name">{c.name}</div>
                  <div className="conn-card-blurb">{c.blurb}</div>
                </div>
                <div className="conn-card-foot mono">
                  {s.status === "connected" && (
                    <>
                      <span>{s.account}</span>
                      <span className="muted">· last sync {s.lastSync}</span>
                    </>
                  )}
                  {s.status === "expired" && (
                    <span style={{ color: "var(--err)" }}>Reconnect required</span>
                  )}
                  {s.status === "disconnected" && (
                    <span className="muted">{c.scopes.length} permission{c.scopes.length !== 1 ? "s" : ""} requested</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <ConnectorModal
        connector={modalConn}
        state={modalId ? state[modalId] : null}
        onClose={() => setModalId(null)}
        onConnect={connect}
        onDisconnect={disconnect}
      />
    </div>
  );
}
