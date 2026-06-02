import { useStore } from '@nanostores/react'
import { useState } from 'react'
import { useT } from '@/locales'

import { Button } from '@/components/ui/button'
import { CheckCircle2, ExternalLink, Loader2, RefreshCw, Sparkles } from '@/lib/icons'
import { cn } from '@/lib/utils'
import {
  $desktopVersion,
  $updateApply,
  $updateChecking,
  $updateStatus,
  checkUpdates,
  openUpdatesWindow
} from '@/store/updates'

import { ListRow, SectionHeading, SettingsContent } from './primitives'

const RELEASE_NOTES_URL = 'https://github.com/NousResearch/hermes-agent/releases'

function relativeTime(ms: number | undefined, t: (key: string, params?: Record<string, string | number>) => string) {
  if (!ms) {
    return t('about.never')
  }

  const diff = Date.now() - ms

  if (diff < 60_000) {
    return t('about.justNow')
  }

  if (diff < 3_600_000) {
    return t('about.minAgo', { n: Math.round(diff / 60_000) })
  }

  if (diff < 86_400_000) {
    return t('about.hoursAgo', { n: Math.round(diff / 3_600_000) })
  }

  return t('about.daysAgo', { n: Math.round(diff / 86_400_000) })
}

export function AboutSettings() {
  const t = useT()
  const version = useStore($desktopVersion)
  const status = useStore($updateStatus)
  const apply = useStore($updateApply)
  const checking = useStore($updateChecking)
  const [justChecked, setJustChecked] = useState(false)

  const behind = status?.behind ?? 0
  const supported = status?.supported !== false
  const applying = apply.applying || apply.stage === 'restart'

  const handleCheck = async () => {
    setJustChecked(false)
    const next = await checkUpdates()
    setJustChecked(Boolean(next))
  }

  let statusLine: string
  let statusTone: 'idle' | 'available' | 'error' = 'idle'

  if (!supported) {
    statusLine = status?.message ?? t('about.cantSelfUpdate')
    statusTone = 'error'
  } else if (status?.error) {
    statusLine = t('about.updateServerUnreachable')
    statusTone = 'error'
  } else if (applying) {
    statusLine = t('about.updateInstalling')
    statusTone = 'available'
  } else if (behind > 0) {
    statusLine = t('about.updateReady', { n: behind })
    statusTone = 'available'
  } else if (status) {
    statusLine = t('about.latestVersion')
  } else {
    statusLine = t('about.tapCheckNow')
  }

  return (
    <SettingsContent>
      <div className="flex flex-col items-center gap-3 pt-6 pb-2 text-center">
        <span className="flex size-16 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <Sparkles className="size-8" />
        </span>
        <div>
          <h2 className="text-lg font-semibold tracking-tight">{t('about.hermesDesktop')}</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {version?.appVersion ? t('about.version', { x: version.appVersion }) : t('about.versionUnavailable')}
          </p>
        </div>
      </div>

      <div className="mx-auto mt-4 w-full max-w-2xl">
        <SectionHeading icon={RefreshCw} title={t('about.updates')} />

        <div
          className={cn(
            'rounded-xl border px-4 py-3 text-sm',
            statusTone === 'available' && 'border-primary/30 bg-primary/5 text-foreground',
            statusTone === 'error' && 'border-destructive/35 bg-destructive/5 text-destructive',
            statusTone === 'idle' && 'border-border/70 bg-muted/20 text-foreground'
          )}
        >
          <div className="flex items-start gap-2">
            {statusTone === 'available' ? (
              <Sparkles className="mt-0.5 size-4 shrink-0 text-primary" />
            ) : statusTone === 'error' ? null : (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
            )}
            <div className="min-w-0">
              <p className="font-medium">{statusLine}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {t('about.lastChecked', { x: relativeTime(status?.fetchedAt, t) })}
                {justChecked && !checking ? ` · ${t('about.justNow')}` : ''}
              </p>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button
              disabled={checking || applying || !supported}
              onClick={() => void handleCheck()}
              size="sm"
              variant="outline"
            >
              {checking ? <Loader2 className="size-3 animate-spin" /> : <RefreshCw className="size-3" />}
              {checking ? t('about.checking') : t('about.checkNow')}
            </Button>

            {behind > 0 && supported && !applying && (
              <Button onClick={() => openUpdatesWindow()} size="sm">
                {t('about.seeWhatsNew')}
              </Button>
            )}

            <Button
              asChild
              className="ml-auto text-xs text-muted-foreground hover:text-foreground"
              size="sm"
              variant="ghost"
            >
              <a
                href={RELEASE_NOTES_URL}
                onClick={event => {
                  event.preventDefault()
                  void window.hermesDesktop?.openExternal?.(RELEASE_NOTES_URL)
                }}
                rel="noreferrer"
                target="_blank"
              >
                <ExternalLink className="size-3" />
                {t('about.releaseNotes')}
              </a>
            </Button>
          </div>
        </div>

        <ListRow
          description={t('about.autoUpdateDesc')}
          hint={`Branch ${status?.branch ?? 'unknown'} · Commit ${status?.currentSha?.slice(0, 7) ?? 'unknown'}`}
          title={t('about.autoUpdates')}
        />
      </div>
    </SettingsContent>
  )
}
