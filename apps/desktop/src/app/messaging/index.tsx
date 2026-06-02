import type * as React from 'react'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { PageLoader } from '@/components/page-loader'
import { StatusDot, type StatusTone } from '@/components/status-dot'
import { Button } from '@/components/ui/button'
import { DisclosureCaret } from '@/components/ui/disclosure-caret'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  getMessagingPlatforms,
  type MessagingEnvVarInfo,
  type MessagingPlatformInfo,
  updateMessagingPlatform
} from '@/hermes'
import { AlertTriangle, ExternalLink, Save, Trash2 } from '@/lib/icons'
import { cn } from '@/lib/utils'
import { t, useTranslations } from '@/locales'
import { notify, notifyError } from '@/store/notifications'

import { useRouteEnumParam } from '../hooks/use-route-enum-param'
import { PageSearchShell } from '../page-search-shell'
import type { SetStatusbarItemGroup } from '../shell/statusbar-controls'

interface MessagingViewProps extends React.ComponentProps<'section'> {
  setStatusbarItemGroup?: SetStatusbarItemGroup
}

type EditMap = Record<string, Record<string, string>>

function getStateLabels(): Record<string, string> {
  const tm = t().messaging
  return {
    connected: tm.connected,
    connecting: tm.connecting,
    disabled: tm.disabled,
    fatal: tm.error,
    gateway_stopped: tm.gatewayStopped,
    not_configured: tm.needsSetup,
    pending_restart: tm.restartNeeded,
    retrying: tm.retrying,
    startup_failed: tm.startupFailed
  }
}

const PLATFORM_TINTS: Record<string, string> = {
  telegram: 'bg-sky-500/15 text-sky-600 dark:text-sky-300',
  discord: 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-300',
  slack: 'bg-violet-500/15 text-violet-600 dark:text-violet-300',
  mattermost: 'bg-blue-500/15 text-blue-600 dark:text-blue-300',
  matrix: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-300',
  signal: 'bg-cyan-500/15 text-cyan-600 dark:text-cyan-300',
  whatsapp: 'bg-green-500/15 text-green-600 dark:text-green-300',
  bluebubbles: 'bg-blue-500/15 text-blue-600 dark:text-blue-300',
  homeassistant: 'bg-teal-500/15 text-teal-600 dark:text-teal-300',
  email: 'bg-amber-500/15 text-amber-600 dark:text-amber-300',
  sms: 'bg-rose-500/15 text-rose-600 dark:text-rose-300',
  dingtalk: 'bg-blue-500/15 text-blue-600 dark:text-blue-300',
  feishu: 'bg-cyan-500/15 text-cyan-600 dark:text-cyan-300',
  wecom: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-300',
  wecom_callback: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-300',
  weixin: 'bg-green-500/15 text-green-600 dark:text-green-300',
  qqbot: 'bg-amber-500/15 text-amber-600 dark:text-amber-300',
  yuanbao: 'bg-orange-500/15 text-orange-600 dark:text-orange-300',
  api_server: 'bg-slate-500/15 text-slate-600 dark:text-slate-300',
  webhook: 'bg-zinc-500/15 text-zinc-600 dark:text-zinc-300'
}

const PILL_TONE: Record<StatusTone, string> = {
  good: 'bg-primary/10 text-primary',
  muted: 'bg-muted text-muted-foreground',
  warn: 'bg-amber-500/10 text-amber-600 dark:text-amber-300',
  bad: 'bg-destructive/10 text-destructive'
}

function getHintByState(): Record<string, string> {
  const tm = t().messaging
  return {
    pending_restart: tm.restartForChange,
    gateway_stopped: tm.startToConnect
  }
}

const stateLabel = (state?: null | string) => {
  const labels = getStateLabels()
  return state ? labels[state] || state.replace(/_/g, ' ') : 'Unknown'
}

function stateTone({ enabled, state }: MessagingPlatformInfo): StatusTone {
  if (!enabled) {
    return 'muted'
  }

  if (state === 'connected') {
    return 'good'
  }

  if (state === 'fatal' || state === 'startup_failed') {
    return 'bad'
  }

  return 'warn'
}

const trimEdits = (edits: Record<string, string>): Record<string, string> =>
  Object.fromEntries(
    Object.entries(edits)
      .map(([k, v]) => [k, v.trim()])
      .filter(([, v]) => v)
  )

function getFieldCopy(): Record<string, { advanced?: boolean; help?: string; label: string; placeholder?: string }> {
  const tm = t().messaging
  return {
    TELEGRAM_BOT_TOKEN: {
      label: tm.botToken,
      help: tm.createBot,
      placeholder: '123456:ABC...'
    },
    TELEGRAM_ALLOWED_USERS: {
      label: tm.allowedTgUsers,
      help: tm.allowedTgUsersDesc
    },
    TELEGRAM_PROXY: {
      label: tm.proxyUrl,
      help: tm.proxyDesc,
      advanced: true
    },
    DISCORD_BOT_TOKEN: {
      label: tm.botToken,
      help: tm.createDiscordApp
    },
    DISCORD_ALLOWED_USERS: {
      label: tm.allowedDiscordUsers,
      help: tm.allowedDiscordUsersDesc
    },
    DISCORD_REPLY_TO_MODE: {
      label: tm.replyStyle,
      help: tm.replyStyleDesc,
      advanced: true
    },
    SLACK_BOT_TOKEN: {
      label: tm.slackBotToken,
      help: tm.slackBotTokenDesc,
      placeholder: 'xoxb-...'
    },
    SLACK_APP_TOKEN: {
      label: tm.slackAppToken,
      help: tm.slackAppTokenDesc,
      placeholder: 'xapp-...'
    },
    SLACK_ALLOWED_USERS: {
      label: tm.allowedSlackUsers,
      help: tm.allowedSlackUsersDesc
    },
    MATTERMOST_URL: {
      label: tm.serverUrl,
      placeholder: 'https://mattermost.example.com'
    },
    MATTERMOST_TOKEN: {
      label: tm.botToken
    },
    MATTERMOST_ALLOWED_USERS: {
      label: tm.allowedUsers,
      help: tm.allowedUsersDesc
    },
    MATRIX_HOMESERVER: {
      label: tm.homeserverUrl,
      placeholder: 'https://matrix.org'
    },
    MATRIX_ACCESS_TOKEN: {
      label: tm.accessToken
    },
    MATRIX_USER_ID: {
      label: tm.botUserId,
      placeholder: '@hermes:example.org'
    },
    MATRIX_ALLOWED_USERS: {
      label: tm.allowedMatrixUsers,
      help: tm.allowedMatrixUsersDesc
    },
    SIGNAL_HTTP_URL: {
      label: tm.signalBridgeUrl,
      placeholder: 'http://127.0.0.1:8080',
      help: tm.signalBridgeDesc
    },
    SIGNAL_ACCOUNT: {
      label: tm.phoneNumber,
      help: tm.phoneNumberDesc
    },
    SIGNAL_ALLOWED_USERS: {
      label: tm.allowedSignalUsers,
      help: tm.allowedSignalUsersDesc
    },
    WHATSAPP_ENABLED: {
      label: tm.enableWhatsapp,
      help: tm.enableWhatsappDesc,
      advanced: true
    },
    WHATSAPP_MODE: {
      label: tm.bridgeMode,
      advanced: true
    },
    WHATSAPP_ALLOWED_USERS: {
      label: tm.allowedWhatsappUsers,
      help: tm.allowedWhatsappUsersDesc
    }
  }
}

function fieldCopy(field: MessagingEnvVarInfo) {
  const copy = getFieldCopy()[field.key] || {}

  return {
    label: copy.label || field.prompt || field.key,
    help: copy.help || field.description,
    placeholder: copy.placeholder || field.prompt,
    advanced: Boolean(copy.advanced || field.advanced)
  }
}

export function MessagingView({ setStatusbarItemGroup: _setStatusbarItemGroup, ...props }: MessagingViewProps) {
  const { messaging: tm } = useTranslations()
  const [platforms, setPlatforms] = useState<MessagingPlatformInfo[] | null>(null)
  const [edits, setEdits] = useState<EditMap>({})
  const [query, setQuery] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [saving, setSaving] = useState<string | null>(null)
  const platformIds = useMemo(() => platforms?.map(p => p.id) ?? [], [platforms])
  const [selectedId, setSelectedId] = useRouteEnumParam('platform', platformIds, platformIds[0] ?? '')

  const refreshPlatforms = useCallback(async (silent = false) => {
    if (!silent) {
      setRefreshing(true)
    }

    try {
      const result = await getMessagingPlatforms()
      setPlatforms(result.platforms)
    } catch (err) {
      if (!silent) {
        notifyError(err, tm.platformsFailed)
      }
    } finally {
      if (!silent) {
        setRefreshing(false)
      }
    }
  }, [tm])

  useEffect(() => {
    void refreshPlatforms()
  }, [refreshPlatforms])

  // Auto-poll while the user is on the messaging page so connection status
  // updates without a manual "check" click. Pause when the tab is hidden.
  useEffect(() => {
    let cancelled = false

    function tick() {
      if (cancelled || document.hidden) {
        return
      }

      void refreshPlatforms(true)
    }

    const id = window.setInterval(tick, 6000)

    return () => {
      cancelled = true
      window.clearInterval(id)
    }
  }, [refreshPlatforms])

  const selected = useMemo(() => {
    if (!platforms) {
      return null
    }

    return platforms.find(platform => platform.id === selectedId) || platforms[0] || null
  }, [platforms, selectedId])

  const visiblePlatforms = useMemo(() => {
    if (!platforms) {
      return []
    }

    const q = query.trim().toLowerCase()

    if (!q) {
      return platforms
    }

    return platforms.filter(platform =>
      [platform.id, platform.name, platform.description, platform.state]
        .filter(Boolean)
        .some(value => String(value).toLowerCase().includes(q))
    )
  }, [platforms, query])

  async function handleToggle(platform: MessagingPlatformInfo, enabled: boolean) {
    setSaving(`enabled:${platform.id}`)

    try {
      await updateMessagingPlatform(platform.id, { enabled })
      setPlatforms(
        current =>
          current?.map(row =>
            row.id === platform.id
              ? {
                  ...row,
                  enabled,
                  state: enabled ? (row.configured ? 'pending_restart' : 'not_configured') : 'disabled'
                }
              : row
          ) ?? current
      )
      notify({
        kind: 'success',
        title: enabled ? tm.platformEnabled.replace('{name}', platform.name) : tm.platformDisabled.replace('{name}', platform.name),
        message: tm.restartForEffect
      })
    } catch (err) {
      notifyError(err, `Failed to update ${platform.name}`)
    } finally {
      setSaving(null)
    }
  }

  async function handleSave(platform: MessagingPlatformInfo) {
    const env = trimEdits(edits[platform.id] || {})

    if (Object.keys(env).length === 0) {
      return
    }

    setSaving(`env:${platform.id}`)

    try {
      await updateMessagingPlatform(platform.id, { env })
      setEdits(current => ({ ...current, [platform.id]: {} }))
      await refreshPlatforms()
      notify({
        kind: 'success',
        title: tm.setupSaved.replace('{name}', platform.name),
        message: tm.setupSavedDesc
      })
    } catch (err) {
      notifyError(err, `Failed to save ${platform.name}`)
    } finally {
      setSaving(null)
    }
  }

  async function handleClear(platform: MessagingPlatformInfo, key: string) {
    setSaving(`clear:${key}`)

    try {
      await updateMessagingPlatform(platform.id, { clear_env: [key] })
      setEdits(current => ({
        ...current,
        [platform.id]: {
          ...(current[platform.id] || {}),
          [key]: ''
        }
      }))
      await refreshPlatforms()
      notify({ kind: 'success', title: tm.keyCleared.replace('{key}', key), message: tm.keyUpdated.replace('{name}', platform.name) })
    } catch (err) {
      notifyError(err, `Failed to clear ${key}`)
    } finally {
      setSaving(null)
    }
  }

  return (
    <PageSearchShell
      {...props}
      onSearchChange={setQuery}
      searchPlaceholder={tm.searchMessaging}
      searchTrailingAction={null}
      searchValue={query}
    >
      {!platforms ? (
        <PageLoader label={tm.loadingPlatforms} />
      ) : (
        <div className="grid h-full min-h-0 grid-cols-1 lg:grid-cols-[14rem_minmax(0,1fr)]">
          <aside className="min-h-0 overflow-y-auto border-b border-(--ui-stroke-tertiary) p-2 lg:border-b-0 lg:border-r">
            <ul className="space-y-1">
              {visiblePlatforms.map(platform => (
                <li key={platform.id}>
                  <PlatformRow
                    active={selected?.id === platform.id}
                    onSelect={() => setSelectedId(platform.id)}
                    platform={platform}
                  />
                </li>
              ))}
            </ul>
          </aside>

          <main className="min-h-0 overflow-hidden">
            {selected && (
              <PlatformDetail
                edits={edits[selected.id] || {}}
                onClear={key => void handleClear(selected, key)}
                onEdit={(key, value) =>
                  setEdits(current => ({
                    ...current,
                    [selected.id]: {
                      ...(current[selected.id] || {}),
                      [key]: value
                    }
                  }))
                }
                onSave={() => void handleSave(selected)}
                onToggle={enabled => void handleToggle(selected, enabled)}
                platform={selected}
                saving={saving}
              />
            )}
          </main>
        </div>
      )}
    </PageSearchShell>
  )
}

function PlatformRow({
  active,
  onSelect,
  platform
}: {
  active: boolean
  onSelect: () => void
  platform: MessagingPlatformInfo
}) {
  return (
    <button
      className={cn(
        'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors',
        active
          ? 'bg-(--ui-bg-tertiary) text-foreground'
          : 'text-(--ui-text-secondary) hover:bg-(--chrome-action-hover) hover:text-foreground'
      )}
      onClick={onSelect}
      type="button"
    >
      <PlatformAvatar platformId={platform.id} platformName={platform.name} />
      <span className="flex min-w-0 flex-1 items-center justify-between gap-2">
        <span className="truncate text-[length:var(--conversation-text-font-size)] font-normal">{platform.name}</span>
        <StatusDot tone={stateTone(platform)} />
      </span>
    </button>
  )
}

function PlatformAvatar({ platformId, platformName }: { platformId: string; platformName: string }) {
  return (
    <span
      className={cn(
        'inline-flex size-6 shrink-0 items-center justify-center rounded-md text-[length:var(--conversation-caption-font-size)] font-medium',
        PLATFORM_TINTS[platformId] || 'bg-(--ui-bg-tertiary) text-(--ui-text-tertiary)'
      )}
    >
      {platformName.charAt(0).toUpperCase()}
    </span>
  )
}

function PlatformDetail({
  edits,
  onClear,
  onEdit,
  onSave,
  onToggle,
  platform,
  saving
}: {
  edits: Record<string, string>
  onClear: (key: string) => void
  onEdit: (key: string, value: string) => void
  onSave: () => void
  onToggle: (enabled: boolean) => void
  platform: MessagingPlatformInfo
  saving: string | null
}) {
  const { messaging: tm, common } = useTranslations()
  const [showAdvanced, setShowAdvanced] = useState(false)

  const hasEdits = Object.keys(trimEdits(edits)).length > 0
  const requiredFields = platform.env_vars.filter(field => field.required)
  const optionalFields = platform.env_vars.filter(field => !field.required && !fieldCopy(field).advanced)
  const advancedFields = platform.env_vars.filter(field => !field.required && fieldCopy(field).advanced)
  const hiddenCount = advancedFields.length
  const isSavingEnv = saving === `env:${platform.id}`

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl space-y-5 px-5 py-4">
          <header className="flex items-start gap-3">
            <PlatformAvatar platformId={platform.id} platformName={platform.name} />
            <div className="min-w-0 flex-1">
              <h3 className="text-[0.9375rem] font-semibold tracking-tight">{platform.name}</h3>
              <p className="mt-1 text-[length:var(--conversation-caption-font-size)] leading-(--conversation-caption-line-height) text-(--ui-text-tertiary)">
                {platform.description}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <StatePill tone={stateTone(platform)}>{stateLabel(platform.state)}</StatePill>
                <SetupPill active={platform.configured}>
                  {platform.configured ? tm.credentialsSet : tm.needsSetup}
                </SetupPill>
                {!platform.gateway_running && <SetupPill active={false}>{tm.gatewayStopped}</SetupPill>}
              </div>
              <PlatformHint platform={platform} />
            </div>
          </header>

          {platform.error_message && (
            <div className="flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-[length:var(--conversation-caption-font-size)] leading-(--conversation-caption-line-height) text-destructive">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
              <span>{platform.error_message}</span>
            </div>
          )}

          <section>
            <SectionTitle>{tm.getCredentials}</SectionTitle>
            <p className="mt-1 text-[length:var(--conversation-caption-font-size)] leading-(--conversation-caption-line-height) text-(--ui-text-tertiary)">
              {introCopy(platform)}
            </p>
            <div className="mt-3">
              <Button asChild size="sm" variant="outline">
                <a href={platform.docs_url} rel="noreferrer" target="_blank">
                  {tm.openSetupGuide}
                  <ExternalLink className="size-3.5" />
                </a>
              </Button>
            </div>
          </section>

          <section>
            <SectionTitle>{common.required}</SectionTitle>
            <div className="mt-3 space-y-4">
              {requiredFields.length > 0 ? (
                requiredFields.map(field => (
                  <MessagingField
                    edits={edits}
                    field={field}
                    key={field.key}
                    onClear={onClear}
                    onEdit={onEdit}
                    saving={saving}
                  />
                ))
              ) : (
                <p className="text-[length:var(--conversation-caption-font-size)] leading-(--conversation-caption-line-height) text-(--ui-text-tertiary)">
                  {tm.noTokenNeeded}
                </p>
              )}
            </div>
          </section>

          {optionalFields.length > 0 && (
            <section>
              <SectionTitle>{common.recommended}</SectionTitle>
              <div className="mt-3 space-y-4">
                {optionalFields.map(field => (
                  <MessagingField
                    edits={edits}
                    field={field}
                    key={field.key}
                    onClear={onClear}
                    onEdit={onEdit}
                    saving={saving}
                  />
                ))}
              </div>
            </section>
          )}

          {hiddenCount > 0 && (
            <section>
              <button
                className="flex w-full items-center justify-between gap-2 rounded-lg px-1 py-1 text-left text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground hover:text-foreground"
                onClick={() => setShowAdvanced(value => !value)}
                type="button"
              >
                <span>{tm.advancedCount.replace('{count}', String(hiddenCount))}</span>
                <DisclosureCaret open={showAdvanced} size="0.875rem" />
              </button>
              {showAdvanced && (
                <div className="mt-3 space-y-4">
                  {advancedFields.map(field => (
                    <MessagingField
                      edits={edits}
                      field={field}
                      key={field.key}
                      onClear={onClear}
                      onEdit={onEdit}
                      saving={saving}
                    />
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      </div>

      <footer className="border-t border-(--ui-stroke-tertiary) bg-(--ui-chat-surface-background) px-5 py-2.5">
        <div className="mx-auto flex max-w-2xl flex-wrap items-center gap-2">
          <label className="flex shrink-0 items-center gap-2 rounded-md border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) px-2.5 py-1.5 text-[length:var(--conversation-text-font-size)]">
            <Switch
              aria-label={platform.enabled ? tm.disableName.replace('{name}', platform.name) : tm.enableName.replace('{name}', platform.name)}
              checked={platform.enabled}
              disabled={saving === `enabled:${platform.id}`}
              onCheckedChange={onToggle}
            />
            <span className="text-xs font-medium text-muted-foreground">
              {platform.enabled ? common.enabled : common.disabled}
            </span>
          </label>

          <div className="ml-auto flex items-center gap-2">
            {hasEdits && <span className="text-xs text-muted-foreground">{tm.unsavedChanges}</span>}
            <Button disabled={!hasEdits || isSavingEnv} onClick={onSave} size="sm">
              <Save />
              {isSavingEnv ? common.saving : common.save}
            </Button>
          </div>
        </div>
      </footer>
    </div>
  )
}

const PLATFORM_INTRO: Record<string, string> = {
  telegram:
    'In Telegram, talk to @BotFather, run /newbot, and copy the token it gives you. Then grab your numeric user ID from @userinfobot.',
  discord:
    'Open the Discord Developer Portal, create an application, add a Bot, then copy its token. Invite the bot to your server with the right scopes.',
  slack:
    'Create a Slack app, enable Socket Mode, install it to your workspace, then copy the Bot token (xoxb-) and App-level token (xapp-).',
  mattermost:
    'On your Mattermost server, create a bot account or personal access token, then paste the server URL and token here.',
  matrix: 'Sign in to your homeserver with the bot account, then copy the access token, user ID, and homeserver URL.',
  signal:
    'Run a signal-cli REST bridge somewhere reachable, then point Hermes at the URL and the registered phone number.',
  whatsapp:
    'Start the WhatsApp bridge that ships with Hermes, scan the QR code on first run, then enable the platform.',
  bluebubbles:
    'Run BlueBubbles Server on a Mac with iMessage, expose its API, then point Hermes at the URL with the server password.',
  homeassistant:
    'In Home Assistant, open your profile and create a long-lived access token. Paste it here along with your HA URL.',
  email:
    'Use a dedicated mailbox. For Gmail/Workspace, create an app password and use imap.gmail.com / smtp.gmail.com.',
  sms: 'Get your Twilio Account SID and Auth Token from the Twilio console, plus a phone number that can send SMS.',
  dingtalk: 'Create a DingTalk app in the developer console, then copy the Client ID (App key) and Client Secret here.',
  feishu:
    'Create a Feishu / Lark app, configure the bot capability, and copy the App ID, App secret, and event encryption keys.',
  wecom:
    'Add a group robot in WeCom and copy its webhook key as WECOM_BOT_ID. Send-only — use the WeCom (app) option for two-way.',
  wecom_callback:
    'Set up a WeCom self-built app, expose its callback URL, and provide the corp ID, secret, agent ID, and AES key.',
  weixin:
    'Sign in to the WeChat Official Account platform, copy the AppID and Token, and point the message callback URL at Hermes.',
  qqbot: 'Register an app on the QQ Open Platform (q.qq.com) and copy the App ID and Client Secret.',
  api_server:
    'Expose Hermes as an OpenAI-compatible API. Set an auth key, then point Open WebUI / LobeChat / etc. at the host:port.',
  webhook:
    'Run an HTTP server that other tools (GitHub, GitLab, custom apps) can POST to. Use the secret to verify signatures.'
}

const introCopy = (platform: MessagingPlatformInfo) => PLATFORM_INTRO[platform.id] || platform.description

function MessagingField({
  edits,
  field,
  onClear,
  onEdit,
  saving
}: {
  edits: Record<string, string>
  field: MessagingEnvVarInfo
  onClear: (key: string) => void
  onEdit: (key: string, value: string) => void
  saving: string | null
}) {
  const { messaging: tm } = useTranslations()
  const copy = fieldCopy(field)

  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap items-baseline gap-2">
        <label className="text-sm font-medium text-foreground" htmlFor={`messaging-field-${field.key}`}>
          {copy.label}
        </label>
        {field.is_set && <span className="text-[0.66rem] font-medium text-primary">{tm.savedStatus}</span>}
      </div>
      <div className="flex items-center gap-2">
        <Input
          className="h-9 rounded-lg font-mono text-sm"
          id={`messaging-field-${field.key}`}
          onChange={event => onEdit(field.key, event.target.value)}
          placeholder={field.is_set ? field.redacted_value || tm.replaceCurrent : copy.placeholder}
          type={field.is_password ? 'password' : 'text'}
          value={edits[field.key] || ''}
        />
        {field.url && (
          <Button asChild size="icon-sm" title={tm.openDocs} variant="ghost">
            <a href={field.url} rel="noreferrer" target="_blank">
              <ExternalLink className="size-3.5" />
            </a>
          </Button>
        )}
        {field.is_set && (
          <Button
            disabled={saving === `clear:${field.key}`}
            onClick={() => onClear(field.key)}
            size="icon-sm"
            title={`Clear ${field.key}`}
            variant="ghost"
          >
            <Trash2 className="size-3.5" />
          </Button>
        )}
      </div>
      {copy.help && <p className="text-xs leading-5 text-muted-foreground">{copy.help}</p>}
    </div>
  )
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h4 className="text-[0.7rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">{children}</h4>
}

function PlatformHint({ platform }: { platform: MessagingPlatformInfo }) {
  const hints = getHintByState()

  if (!platform.enabled || platform.state === 'connected') {
    return null
  }

  const hint = hints[platform.state || ''] || (platform.gateway_running ? null : hints.gateway_stopped)

  return hint ? <p className="mt-2 text-xs leading-5 text-muted-foreground">{hint}</p> : null
}

function StatePill({ children, tone }: { children: string; tone: StatusTone }) {
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-[0.66rem] font-medium',
        PILL_TONE[tone]
      )}
    >
      <StatusDot tone={tone} />
      {children}
    </span>
  )
}

function SetupPill({ active, children }: { active: boolean; children: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2 py-0.5 text-[0.66rem] font-medium',
        PILL_TONE[active ? 'good' : 'muted']
      )}
    >
      {children}
    </span>
  )
}
