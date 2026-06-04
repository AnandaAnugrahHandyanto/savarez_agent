import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { DesktopAuthProvider, DesktopConnectionConfig, DesktopConnectionProbeResult, DesktopRemoteConnection } from '@/global'
import { AlertCircle, Check, FileText, Globe, Loader2, LogIn, Monitor, Plus, Trash2 } from '@/lib/icons'
import { cn } from '@/lib/utils'
import { notify, notifyError } from '@/store/notifications'

import { CONTROL_TEXT } from './constants'
import { EmptyState, ListRow, LoadingState, Pill, SettingsContent } from './primitives'

type AuthMode = 'oauth' | 'token'
type ProbeStatus = 'idle' | 'probing' | 'done' | 'error'

interface AddForm {
  label: string
  token: string
  url: string
}

const EMPTY_FORM: AddForm = { label: '', token: '', url: '' }

function ModeCard({
  active,
  description,
  disabled,
  icon: Icon,
  onSelect,
  title
}: {
  active: boolean
  description: string
  disabled?: boolean
  icon: typeof Monitor
  onSelect: () => void
  title: string
}) {
  return (
    <button
      className={cn(
        'w-full rounded-xl border p-3 text-left transition',
        active
          ? 'border-(--ui-stroke-secondary) bg-(--ui-bg-tertiary)'
          : 'border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) hover:bg-(--chrome-action-hover)',
        disabled && 'cursor-not-allowed opacity-50'
      )}
      disabled={disabled}
      onClick={onSelect}
      type="button"
    >
      <div className="flex items-center gap-2 text-[length:var(--conversation-text-font-size)] font-medium">
        <Icon className="size-4 text-muted-foreground" />
        <span>{title}</span>
        {active ? <Check className="ml-auto size-4 text-primary" /> : null}
      </div>
      <p className="mt-1.5 text-[length:var(--conversation-caption-font-size)] leading-(--conversation-caption-line-height) text-(--ui-text-tertiary)">
        {description}
      </p>
    </button>
  )
}

// A remote connection a gateway is bound to. Token entries can connect once a
// token is saved; OAuth entries surface a "Sign in" affordance until the
// session cookie is established, then a "Connect" button.
function ConnectionRow({
  active,
  busy,
  connection,
  envOverride,
  onActivate,
  onRemove,
  onSignIn
}: {
  active: boolean
  busy: boolean
  connection: DesktopRemoteConnection
  envOverride: boolean
  onActivate: () => void
  onRemove: () => void
  onSignIn: () => void
}) {
  const title = connection.label || connection.profile || connection.url
  const isOauth = connection.authMode === 'oauth'
  const needsSignIn = isOauth && !connection.oauthConnected
  // Token entries need a saved token; OAuth entries need a live session cookie.
  const ready = isOauth ? Boolean(connection.oauthConnected) : connection.tokenSet

  return (
    <div
      className={cn(
        'flex items-center gap-3 rounded-xl border px-3 py-2.5',
        active ? 'border-(--ui-stroke-secondary) bg-(--ui-bg-tertiary)' : 'border-(--ui-stroke-tertiary)'
      )}
    >
      <Globe className="size-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-[length:var(--conversation-text-font-size)] font-medium">
          <span className="truncate">{title}</span>
          {connection.profile ? <Pill tone="primary">{connection.profile}</Pill> : null}
          <Pill tone="muted">{isOauth ? 'OAuth' : 'token'}</Pill>
          {active ? <Pill tone="primary">connected</Pill> : null}
        </div>
        <p className="mt-0.5 truncate font-mono text-[length:var(--conversation-caption-font-size)] text-(--ui-text-tertiary)">
          {connection.url}
          {ready ? '' : isOauth ? ' · not signed in' : ' · no token'}
        </p>
      </div>
      {needsSignIn ? (
        <Button disabled={envOverride || busy} onClick={onSignIn} size="sm" variant="outline">
          <LogIn className="size-4" />
          Sign in
        </Button>
      ) : null}
      <Button
        disabled={envOverride || busy || active || !ready}
        onClick={onActivate}
        size="sm"
        variant={active ? 'outline' : 'default'}
      >
        {active ? 'Connected' : 'Connect'}
      </Button>
      <Button
        aria-label={`Remove ${title}`}
        className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
        disabled={envOverride || busy}
        onClick={onRemove}
        size="sm"
        variant="ghost"
      >
        <Trash2 className="size-4" />
      </Button>
    </div>
  )
}

export function GatewaySettings() {
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [testing, setTesting] = useState(false)
  const [config, setConfig] = useState<DesktopConnectionConfig | null>(null)
  const [form, setForm] = useState<AddForm>(EMPTY_FORM)
  const [lastTest, setLastTest] = useState<null | string>(null)

  // Auth-mode probe: as the user types a remote URL we ask the gateway (via
  // its public /api/status) whether it gates with OAuth or a static session
  // token, so the add form can show the right control (token box vs OAuth note).
  const [probeStatus, setProbeStatus] = useState<ProbeStatus>('idle')
  const [probe, setProbe] = useState<DesktopConnectionProbeResult | null>(null)
  const probeSeq = useRef(0)

  const reload = useCallback(async () => {
    const desktop = window.hermesDesktop

    if (!desktop?.connections) {
      setLoading(false)

      return
    }

    try {
      setConfig(await desktop.connections.get())
    } catch (err) {
      notifyError(err, 'Gateway settings failed to load')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  const envOverride = Boolean(config?.envOverride)
  const localActive = config?.mode === 'local'

  // Debounced probe of the entered remote URL. The probe result drives whether
  // the add form shows a session-token box or an OAuth note.
  const trimmedUrl = form.url.trim()
  useEffect(() => {
    if (!trimmedUrl || !/^https?:\/\//i.test(trimmedUrl)) {
      setProbeStatus('idle')
      setProbe(null)

      return
    }

    const desktop = window.hermesDesktop

    if (!desktop?.connections?.probe) {
      return
    }

    const seq = ++probeSeq.current
    setProbeStatus('probing')

    const timer = setTimeout(() => {
      desktop.connections
        .probe(trimmedUrl)
        .then(result => {
          if (seq !== probeSeq.current) {
            return
          }

          setProbe(result)
          setProbeStatus(result.reachable ? 'done' : 'error')
        })
        .catch(() => {
          if (seq !== probeSeq.current) {
            return
          }

          setProbe(null)
          setProbeStatus('error')
        })
    }, 500)

    return () => clearTimeout(timer)
  }, [trimmedUrl])

  const formAuthMode: AuthMode = useMemo(() => {
    if (probeStatus === 'done' && probe && probe.authMode !== 'unknown') {
      return probe.authMode
    }

    return 'token'
  }, [probe, probeStatus])

  const providerLabel = useMemo(() => {
    const providers: DesktopAuthProvider[] = probe?.providers ?? []

    if (providers.length === 1) {
      return providers[0].displayName || providers[0].name
    }

    if (providers.length > 1) {
      return providers.map(p => p.displayName || p.name).join(' / ')
    }

    return 'your identity provider'
  }, [probe])

  const switchToLocal = useCallback(async () => {
    setBusy(true)

    try {
      await window.hermesDesktop.connections.activateLocal()
      notify({ kind: 'success', title: 'Switching to local gateway', message: 'Hermes Desktop will reconnect.' })
    } catch (err) {
      notifyError(err, 'Could not switch to local gateway')
      setBusy(false)
    }
  }, [])

  const activate = useCallback(async (connection: DesktopRemoteConnection) => {
    setBusy(true)

    try {
      await window.hermesDesktop.connections.activate(connection.id)
      notify({
        kind: 'success',
        title: 'Switching connection',
        message: `Reconnecting to ${connection.label || connection.profile || connection.url}.`
      })
    } catch (err) {
      notifyError(err, 'Could not switch connection')
      setBusy(false)
    }
  }, [])

  const remove = useCallback(async (connection: DesktopRemoteConnection) => {
    setBusy(true)

    try {
      setConfig(await window.hermesDesktop.connections.remove(connection.id))
      notify({ kind: 'success', title: 'Connection removed', message: connection.label || connection.url })
    } catch (err) {
      notifyError(err, 'Could not remove connection')
    } finally {
      setBusy(false)
    }
  }, [])

  // OAuth sign-in for an existing entry: open the gateway login window for its
  // URL, then refresh so the row reflects the new cookie state.
  const signIn = useCallback(
    async (connection: DesktopRemoteConnection) => {
      setBusy(true)

      try {
        const result = await window.hermesDesktop.connections.oauthLogin(connection.url)

        if (result.connected) {
          notify({ kind: 'success', title: 'Signed in', message: `Connected to ${connection.label || connection.url}.` })
        } else {
          notify({
            kind: 'warning',
            title: 'Sign-in incomplete',
            message: 'The login window closed before authentication finished.'
          })
        }

        await reload()
      } catch (err) {
        notifyError(err, 'Sign-in failed')
      } finally {
        setBusy(false)
      }
    },
    [reload]
  )

  const testForm = useCallback(async () => {
    if (!trimmedUrl) {
      notify({ kind: 'warning', title: 'Connection incomplete', message: 'Enter a URL to test.' })

      return
    }

    setTesting(true)
    setLastTest(null)

    try {
      const result = await window.hermesDesktop.connections.test({
        token: form.token.trim() || undefined,
        url: trimmedUrl
      })

      const profile = result.profile ? ` · profile "${result.profile}"` : ''
      const message = `Reachable${result.version ? ` · Hermes ${result.version}` : ''}${profile}`
      setLastTest(message)
      notify({ kind: 'success', title: 'Gateway reachable', message })
    } catch (err) {
      notifyError(err, 'Connection test failed')
    } finally {
      setTesting(false)
    }
  }, [form.token, trimmedUrl])

  const add = useCallback(async () => {
    if (!trimmedUrl) {
      notify({ kind: 'warning', title: 'Connection incomplete', message: 'Enter a URL to add a connection.' })

      return
    }

    if (formAuthMode === 'token' && !form.token.trim()) {
      notify({
        kind: 'warning',
        title: 'Session token required',
        message: 'This gateway uses a session token — paste one to add it.'
      })

      return
    }

    setBusy(true)

    try {
      const next = await window.hermesDesktop.connections.add({
        label: form.label.trim() || undefined,
        token: form.token.trim() || undefined,
        url: trimmedUrl
      })

      setConfig(next)
      setForm(EMPTY_FORM)
      setLastTest(null)
      const added = next.remotes[next.remotes.length - 1]
      notify({
        kind: 'success',
        title: 'Connection added',
        message: added?.profile
          ? `Detected profile "${added.profile}".`
          : added?.authMode === 'oauth'
            ? 'OAuth gateway added — sign in to connect.'
            : 'Profile could not be auto-detected.'
      })
    } catch (err) {
      notifyError(err, 'Could not add connection')
    } finally {
      setBusy(false)
    }
  }, [form.label, form.token, formAuthMode, trimmedUrl])

  if (loading) {
    return <LoadingState label="Loading gateway settings..." />
  }

  if (!window.hermesDesktop?.connections || !config) {
    return (
      <EmptyState
        description="The desktop IPC bridge does not expose gateway settings."
        title="Gateway settings unavailable"
      />
    )
  }

  return (
    <SettingsContent>
      <div className="mb-5">
        <div className="flex items-center gap-2 text-[length:var(--conversation-text-font-size)] font-medium">
          <Globe className="size-4 text-muted-foreground" />
          Gateway Connection
          {envOverride ? <Pill tone="primary">env override</Pill> : null}
        </div>
        <p className="mt-2 max-w-2xl text-[length:var(--conversation-caption-font-size)] leading-(--conversation-caption-line-height) text-(--ui-text-tertiary)">
          Hermes Desktop starts its own local gateway by default. Add a remote connection for each Hermes profile you run
          elsewhere — each points at one gateway, the profile is detected automatically, and hosted gateways use OAuth
          while self-hosted ones may use a session token. Switch between them here or from the Profiles menu.
        </p>
      </div>

      {envOverride ? (
        <div className="mb-5 flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-[length:var(--conversation-caption-font-size)] text-destructive">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <div>
            <div className="font-medium">Environment variables are controlling this desktop session.</div>
            <div className="mt-1 leading-5">
              Unset <code>HERMES_DESKTOP_REMOTE_URL</code> and <code>HERMES_DESKTOP_REMOTE_TOKEN</code> to manage
              connections below.
            </div>
          </div>
        </div>
      ) : null}

      <ModeCard
        active={Boolean(localActive)}
        description="Start a private Hermes backend on localhost. This is the default and works offline."
        disabled={envOverride || busy}
        icon={Monitor}
        onSelect={() => void switchToLocal()}
        title="Local gateway"
      />

      <div className="mt-5 mb-2 text-[length:var(--conversation-caption-font-size)] font-medium uppercase tracking-[0.12em] text-(--ui-text-tertiary)">
        Remote connections
      </div>

      {config.remotes.length === 0 ? (
        <p className="rounded-xl border border-(--ui-stroke-tertiary) px-3 py-4 text-center text-[length:var(--conversation-caption-font-size)] text-(--ui-text-tertiary)">
          No remote connections yet. Add one below to connect to a profile running on another machine.
        </p>
      ) : (
        <div className="space-y-2">
          {config.remotes.map(connection => (
            <ConnectionRow
              active={config.mode === 'remote' && config.activeRemoteId === connection.id}
              busy={busy}
              connection={connection}
              envOverride={envOverride}
              key={connection.id}
              onActivate={() => void activate(connection)}
              onRemove={() => void remove(connection)}
              onSignIn={() => void signIn(connection)}
            />
          ))}
        </div>
      )}

      <div className="mt-6 rounded-xl border border-(--ui-stroke-tertiary) p-3">
        <div className="mb-2 flex items-center gap-2 text-[length:var(--conversation-text-font-size)] font-medium">
          <Plus className="size-4 text-muted-foreground" />
          Add a connection
        </div>
        <div className="divide-y divide-border/40">
          <ListRow
            action={
              <Input
                className={cn('h-8', CONTROL_TEXT)}
                disabled={envOverride}
                onChange={event => setForm(current => ({ ...current, url: event.target.value }))}
                placeholder="https://gateway.example.com/profile"
                value={form.url}
              />
            }
            description="Base URL for the remote dashboard. Path prefixes are supported, e.g. /coder."
            title="Remote URL"
          />

          {probeStatus === 'probing' ? (
            <div className="flex items-center gap-2 py-3 text-[length:var(--conversation-caption-font-size)] text-(--ui-text-tertiary)">
              <Loader2 className="size-4 animate-spin" />
              Checking how this gateway authenticates…
            </div>
          ) : null}

          {probeStatus === 'error' ? (
            <div className="flex items-start gap-2 py-3 text-[length:var(--conversation-caption-font-size)] text-(--ui-text-tertiary)">
              <AlertCircle className="mt-0.5 size-4 shrink-0" />
              Could not reach this gateway yet. Check the URL — the auth method will appear once it responds.
            </div>
          ) : null}

          {/* OAuth gateways: no token needed at add-time; sign in from the row. */}
          {probeStatus === 'done' && formAuthMode === 'oauth' ? (
            <div className="flex items-start gap-2 py-3 text-[length:var(--conversation-caption-font-size)] text-(--ui-text-tertiary)">
              <LogIn className="mt-0.5 size-4 shrink-0" />
              This gateway uses OAuth ({providerLabel}). Add it, then click "Sign in" on its row to authorize this
              desktop app.
            </div>
          ) : null}

          {/* Session-token gateways: collect the token up front. */}
          {formAuthMode === 'token' ? (
            <ListRow
              action={
                <Input
                  autoComplete="off"
                  className={cn('h-8 font-mono', CONTROL_TEXT)}
                  disabled={envOverride}
                  onChange={event => setForm(current => ({ ...current, token: event.target.value }))}
                  placeholder="Paste session token"
                  type="password"
                  value={form.token}
                />
              }
              description="The dashboard session token (HERMES_DASHBOARD_SESSION_TOKEN) for that gateway."
              title="Session token"
            />
          ) : null}

          <ListRow
            action={
              <Input
                className={cn('h-8', CONTROL_TEXT)}
                disabled={envOverride}
                onChange={event => setForm(current => ({ ...current, label: event.target.value }))}
                placeholder="Defaults to the detected profile"
                value={form.label}
              />
            }
            description="Optional friendly name for this connection."
            title="Label"
          />
        </div>

        {lastTest ? <div className="mt-3 text-xs text-primary">{lastTest}</div> : null}

        <div className="mt-4 flex flex-wrap justify-end gap-3">
          <Button disabled={envOverride || testing} onClick={() => void testForm()} variant="outline">
            {testing ? <Loader2 className="size-4 animate-spin" /> : null}
            Test
          </Button>
          <Button disabled={envOverride || busy} onClick={() => void add()}>
            {busy ? <Loader2 className="size-4 animate-spin" /> : null}
            Add connection
          </Button>
        </div>
      </div>

      <div className="mt-6 divide-y divide-border/40">
        <ListRow
          action={
            <Button onClick={() => void window.hermesDesktop?.revealLogs()} variant="outline">
              <FileText className="size-4" />
              Open logs
            </Button>
          }
          description="Reveal desktop.log in your file manager — useful when the gateway fails to start."
          title="Diagnostics"
        />
      </div>
    </SettingsContent>
  )
}
