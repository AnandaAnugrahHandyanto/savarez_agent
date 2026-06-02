import { useStore } from '@nanostores/react'
import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'

import { ModelPickerDialog } from '@/components/model-picker'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { getGlobalModelOptions } from '@/hermes'
import {
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  KeyRound,
  Loader2,
  Sparkles,
  Terminal
} from '@/lib/icons'
import { isProviderSetupErrorMessage } from '@/lib/provider-setup-errors'
import { cn } from '@/lib/utils'
import { t, tp, useTranslations } from '@/locales'
import { $desktopBoot, type DesktopBootState } from '@/store/boot'
import {
  $desktopOnboarding,
  cancelOnboardingFlow,
  closeManualOnboarding,
  confirmOnboardingModel,
  copyDeviceCode,
  copyExternalCommand,
  type OnboardingContext,
  type OnboardingFlow,
  recheckExternalSignin,
  refreshOnboarding,
  saveOnboardingApiKey,
  setOnboardingCode,
  setOnboardingMode,
  setOnboardingModel,
  startProviderOAuth,
  submitOnboardingCode
} from '@/store/onboarding'
import type { OAuthProvider } from '@/types/hermes'

interface DesktopOnboardingOverlayProps {
  enabled: boolean
  onCompleted?: () => void
  requestGateway: OnboardingContext['requestGateway']
}

interface ApiKeyOption {
  description: string
  docsUrl: string
  envKey: string
  id: string
  name: string
  placeholder?: string
  short?: string
}

const MIN_KEY_LENGTH = 8

const getApiKeyOptions = (): ApiKeyOption[] => {
  const tr = t().onboarding
  return [
    {
      id: 'openrouter',
      name: tr.openrouterKey,
      short: tr.oneKeyModels,
      envKey: 'OPENROUTER_API_KEY',
      description: tr.oneKeyDesc,
      docsUrl: 'https://openrouter.ai/keys'
    },
    {
      id: 'openai',
      name: 'OpenAI',
      short: tr.gptModels,
      envKey: 'OPENAI_API_KEY',
      description: tr.gptDesc,
      docsUrl: 'https://platform.openai.com/api-keys'
    },
    {
      id: 'gemini',
      name: 'Google Gemini',
      short: tr.geminiModels,
      envKey: 'GEMINI_API_KEY',
      description: tr.geminiDesc,
      docsUrl: 'https://aistudio.google.com/app/apikey'
    },
    {
      id: 'xai',
      name: 'xAI Grok',
      short: tr.grokModels,
      envKey: 'XAI_API_KEY',
      description: tr.grokDesc,
      docsUrl: 'https://console.x.ai/'
    },
    {
      id: 'local',
      name: tr.localEndpoint,
      short: tr.selfHosted,
      envKey: 'OPENAI_BASE_URL',
      description: tr.localDesc,
      docsUrl: 'https://github.com/NousResearch/hermes-agent#bring-your-own-endpoint',
      placeholder: 'http://127.0.0.1:8000/v1'
    }
  ]
}

const getProviderDisplay = (): Record<string, { order: number; title: string }> => {
  const tr = t().onboarding
  return {
    nous: { order: 0, title: tr.nousPortal },
    anthropic: { order: 1, title: tr.anthropicClaude },
    'openai-codex': { order: 2, title: tr.openaiCodex },
    'minimax-oauth': { order: 3, title: tr.minimax },
    'claude-code': { order: 4, title: tr.claudeCode },
    'qwen-oauth': { order: 5, title: tr.qwenCode }
  }
}

const assetPath = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\/+/, '')}`

const getFlowSubtitles = (): Record<OAuthProvider['flow'], string> => {
  const tr = t().onboarding
  return {
    pkce: tr.flowPkce,
    device_code: tr.flowDeviceCode,
    external: tr.flowExternal
  }
}

const providerTitle = (p: OAuthProvider) => getProviderDisplay()[p.id]?.title ?? p.name
const orderOf = (p: OAuthProvider) => getProviderDisplay()[p.id]?.order ?? 99

const sortProviders = (providers: OAuthProvider[]) =>
  [...providers].sort((a, b) => orderOf(a) - orderOf(b) || a.name.localeCompare(b.name))

export function DesktopOnboardingOverlay({ enabled, onCompleted, requestGateway }: DesktopOnboardingOverlayProps) {
  const onboarding = useStore($desktopOnboarding)
  const boot = useStore($desktopBoot)
  const ctxRef = useRef<OnboardingContext>({ requestGateway, onCompleted })
  ctxRef.current = { requestGateway, onCompleted }

  const ctx = useMemo<OnboardingContext>(
    () => ({
      requestGateway: (...args) => ctxRef.current.requestGateway(...args),
      onCompleted: () => ctxRef.current.onCompleted?.()
    }),
    []
  )

  useEffect(() => {
    if (enabled || onboarding.requested) {
      void refreshOnboarding(ctx)
    }
  }, [ctx, enabled, onboarding.requested])

  // Mount from frame 1 so we replace the boot overlay seamlessly. The
  // configured field stays null until the runtime check resolves; only then
  // do we know whether to dismiss (true) or surface the picker (false).
  // EXCEPTION: manual mode (user opened the selector from a working app to
  // add/switch a provider) shows the overlay regardless of configured state.
  if (onboarding.configured === true && !onboarding.manual) {
    return null
  }

  const { flow } = onboarding
  const rawReason = onboarding.reason?.trim() || null
  const reason = rawReason && !isProviderSetupErrorMessage(rawReason) ? rawReason : null
  // In manual mode the app is already configured, so the flow is "ready"
  // immediately — no runtime gate needed. Otherwise wait for the readiness
  // check (configured === false) before showing the picker.
  const ready = onboarding.manual || (enabled && onboarding.configured === false)
  const showPicker = flow.status === 'idle' || flow.status === 'success'

  return (
    <div className="fixed inset-0 z-1300 flex items-center justify-center bg-(--ui-chat-surface-background) p-6">
      <div className="w-full max-w-[45rem] overflow-hidden rounded-xl border border-(--ui-stroke-secondary) bg-(--ui-chat-bubble-background) shadow-sm">
        <Header />
        <div className="grid gap-3 p-5">
          {onboarding.manual ? (
            <div className="flex justify-end">
              <button
                className="text-xs font-medium text-muted-foreground transition hover:text-foreground"
                onClick={() => closeManualOnboarding()}
                type="button"
              >
                {t().common.close}
              </button>
            </div>
          ) : null}
          {reason ? <ReasonNotice reason={reason} /> : null}
          {ready ? showPicker ? <Picker ctx={ctx} /> : <FlowPanel ctx={ctx} flow={flow} /> : <Preparing boot={boot} />}
        </div>
      </div>
    </div>
  )
}

function ReasonNotice({ reason }: { reason: string }) {
  return (
    <div className="rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      {reason}
    </div>
  )
}

function Preparing({ boot }: { boot: DesktopBootState }) {
  const tr = useTranslations()
  const progress = Math.max(2, Math.min(100, Math.round(boot.progress)))
  const hasError = Boolean(boot.error)
  const installing = boot.phase.startsWith('runtime.')

  return (
    <div className="grid gap-3" role="status">
      <p className="text-sm text-muted-foreground">
        {installing
          ? tr.onboarding.finishingInstall
          : tr.onboarding.starting}
      </p>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            'h-full rounded-full bg-primary transition-[width] duration-300 ease-out',
            hasError && 'bg-destructive'
          )}
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
        <span className="truncate">{boot.message}</span>
        <span>{progress}%</span>
      </div>
      {hasError ? <p className="text-xs text-destructive">{boot.error}</p> : null}
    </div>
  )
}

function Header() {
  const tr = useTranslations()
  return (
    <div className="border-b border-(--ui-stroke-tertiary) bg-(--ui-chat-bubble-background) px-5 py-4">
      <div className="flex items-start gap-3">
        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-(--ui-bg-tertiary) text-(--ui-text-tertiary)">
          <Sparkles className="size-5" />
        </div>
        <div>
          <h2 className="text-[0.9375rem] font-semibold tracking-tight">{tr.onboarding.setupTitle}</h2>
          <p className="mt-1 max-w-xl text-[0.8125rem] leading-5 text-(--ui-text-tertiary)">
            {tr.onboarding.setupDesc}
          </p>
        </div>
      </div>
    </div>
  )
}

const FEATURED_ID = 'nous'
const SHOW_ALL_KEY = 'hermes-onboarding-show-all-v1'

const readShowAll = () => {
  try {
    return window.localStorage.getItem(SHOW_ALL_KEY) === '1'
  } catch {
    return false
  }
}

const persistShowAll = (value: boolean) => {
  try {
    window.localStorage.setItem(SHOW_ALL_KEY, value ? '1' : '0')
  } catch {
    // localStorage unavailable — degrade silently.
  }

  return value
}

export function Picker({ ctx }: { ctx: OnboardingContext }) {
  const tr = useTranslations()
  const { mode, providers } = useStore($desktopOnboarding)
  const [showAll, setShowAll] = useState(readShowAll)
  const ordered = useMemo(() => (providers ? sortProviders(providers) : []), [providers])
  const hasOauth = ordered.length > 0

  if (mode === 'apikey' || !hasOauth) {
    return <ApiKeyForm canGoBack={hasOauth} ctx={ctx} />
  }

  if (providers === null) {
    return <Status>{tr.onboarding.lookingUpProviders}</Status>
  }

  const select = (p: OAuthProvider) => void startProviderOAuth(p, ctx)
  const featured = ordered.find(p => p.id === FEATURED_ID) ?? null
  const rest = featured ? ordered.filter(p => p.id !== FEATURED_ID) : ordered
  // Collapse the secondary providers behind a disclosure only when Nous
  // Portal is present to anchor the choice — otherwise show the full list.
  const collapsible = Boolean(featured) && rest.length > 0
  const showRest = !collapsible || showAll

  return (
    <div className="grid gap-2">
      {featured ? <FeaturedProviderRow onSelect={select} provider={featured} /> : null}
      {showRest ? (
        <>
          {rest.map(p => (
            <ProviderRow key={p.id} onSelect={select} provider={p} />
          ))}
          <KeyProviderRow onClick={() => setOnboardingMode('apikey')} />
        </>
      ) : null}
      {collapsible ? (
        <button
          className="flex items-center justify-center gap-1.5 pt-1 text-xs font-medium text-muted-foreground transition hover:text-foreground"
          onClick={() => setShowAll(persistShowAll(!showAll))}
          type="button"
        >
          {showAll ? tr.common.collapse : tr.onboarding.otherProviders}
          <ChevronDown className={cn('size-3.5 transition', showAll && 'rotate-180')} />
        </button>
      ) : null}
      <div className="flex justify-end pt-1">
        <button
          className="text-xs font-medium text-muted-foreground hover:text-foreground"
          onClick={() => setOnboardingMode('apikey')}
          type="button"
        >
          {tr.onboarding.haveApiKey}
        </button>
      </div>
    </div>
  )
}

function FeaturedProviderRow({
  onSelect,
  provider
}: {
  onSelect: (provider: OAuthProvider) => void
  provider: OAuthProvider
}) {
  const tr = useTranslations()
  const loggedIn = provider.status?.logged_in

  return (
    <button
      className={cn(
        'group flex w-full items-center justify-between gap-4 rounded-2xl border-2 border-primary/50 bg-primary/5 p-4 text-left transition hover:border-primary hover:bg-primary/10',
        loggedIn && 'border-primary'
      )}
      onClick={() => onSelect(provider)}
      type="button"
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <img alt="" className="size-5 shrink-0 rounded" src={assetPath('apple-touch-icon.png')} />
          <span className="text-base font-semibold">{providerTitle(provider)}</span>
          {loggedIn ? (
            <ConnectedTag />
          ) : (
            <span className="inline-flex items-center gap-1.5 bg-primary px-2 py-0.5 text-[0.64rem] font-semibold uppercase tracking-[0.16em] text-primary-foreground">
              <span aria-hidden="true" className="dither inline-block size-2 shrink-0" />
              {tr.onboarding.recommendedTag}
            </span>
          )}
        </div>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{tr.onboarding.featuredPitch}</p>
      </div>
      <ChevronRight className="size-5 shrink-0 text-primary transition group-hover:translate-x-0.5" />
    </button>
  )
}

function ConnectedTag() {
  const tr = useTranslations()
  return (
    <span className="inline-flex items-center gap-1 bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
      <Check className="size-3" />
      {tr.onboarding.connectedTag}
    </span>
  )
}

function KeyProviderRow({ onClick }: { onClick: () => void }) {
  const tr = useTranslations()
  return (
    <button
      className="group flex w-full items-center justify-between gap-3 rounded-2xl border border-border bg-background/60 p-3 text-left transition hover:border-primary/40 hover:bg-accent/40"
      onClick={onClick}
      type="button"
    >
      <div className="min-w-0">
        <span className="text-sm font-semibold">{tr.onboarding.openrouterKey}</span>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{tr.onboarding.openrouterKeyDesc}</p>
      </div>
      <ChevronRight className="size-4 text-muted-foreground transition group-hover:text-foreground" />
    </button>
  )
}

function ProviderRow({ onSelect, provider }: { onSelect: (provider: OAuthProvider) => void; provider: OAuthProvider }) {
  const loggedIn = provider.status?.logged_in
  const Trail = provider.flow === 'external' ? Terminal : ChevronRight

  return (
    <button
      className={cn(
        'group flex w-full items-center justify-between gap-3 rounded-2xl border border-border bg-background/60 p-3 text-left transition hover:border-primary/40 hover:bg-accent/40',
        loggedIn && 'border-primary/30'
      )}
      onClick={() => onSelect(provider)}
      type="button"
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">{providerTitle(provider)}</span>
          {loggedIn ? <ConnectedTag /> : null}
        </div>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">{getFlowSubtitles()[provider.flow]}</p>
      </div>
      <Trail className="size-4 text-muted-foreground transition group-hover:text-foreground" />
    </button>
  )
}

function ApiKeyForm({ canGoBack, ctx }: { canGoBack: boolean; ctx: OnboardingContext }) {
  const tr = useTranslations()
  const [option, setOption] = useState<ApiKeyOption>(() => getApiKeyOptions()[0])
  const [value, setValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<null | string>(null)

  const apiKeyOptions = getApiKeyOptions()
  const isLocal = option.envKey === 'OPENAI_BASE_URL'
  const canSave = value.trim().length >= (isLocal ? 1 : MIN_KEY_LENGTH)

  const submit = async () => {
    if (!canSave || saving) {
      return
    }

    setSaving(true)
    setError(null)
    const result = await saveOnboardingApiKey(option.envKey, value, option.name, ctx)

    if (result.ok) {
      setValue('')
    } else {
      setError(result.message ?? 'Could not save credential.')
    }

    setSaving(false)
  }

  return (
    <div className="grid gap-4">
      {canGoBack ? (
        <button
          className="-mt-1 flex items-center gap-1 self-start text-xs font-medium text-muted-foreground hover:text-foreground"
          onClick={() => setOnboardingMode('oauth')}
          type="button"
        >
          <ChevronLeft className="size-3" />
          {tr.onboarding.backToSignIn}
        </button>
      ) : null}

      <div className="grid gap-2 sm:grid-cols-2">
        {apiKeyOptions.map(o => (
          <button
            className={cn(
              'rounded-2xl border bg-background/60 p-3 text-left transition hover:bg-accent/50',
              option.id === o.id ? 'border-primary ring-2 ring-primary/20' : 'border-border'
            )}
            key={o.id}
            onClick={() => {
              setOption(o)
              setValue('')
              setError(null)
            }}
            type="button"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">{o.name}</span>
              {option.id === o.id ? <Check className="size-4 text-primary" /> : null}
            </div>
            {o.short ? <p className="mt-1 text-xs text-muted-foreground">{o.short}</p> : null}
          </button>
        ))}
      </div>

      <div className="grid gap-2">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm leading-6 text-muted-foreground">{option.description}</p>
          {option.docsUrl ? <DocsLink href={option.docsUrl}>{tr.onboarding.getKey}</DocsLink> : null}
        </div>
        <Input
          autoComplete="off"
          autoFocus
          className="font-mono"
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && void submit()}
          placeholder={option.placeholder || tr.onboarding.pasteApiKey}
          type={isLocal ? 'text' : 'password'}
          value={value}
        />
        {error ? <p className="text-xs text-destructive">{error}</p> : null}
      </div>

      <div className="flex justify-end">
        <Button disabled={!canSave || saving} onClick={() => void submit()}>
          {saving ? <Loader2 className="size-4 animate-spin" /> : <KeyRound className="size-4" />}
          {saving ? tr.common.connecting : tr.common.connect}
        </Button>
      </div>
    </div>
  )
}

function FlowPanel({ ctx, flow }: { ctx: OnboardingContext; flow: OnboardingFlow }) {
  const title = 'provider' in flow && flow.provider ? providerTitle(flow.provider) : ''

  if (flow.status === 'starting') {
    return <Status>{tp('onboarding.startSignIn', { title })}</Status>
  }

  if (flow.status === 'submitting') {
    return <Status>{tp('onboarding.verifyingCode', { title })}</Status>
  }

  if (flow.status === 'success') {
    return (
      <div className="flex items-center gap-2 rounded-2xl border border-primary/30 bg-primary/10 px-4 py-3 text-sm text-primary">
        <Check className="size-4" />
        {tp('onboarding.connectedPicking', { title })}
      </div>
    )
  }

  if (flow.status === 'confirming_model') {
    return <ConfirmingModelPanel ctx={ctx} flow={flow} />
  }

  if (flow.status === 'error') {
    return (
      <div className="grid gap-3">
        <div className="rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {flow.message || t().onboarding.signInFailed}
        </div>
        <div className="flex justify-end">
          <Button onClick={cancelOnboardingFlow} variant="outline">
            {t().onboarding.pickDifferent}
          </Button>
        </div>
      </div>
    )
  }

  if (flow.status === 'awaiting_user') {
    return (
      <Step title={tp('onboarding.signInWith', { title })}>
        <ol className="list-decimal space-y-1 pl-5 text-sm text-muted-foreground">
          <li>{tp('onboarding.openedBrowser', { title })}</li>
          <li>{t().onboarding.authorizeHermes}</li>
          <li>{t().onboarding.copyAuthCode}</li>
        </ol>
        <Input
          autoFocus
          onChange={e => setOnboardingCode(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && void submitOnboardingCode(ctx)}
          placeholder={t().onboarding.pasteAuthCode}
          value={flow.code}
        />
        <FlowFooter left={<DocsLink href={flow.start.auth_url}>{t().onboarding.reopenAuth}</DocsLink>}>
          <CancelBtn />
          <Button disabled={!flow.code.trim()} onClick={() => void submitOnboardingCode(ctx)}>
            {t().onboarding.continue_}
          </Button>
        </FlowFooter>
      </Step>
    )
  }

  if (flow.status === 'external_pending') {
    return (
      <Step title={tp('onboarding.signInWith', { title })}>
        <p className="text-sm text-muted-foreground">
          {tp('onboarding.cliSignIn', { title })}
        </p>
        <CodeBlock copied={flow.copied} onCopy={() => void copyExternalCommand()} text={flow.provider.cli_command} />
        <FlowFooter
          left={flow.provider.docs_url ? <DocsLink href={flow.provider.docs_url}>{tp('onboarding.docsLink', { title })}</DocsLink> : null}
        >
          <CancelBtn />
          <Button onClick={() => void recheckExternalSignin(ctx)}>
            <Check className="size-4" />
            {t().onboarding.iveSignedIn}
          </Button>
        </FlowFooter>
      </Step>
    )
  }

  if (flow.status !== 'polling') {
    return null
  }

  return (
    <Step title={tp('onboarding.signInWith', { title })}>
      <p className="text-sm text-muted-foreground">{tp('onboarding.enterCode', { title })}</p>
      <CodeBlock copied={flow.copied} large onCopy={() => void copyDeviceCode()} text={flow.start.user_code} />
      <FlowFooter left={<DocsLink href={flow.start.verification_url}>{t().onboarding.reopenVerification}</DocsLink>}>
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3 animate-spin" />
          {t().onboarding.waitingAuth}
        </span>
        <CancelBtn size="sm" />
      </FlowFooter>
    </Step>
  )
}

function Step({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <div className="grid gap-4">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </div>
  )
}

function CodeBlock({
  copied,
  large,
  onCopy,
  text
}: {
  copied: boolean
  large?: boolean
  onCopy: () => void
  text: string
}) {
  const tr = useTranslations()
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-secondary/30 px-4 py-3">
      <code className={cn('font-mono', large ? 'text-2xl tracking-[0.4em]' : 'text-sm')}>{text}</code>
      <Button onClick={onCopy} size="sm" variant="outline">
        {copied ? <Check className="size-4" /> : tr.common.copy}
      </Button>
    </div>
  )
}

function FlowFooter({ children, left }: { children: React.ReactNode; left?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">{left}</div>
      <div className="flex items-center gap-3">{children}</div>
    </div>
  )
}

function CancelBtn({ size = 'default' }: { size?: 'default' | 'sm' }) {
  const tr = useTranslations()
  return (
    <Button onClick={cancelOnboardingFlow} size={size} variant="ghost">
      {tr.common.cancel}
    </Button>
  )
}

function ConfirmingModelPanel({
  ctx,
  flow
}: {
  ctx: OnboardingContext
  flow: Extract<OnboardingFlow, { status: 'confirming_model' }>
}) {
  const tr = useTranslations()
  // Local state controls whether the model picker dialog is open.
  // We reuse the existing ModelPickerDialog component (the same picker
  // available from the chat shell) rather than building an inline
  // dropdown — gives us search, multi-provider listing if relevant, and
  // a familiar UI for users who'll see this picker again later.
  const [pickerOpen, setPickerOpen] = useState(false)

  // Pull pricing + tier for the just-picked default so the confirm card
  // shows the same $/Mtok + Free/Pro info the picker and CLI do.
  const options = useQuery({
    queryKey: ['onboarding-model-options', flow.providerSlug],
    queryFn: () => getGlobalModelOptions()
  })
  const providerRow = options.data?.providers?.find(
    p => String(p.slug).toLowerCase() === flow.providerSlug.toLowerCase()
  )
  const price = providerRow?.pricing?.[flow.currentModel]
  const freeTier = providerRow?.free_tier

  return (
    <div className="grid gap-4">
      <div className="flex items-center gap-2 rounded-2xl border border-primary/30 bg-primary/10 px-4 py-3 text-sm text-primary">
        <Check className="size-4 shrink-0" />
        <span>{tp('onboarding.connectedLabel', { title: flow.label })}</span>
      </div>

      <div className="grid gap-3 rounded-2xl border border-border bg-background/60 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">{tr.onboarding.defaultModel}</p>
              {freeTier === true && (
                <span className="rounded-sm bg-emerald-500/15 px-1 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
                  {tr.onboarding.freeTier}
                </span>
              )}
              {freeTier === false && (
                <span className="rounded-sm bg-primary/15 px-1 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide text-primary">
                  {tr.onboarding.pro}
                </span>
              )}
            </div>
            <p className="mt-1 truncate font-mono text-sm">{flow.currentModel}</p>
            {price && (price.input || price.output) && (
              <p className="mt-1 font-mono text-xs text-muted-foreground">
                {price.free
                  ? tr.onboarding.free
                  : tp('onboarding.pricePerMtok', {
                      inputPrice: price.input || '?',
                      outputPrice: price.output || '?'
                    })}
              </p>
            )}
          </div>
          <Button disabled={flow.saving} onClick={() => setPickerOpen(true)} size="sm" variant="outline">
            {tr.common.change}
          </Button>
        </div>
      </div>

      <div className="flex justify-end">
        <Button disabled={flow.saving} onClick={() => confirmOnboardingModel(ctx)}>
          {flow.saving ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
          {tr.onboarding.startChatting}
        </Button>
      </div>

      {/*
        ModelPickerDialog defaults to z-130 on its content, which renders
        UNDER the onboarding overlay (z-1300) and breaks pointer events.
        Bump it above with z-[1310] so the picker sits on top of the
        onboarding panel. The dialog's own dim-backdrop layer stays at
        its default z-120 — the onboarding overlay is already dimming
        the rest of the screen, so we don't want a second backdrop.
      */}
      <ModelPickerDialog
        contentClassName="z-[1310]"
        currentModel={flow.currentModel}
        currentProvider={flow.providerSlug}
        onOpenChange={setPickerOpen}
        onSelect={({ model }) => {
          void setOnboardingModel(model)
          setPickerOpen(false)
        }}
        open={pickerOpen}
      />
    </div>
  )
}

function DocsLink({ children, href }: { children: React.ReactNode; href: string }) {
  return (
    <Button asChild size="xs" variant="ghost">
      <a href={href} rel="noreferrer" target="_blank">
        <ExternalLink className="size-3" />
        {children}
      </a>
    </Button>
  )
}

function Status({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-muted/30 px-4 py-6 text-sm text-muted-foreground">
      <Loader2 className="size-4 animate-spin" />
      {children}
    </div>
  )
}
