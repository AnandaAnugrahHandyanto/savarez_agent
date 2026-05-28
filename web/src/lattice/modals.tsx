// modals.tsx — Account + Settings modals
import { useState } from 'react';
import { Modal, InlineEditable, cn } from './primitives';
import { ViewHeader } from './views';
import { AUDIT_LOG } from './connectors';

interface AccountData {
  initials: string;
  name: string;
  email: string;
  workspace: string;
  plan: string;
  memberSince: string;
  tz: string;
  model: string;
  usage: { used: number; cap: number };
}

interface MyAccountBodyProps {
  account: AccountData;
  onChange: (patch: Partial<AccountData>) => void;
}

export function MyAccountBody({ account, onChange }: MyAccountBodyProps) {
  return (
    <>
      <div className="acc-head">
        <div className="acc-avatar">{account.initials}</div>
        <div className="acc-head-meta">
          <div className="acc-name">
            <InlineEditable value={account.name} onChange={(v) => onChange({ name: v })} />
          </div>
          <div className="acc-plan">
            <span className="badge">{account.plan}</span>
            <span className="muted mono">since {account.memberSince}</span>
          </div>
        </div>
      </div>

      <div className="acc-rows">
        <div className="acc-row">
          <span className="acc-label">Email</span>
          <InlineEditable value={account.email} onChange={(v) => onChange({ email: v })} type="email" />
        </div>
        <div className="acc-row">
          <span className="acc-label">Workspace</span>
          <InlineEditable value={account.workspace} onChange={(v) => onChange({ workspace: v })} />
        </div>
        <div className="acc-row">
          <span className="acc-label">Time zone</span>
          <InlineEditable value={account.tz} onChange={(v) => onChange({ tz: v })} />
        </div>
        <div className="acc-row">
          <span className="acc-label">Default model</span>
          <InlineEditable value={account.model} onChange={(v) => onChange({ model: v })} />
        </div>
      </div>

      <div className="acc-meter">
        <div className="acc-meter-hd">
          <span>Usage this month</span>
          <span className="mono muted">{account.usage.used.toLocaleString()} / {account.usage.cap.toLocaleString()} tk</span>
        </div>
        <div className="acc-meter-bar">
          <div className="acc-meter-fill" style={{ width: `${Math.min(100, (account.usage.used / account.usage.cap) * 100)}%` }} />
        </div>
      </div>

      <div className="acc-actions">
        <button className="btn btn-sm">Manage billing</button>
        <button className="btn btn-sm danger">Sign out</button>
      </div>
    </>
  );
}

export function MyAccountView({ account, onChange }: MyAccountBodyProps) {
  return (
    <div className="view">
      <ViewHeader title="My account" subtitle="Sua conta e plano" />
      <div className="view-body view-body-scroll">
        <div className="acc-view-shell">
          <MyAccountBody account={account} onChange={onChange} />
        </div>
      </div>
    </div>
  );
}

interface MyAccountModalProps extends MyAccountBodyProps {
  open: boolean;
  onClose: () => void;
}

export function MyAccountModal({ open, onClose, account, onChange }: MyAccountModalProps) {
  return (
    <Modal open={open} onClose={onClose} title="My account" width={520}>
      <MyAccountBody account={account} onChange={onChange} />
    </Modal>
  );
}

const SETTINGS_TABS = [
  { id: "general",    label: "General" },
  { id: "model",      label: "Model" },
  { id: "appearance", label: "Appearance" },
  { id: "audit",      label: "Audit log" },
  { id: "shortcuts",  label: "Shortcuts" },
  { id: "about",      label: "About" },
];

interface AppSettings {
  language: string;
  soundEnabled: boolean;
  notificationsEnabled: boolean;
  autoSave: boolean;
  model: string;
  creativity: number;
  maxTokens: number;
  showTools: boolean;
  dark: boolean;
  compact: boolean;
  accent: string;
}

interface SettingsBodyProps {
  settings: AppSettings;
  onChange: (patch: Partial<AppSettings>) => void;
  tab: string;
  setTab: (t: string) => void;
}

export function SettingsBody({ settings, onChange, tab, setTab }: SettingsBodyProps) {
  const Toggle = ({ label, value, onChange: onCh, hint }: { label: string; value: boolean; onChange: (v: boolean) => void; hint?: string }) => (
    <div className="set-row">
      <div>
        <div className="set-label">{label}</div>
        {hint && <div className="set-hint">{hint}</div>}
      </div>
      <button className={cn("switch", value && "on")} onClick={() => onCh(!value)} role="switch" aria-checked={value}>
        <span className="thumb" />
      </button>
    </div>
  );

  const Slider = ({ label, value, onChange: onCh, min = 0, max = 100, step = 1, suffix = "" }: { label: string; value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number; suffix?: string }) => (
    <div className="set-row">
      <div><div className="set-label">{label}</div></div>
      <div className="set-slider">
        <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onCh(+e.target.value)} />
        <span className="mono muted" style={{ minWidth: 36, textAlign: "right" }}>{value}{suffix}</span>
      </div>
    </div>
  );

  const Select = ({ label, value, options, onChange: onCh }: { label: string; value: string; options: { value: string; label: string }[]; onChange: (v: string) => void }) => (
    <div className="set-row">
      <div className="set-label">{label}</div>
      <select className="set-select" value={value} onChange={(e) => onCh(e.target.value)}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );

  return (
    <div className="set-shell">
      <nav className="set-nav">
        {SETTINGS_TABS.map((t) => (
          <button key={t.id} className={cn("set-nav-item", tab === t.id && "is-active")} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>
      <div className="set-pane">
        {tab === "general" && (
          <>
            <Select label="Language" value={settings.language}
              options={[{value:"en",label:"English"},{value:"pt",label:"Português"},{value:"es",label:"Español"},{value:"fr",label:"Français"}]}
              onChange={(v) => onChange({ language: v })} />
            <Toggle label="Sound effects" value={settings.soundEnabled} onChange={(v) => onChange({ soundEnabled: v })}
              hint="Subtle chimes when tasks complete." />
            <Toggle label="Notifications" value={settings.notificationsEnabled} onChange={(v) => onChange({ notificationsEnabled: v })}
              hint="Surface background-task results in the panel." />
            <Toggle label="Auto-save drafts" value={settings.autoSave} onChange={(v) => onChange({ autoSave: v })} />
          </>
        )}
        {tab === "model" && (
          <>
            <Select label="Default model" value={settings.model}
              options={[{value:"lattice-1 · pro",label:"lattice-1 · pro"},{value:"lattice-1 · fast",label:"lattice-1 · fast"},{value:"lattice-1 · max",label:"lattice-1 · max"}]}
              onChange={(v) => onChange({ model: v })} />
            <Slider label="Creativity" value={settings.creativity} min={0} max={100} onChange={(v) => onChange({ creativity: v })} />
            <Slider label="Max tokens" value={settings.maxTokens} min={512} max={32000} step={512} onChange={(v) => onChange({ maxTokens: v })} />
            <Toggle label="Show tool calls" value={settings.showTools} onChange={(v) => onChange({ showTools: v })} />
          </>
        )}
        {tab === "appearance" && (
          <>
            <Toggle label="Dark mode" value={settings.dark} onChange={(v) => onChange({ dark: v })} />
            <Toggle label="Compact density" value={settings.compact} onChange={(v) => onChange({ compact: v })} />
            <div className="set-row">
              <div className="set-label">Accent color</div>
              <div className="swatch-row">
                {["#2563eb","#16a34a","#9333ea","#dc2626","#0d9488","#ea580c"].map((c) => (
                  <button key={c} className={cn("swatch", settings.accent === c && "is-active")}
                          style={{ background: c }} onClick={() => onChange({ accent: c })} aria-label={`Accent ${c}`} />
                ))}
              </div>
            </div>
          </>
        )}
        {tab === "audit" && (
          <table className="audit-table">
            <thead>
              <tr><th>When</th><th>Actor</th><th>Action</th><th>Connector</th><th>Scopes</th></tr>
            </thead>
            <tbody>
              {AUDIT_LOG.map((a) => (
                <tr key={a.id}>
                  <td className="mono">{a.ts}</td>
                  <td>{a.actor}</td>
                  <td>{a.action}</td>
                  <td>{a.target}</td>
                  <td className="muted">{a.scopes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {tab === "shortcuts" && (
          <div className="kbd-grid">
            {[
              ["New chat", "⌘N"],
              ["Search", "⌘K"],
              ["Toggle sidebar", "⌘B"],
              ["Toggle tasks", "⌘J"],
              ["Send", "↵"],
              ["Newline", "⇧↵"],
              ["Voice input", "⌘ ⇧ V"],
              ["Settings", "⌘,"],
              ["Switch model", "⌘ ⇧ M"],
              ["Stop generation", "Esc"],
            ].map(([k, v]) => (
              <div key={k} className="kbd-row">
                <span>{k}</span>
                <span className="kbd mono">{v}</span>
              </div>
            ))}
          </div>
        )}
        {tab === "about" && (
          <div className="about">
            <div className="about-brand">
              <div>
                <div style={{ fontSize: 18, fontWeight: 600 }}>Lattice</div>
                <div className="mono muted">v0.4.2 · build 2026.05.27</div>
              </div>
            </div>
            <p className="about-copy">A quiet workspace for thinking with an agent. Conversations, projects, and the agent's working memory in one place.</p>
            <div className="about-links">
              <button className="btn">Release notes</button>
              <button className="btn">Documentation</button>
              <button className="btn">Keyboard shortcuts</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

interface SettingsViewProps {
  settings: AppSettings;
  onChange: (patch: Partial<AppSettings>) => void;
}

export function SettingsView({ settings, onChange }: SettingsViewProps) {
  const [tab, setTab] = useState("general");
  return (
    <div className="view">
      <ViewHeader title="Settings" subtitle="Configurações da conta e do workspace" />
      <div className="view-body view-body-scroll set-view-body">
        <SettingsBody settings={settings} onChange={onChange} tab={tab} setTab={setTab} />
      </div>
    </div>
  );
}

interface SettingsModalProps extends SettingsViewProps {
  open: boolean;
  onClose: () => void;
}

export function SettingsModal({ open, onClose, settings, onChange }: SettingsModalProps) {
  const [tab, setTab] = useState("general");
  return (
    <Modal open={open} onClose={onClose} title="Settings" width={720}>
      <SettingsBody settings={settings} onChange={onChange} tab={tab} setTab={setTab} />
    </Modal>
  );
}
