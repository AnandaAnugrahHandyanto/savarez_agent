import { useStore } from '@nanostores/react'
import {
  IconBookmark,
  IconBookmarkFilled,
  IconDownload,
  IconRefresh,
  IconTrash
} from '@tabler/icons-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { PageLoader } from '@/components/page-loader'
import { Button } from '@/components/ui/button'
import { SearchField } from '@/components/ui/search-field'
import { SegmentedControl } from '@/components/ui/segmented-control'
import {
  getActionStatus,
  getLogs,
  getStatus,
  getUsageAnalytics,
  restartGateway,
  updateHermes
} from '@/hermes'
import type { ActionStatusResponse, AnalyticsResponse, StatusResponse } from '@/hermes'
import { useI18n } from '@/i18n'
import { sessionTitle } from '@/lib/chat-runtime'
import { Activity, AlertCircle, BarChart3, Pin } from '@/lib/icons'
import { exportSession } from '@/lib/session-export'
import { cn } from '@/lib/utils'
import { upsertDesktopActionTask } from '@/store/activity'
import { $pinnedSessionIds, pinSession, unpinSession } from '@/store/layout'
import { $sessions } from '@/store/session'

import { useRefreshHotkey } from '../hooks/use-refresh-hotkey'
import { useRouteEnumParam } from '../hooks/use-route-enum-param'
import { OverlayActionButton, OverlayCard, overlayCardClass, OverlayIconButton } from '../overlays/overlay-chrome'
import { OverlaySearchInput } from '../overlays/overlay-search-input'
import { OverlayMain, OverlayNavItem, OverlaySidebar, OverlaySplitLayout } from '../overlays/overlay-split-layout'
import { OverlayView } from '../overlays/overlay-view'
import { ARTIFACTS_ROUTE, MESSAGING_ROUTE, NEW_CHAT_ROUTE, SETTINGS_ROUTE, SKILLS_ROUTE } from '../routes'

export type CommandCenterSection = 'sessions' | 'system' | 'usage'

const SECTIONS = ['sessions', 'system', 'usage'] as const satisfies readonly CommandCenterSection[]

const USAGE_PERIODS = [7, 30, 90] as const
type UsagePeriod = (typeof USAGE_PERIODS)[number]

interface CommandCenterViewProps {
  initialSection?: CommandCenterSection
  onClose: () => void
  onDeleteSession: (sessionId: string) => Promise<void>
  // Accepted for call-site parity; navigation lives in the global Cmd+K palette.
  onNavigateRoute?: (path: string) => void
  onOpenSession: (sessionId: string) => void
}

function formatTimestamp(value?: number | null): string {
  if (!value) {
    return ''
  }

  const date = new Date(value * 1000)

  if (Number.isNaN(date.getTime())) {
    return ''
  }

  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}

function splitSessionSearchResult(result: SessionSearchApiResult, sessionsById: Map<string, SessionInfo>) {
  const row = sessionsById.get(result.session_id)
  const title = row ? sessionTitle(row) : result.session_id
  const detail = [result.model, result.source].filter(Boolean).join(' · ')

  return { detail, title }
}

function matchesSearchQuery(query: string, ...values: Array<string | undefined>): boolean {
  const normalized = query.trim().toLowerCase()

  if (!normalized) {
    return true
  }

  return values.some(value => value?.toLowerCase().includes(normalized))
}

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delayMs)

    return () => window.clearTimeout(id)
  }, [delayMs, value])

  return debounced
}

function RowIconButton({
  children,
  className,
  onClick,
  title
}: {
  children: ReactNode
  className?: string
  onClick: (event: MouseEvent<HTMLButtonElement>) => void
  title: string
}) {
  return (
    <Button
      aria-label={title}
      className={cn('text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground', className)}
      onClick={onClick}
      size="icon-xs"
      title={title}
      type="button"
      variant="ghost"
    >
      {children}
    </Button>
  )
}

function EmptyPanel({ action, description, title }: { action?: ReactNode; description: string; title?: string }) {
  return (
    <div className="grid min-h-48 place-items-center px-6 text-center">
      <div>
        {title && (
          <div className="text-[length:var(--conversation-text-font-size)] font-medium text-foreground">{title}</div>
        )}
        <div className="mt-1 text-[length:var(--conversation-caption-font-size)] leading-(--conversation-caption-line-height) text-(--ui-text-tertiary)">
          {description}
        </div>
        {action && <div className="mt-3 flex justify-center">{action}</div>}
      </div>
    </div>
  )
}

export function CommandCenterView({ initialSection, onClose, onDeleteSession, onOpenSession }: CommandCenterViewProps) {
  const { t } = useI18n()
  const cc = t.commandCenter
  const sessions = useStore($sessions)
  const pinnedSessionIds = useStore($pinnedSessionIds)

  const [section, setSection] = useRouteEnumParam('section', SECTIONS, initialSection ?? 'sessions')

  const [query, setQuery] = useState('')
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchGroups, setSearchGroups] = useState<CommandCenterSearchGroup[]>([])
  const [status, setStatus] = useState<StatusResponse | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [systemLoading, setSystemLoading] = useState(false)
  const [systemError, setSystemError] = useState('')
  const [systemAction, setSystemAction] = useState<ActionStatusResponse | null>(null)
  const [usagePeriod, setUsagePeriod] = useState<UsagePeriod>(30)
  const [usage, setUsage] = useState<AnalyticsResponse | null>(null)
  const [usageLoading, setUsageLoading] = useState(false)
  const [usageError, setUsageError] = useState('')
  const searchRequestRef = useRef(0)
  const usageRequestRef = useRef(0)

  const debouncedQuery = useDebouncedValue(query.trim(), 180)

  const sessionsById = useMemo(() => new Map(sessions.map(session => [session.id, session])), [sessions])

  const filteredSessions = useMemo(
    () =>
      [...sessions].sort((a, b) => {
        const left = a.last_active || a.started_at || 0
        const right = b.last_active || b.started_at || 0

        return right - left
      }),
    [sessions]
  )

  const searchProviders = useMemo<readonly CommandCenterSearchProvider[]>(
    () => [
      {
        id: 'navigation',
        label: cc.providerNavigate,
        search: async searchQuery => {
          const routeHits: RouteSearchHit[] = NAV_ROUTES.filter(entry =>
            matchesSearchQuery(searchQuery, cc.nav[entry.key].title, cc.nav[entry.key].detail, entry.route)
          ).map(entry => ({
            detail: cc.nav[entry.key].detail,
            kind: 'route',
            route: entry.route,
            title: cc.nav[entry.key].title
          }))

    return sorted.filter(session => {
      const haystack = `${sessionTitle(session)} ${session.id}`.toLowerCase()

          return [...routeHits, ...sectionHits]
        }
      },
      {
        id: 'sessions',
        label: cc.providerSessions,
        search: async searchQuery => {
          const response = await searchSessions(searchQuery)

          return response.results.map(result => {
            const { detail, title } = splitSessionSearchResult(result, sessionsById)

            return {
              detail,
              kind: 'session',
              sessionId: result.session_id,
              snippet: result.snippet || '',
              title
            } satisfies SessionSearchHit
          })
        }
      }
    ],
    [cc, sessionsById]
  )

  const refreshSystem = useCallback(async () => {
    setSystemLoading(true)
    setSystemError('')

    try {
      const [nextStatus, nextLogs] = await Promise.all([
        getStatus(),
        getLogs({
          file: 'agent',
          lines: 120
        })
      ])

      setStatus(nextStatus)
      setLogs(nextLogs.lines)
    } catch (error) {
      setSystemError(error instanceof Error ? error.message : String(error))
    } finally {
      setSystemLoading(false)
    }
  }, [])

  const refreshUsage = useCallback(async (days: UsagePeriod) => {
    const requestId = usageRequestRef.current + 1
    usageRequestRef.current = requestId
    setUsageLoading(true)
    setUsageError('')

    try {
      const response = await getUsageAnalytics(days)

      if (usageRequestRef.current === requestId) {
        setUsage(response)
      }
    } catch (error) {
      if (usageRequestRef.current === requestId) {
        setUsageError(error instanceof Error ? error.message : String(error))
      }
    } finally {
      if (usageRequestRef.current === requestId) {
        setUsageLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    if (!debouncedQuery) {
      setSearchGroups([])
      setSearchLoading(false)

      return
    }

    const requestId = searchRequestRef.current + 1
    searchRequestRef.current = requestId
    setSearchLoading(true)

    void Promise.all(
      searchProviders.map(async provider => ({
        id: provider.id,
        label: provider.label,
        results: await provider.search(debouncedQuery)
      }))
    )
      .then(groups => {
        if (searchRequestRef.current === requestId) {
          setSearchGroups(groups.filter(group => group.results.length > 0))
        }
      })
      .catch(() => {
        if (searchRequestRef.current === requestId) {
          setSearchGroups([])
        }
      })
      .finally(() => {
        if (searchRequestRef.current === requestId) {
          setSearchLoading(false)
        }
      })
  }, [debouncedQuery, searchProviders])

  useEffect(() => {
    if (section === 'system' && !status && !systemLoading) {
      void refreshSystem()
    }
  }, [refreshSystem, section, status, systemLoading])

  useEffect(() => {
    if (section === 'usage') {
      void refreshUsage(usagePeriod)
    }
  }, [refreshUsage, section, usagePeriod])

  useRefreshHotkey(() => {
    if (section === 'system') {
      void refreshSystem()
    } else if (section === 'usage') {
      void refreshUsage(usagePeriod)
    }
  })

  const showGlobalSearchResults = debouncedQuery.length > 0
  const hasGlobalSearchResults = searchGroups.length > 0
  const sessionListHasResults = filteredSessions.length > 0

  const runSystemAction = useCallback(
    async (kind: 'restart' | 'update') => {
      setSystemError('')

      try {
        const started = kind === 'restart' ? await restartGateway() : await updateHermes()
        let nextStatus: ActionStatusResponse | null = null

        for (let attempt = 0; attempt < 18; attempt += 1) {
          await new Promise(resolve => window.setTimeout(resolve, 1200))
          const polled = await getActionStatus(started.name, 180)
          nextStatus = polled
          setSystemAction(polled)
          upsertDesktopActionTask(polled)

          if (!polled.running) {
            break
          }
        }

        if (!nextStatus) {
          const pendingStatus = {
            exit_code: null,
            lines: [cc.actionStartedWaiting],
            name: started.name,
            pid: started.pid,
            running: true
          }

          setSystemAction(pendingStatus)
          upsertDesktopActionTask(pendingStatus)
        }
      } catch (error) {
        setSystemError(error instanceof Error ? error.message : String(error))
      } finally {
        void refreshSystem()
      }
    },
    [cc, refreshSystem]
  )

  return (
    <OverlayView closeLabel={cc.close} onClose={onClose}>
      <OverlaySplitLayout>
        <OverlaySidebar>
          {SECTIONS.map(value => (
            <OverlayNavItem
              active={section === value}
              icon={value === 'sessions' ? Pin : value === 'system' ? Activity : BarChart3}
              key={value}
              label={cc.sections[value]}
              onClick={() => setSection(value)}
            />
          ))}
        </OverlaySidebar>

        <OverlayMain>
          <header className="mb-4 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-[length:var(--conversation-text-font-size)] font-semibold text-foreground">
                {cc.sections[section]}
              </h2>
              <p className="mt-0.5 text-[length:var(--conversation-caption-font-size)] leading-(--conversation-caption-line-height) text-(--ui-text-tertiary)">
                {cc.sectionDescriptions[section]}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {section === 'sessions' && (
                <SearchField
                  containerClassName="max-w-[40vw]"
                  onChange={next => setQuery(next)}
                  placeholder={cc.searchPlaceholder}
                  value={query}
                />
              )}
              {section === 'usage' && (
                <SegmentedControl
                  onChange={id => setUsagePeriod(Number(id) as UsagePeriod)}
                  options={USAGE_PERIODS.map(value => ({ id: String(value), label: cc.days(value) }))}
                  value={String(usagePeriod)}
                />
              )}
            </div>
            {section === 'system' && (
              <OverlayActionButton disabled={systemLoading} onClick={() => void refreshSystem()}>
                <IconRefresh className={cn('mr-1.5 size-3.5', systemLoading && 'animate-spin')} />
                {systemLoading ? cc.refreshing : cc.refresh}
              </OverlayActionButton>
            )}
            {section === 'usage' && (
              <OverlayActionButton disabled={usageLoading} onClick={() => void refreshUsage(usagePeriod)}>
                <IconRefresh className={cn('mr-1.5 size-3.5', usageLoading && 'animate-spin')} />
                {usageLoading ? cc.refreshing : cc.refresh}
              </OverlayActionButton>
            )}
          </header>

          {showGlobalSearchResults ? (
            <div className="min-h-0 flex-1 overflow-y-auto pr-1">
              {!hasGlobalSearchResults ? (
                <OverlayCard className="px-3 py-4 text-sm text-muted-foreground">{cc.noResults}</OverlayCard>
              ) : (
                <div className="grid gap-3">
                  {searchGroups.map(group => (
                    <section className="grid gap-1.5" key={group.id}>
                      <h3 className="px-0.5 text-xs font-semibold tracking-[0.08em] text-muted-foreground/80 uppercase">
                        {group.label}
                      </h3>
                      {group.results.map(result => {
                        if (result.kind === 'session') {
                          const pinned = pinnedSessionIds.includes(result.sessionId)

                          return (
                            <OverlayCard className="p-2.5" key={`${group.id}:${result.sessionId}:${result.snippet}`}>
                              <button
                                className="w-full text-left"
                                onClick={() => handleSearchSelect(result)}
                                type="button"
                              >
                                <div className="truncate text-sm font-medium text-foreground">{result.title}</div>
                                <div className="mt-0.5 text-xs text-muted-foreground">
                                  {result.detail || result.sessionId}
                                </div>
                                {result.snippet && (
                                  <div className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground/85">
                                    {result.snippet}
                                  </div>
                                )}
                              </button>
                              <div className="mt-2 flex gap-1">
                                <OverlayIconButton
                                  onClick={event => {
                                    event.preventDefault()
                                    event.stopPropagation()
                                    pinned ? unpinSession(result.sessionId) : pinSession(result.sessionId)
                                  }}
                                  title={pinned ? cc.unpinSession : cc.pinSession}
                                >
                                  {pinned ? (
                                    <IconBookmarkFilled className="size-3.5" />
                                  ) : (
                                    <IconBookmark className="size-3.5" />
                                  )}
                                </OverlayIconButton>
                                <OverlayIconButton
                                  onClick={event => {
                                    event.preventDefault()
                                    event.stopPropagation()
                                    void exportSession(result.sessionId, { title: result.title })
                                  }}
                                  title={cc.exportSession}
                                >
                                  <IconDownload className="size-3.5" />
                                </OverlayIconButton>
                                <OverlayIconButton
                                  className="hover:text-destructive"
                                  onClick={event => {
                                    event.preventDefault()
                                    event.stopPropagation()
                                    void onDeleteSession(result.sessionId)
                                  }}
                                  title={cc.deleteSession}
                                >
                                  <IconTrash className="size-3.5" />
                                </OverlayIconButton>
                              </div>
                            </OverlayCard>
                          )
                        }

                        return (
                          <button
                            className={cn(
                              overlayCardClass,
                              'w-full px-3 py-2 text-left transition-colors hover:bg-[color-mix(in_srgb,var(--dt-muted)_48%,var(--dt-card))]'
                            )}
                            key={`${group.id}:${result.kind}:${result.title}`}
                            onClick={() => handleSearchSelect(result)}
                            type="button"
                          >
                            <div className="text-sm font-medium text-foreground">{result.title}</div>
                            {result.detail && (
                              <div className="mt-0.5 text-xs text-muted-foreground">{result.detail}</div>
                            )}
                          </button>
                        )
                      })}
                    </section>
                  ))}
                </div>
              )}
            </div>
          ) : section === 'sessions' ? (
            <div className="min-h-0 flex-1 overflow-y-auto">
              {!sessionListHasResults ? (
                <EmptyPanel description={debouncedQuery ? cc.noResults : cc.noSessions} />
              ) : (
                <div className="grid gap-1.5">
                  {filteredSessions.map(session => {
                    const pinned = pinnedSessionIds.includes(session.id)

                    return (
                      <OverlayCard className="flex items-center gap-2 px-2.5 py-2" key={session.id}>
                        <button
                          className="min-w-0 flex-1 text-left"
                          onClick={() => onOpenSession(session.id)}
                          type="button"
                        >
                          <div className="truncate text-sm font-medium text-foreground">{sessionTitle(session)}</div>
                          <div className="truncate text-xs text-muted-foreground">
                            {formatTimestamp(session.last_active || session.started_at)}
                          </div>
                        </button>
                        <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                          <RowIconButton
                            onClick={() => (pinned ? unpinSession(pinId) : pinSession(pinId))}
                            title={pinned ? cc.unpinSession : cc.pinSession}
                          >
                            {pinned ? (
                              <IconBookmarkFilled className="size-3.5" />
                            ) : (
                              <IconBookmark className="size-3.5" />
                            )}
                          </RowIconButton>
                          <RowIconButton
                            onClick={() => void exportSession(session.id, { session, title: sessionTitle(session) })}
                            title={cc.exportSession}
                          >
                            <IconDownload className="size-3.5" />
                          </RowIconButton>
                          <RowIconButton
                            className="hover:text-destructive"
                            onClick={() => void onDeleteSession(session.id)}
                            title={cc.deleteSession}
                          >
                            <IconTrash className="size-3.5" />
                          </RowIconButton>
                        </div>
                      </li>
                    )
                  })}
                </div>
              )}
            </div>
          ) : section === 'usage' ? (
            <UsagePanel
              error={usageError}
              loading={usageLoading}
              onPeriodChange={setUsagePeriod}
              onRefresh={() => void refreshUsage(usagePeriod)}
              period={usagePeriod}
              usage={usage}
            />
          ) : (
            <div className="grid min-h-0 flex-1 grid-rows-[auto_minmax(0,1fr)] gap-3">
              <OverlayCard className="p-3 text-sm">
                {status ? (
                  <div className="grid gap-2">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span
                            className={cn(
                              'size-2 rounded-full',
                              status.gateway_running ? 'bg-emerald-500' : 'bg-amber-500'
                            )}
                          />
                          <span className="text-[length:var(--conversation-text-font-size)] font-medium text-foreground">
                            {status.gateway_running ? cc.gatewayRunning : cc.gatewayStopped}
                          </span>
                        </div>
                        <div className="mt-1 text-[length:var(--conversation-caption-font-size)] text-(--ui-text-tertiary)">
                          {cc.hermesActiveSessions(status.version, status.active_sessions)}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5 whitespace-nowrap">
                        <Button onClick={() => void runSystemAction('restart')} size="xs" variant="text">
                          {cc.restartMessaging}
                        </Button>
                        <Button onClick={() => void runSystemAction('update')} size="xs" variant="textStrong">
                          {cc.updateHermes}
                        </Button>
                      </div>
                    </div>
                    {systemAction && (
                      <div className="text-xs text-muted-foreground">
                        {systemAction.name} ·{' '}
                        {systemAction.running ? cc.actionRunning : systemAction.exit_code === 0 ? cc.actionDone : cc.actionFailed}
                      </div>
                    )}
                  </div>
                ) : (
                  <PageLoader className="min-h-32" label={cc.loadingStatus} />
                )}
              </OverlayCard>

              <OverlayCard className="min-h-0 overflow-hidden p-2">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-[0.625rem] font-medium uppercase tracking-[0.08em] text-(--ui-text-tertiary)">
                    {cc.recentLogs}
                  </span>
                  {systemError && (
                    <span className="inline-flex items-center gap-1 text-xs text-destructive">
                      <AlertCircle className="size-3.5" />
                      {systemError}
                    </span>
                  )}
                </div>
                <pre className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap wrap-break-word rounded-lg border border-(--ui-stroke-tertiary) bg-(--ui-bg-quinary) p-3 font-mono text-[0.65rem] leading-relaxed text-(--ui-text-tertiary)">
                  {logs.length ? logs.join('\n') : cc.noLogs}
                </pre>
              </OverlayCard>
            </div>
          )}
        </OverlayMain>
      </OverlaySplitLayout>
    </OverlayView>
  )
}

function formatTokens(value: null | number | undefined): string {
  const num = Number(value || 0)

  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1)}M`
  }

  if (num >= 1_000) {
    return `${(num / 1_000).toFixed(1)}K`
  }

  return num.toLocaleString()
}

function formatCost(value: null | number | undefined): string {
  const num = Number(value || 0)

  if (num === 0) {
    return '$0.00'
  }

  if (num < 0.01) {
    return '<$0.01'
  }

  return `$${num.toFixed(2)}`
}

function formatInteger(value: null | number | undefined): string {
  return Number(value ?? 0).toLocaleString()
}

interface UsagePanelProps {
  error: string
  loading: boolean
  onPeriodChange: (period: UsagePeriod) => void
  onRefresh: () => void
  period: UsagePeriod
  usage: AnalyticsResponse | null
}

function UsagePanel({ error, loading, onRefresh, period, usage }: UsagePanelProps) {
  const { t } = useI18n()
  const cc = t.commandCenter
  const daily = useMemo(() => usage?.daily ?? [], [usage])
  const totals = usage?.totals
  const byModel = usage?.by_model ?? []
  const topSkills = usage?.skills?.top_skills ?? []

  const maxTokens = useMemo(() => {
    if (!daily.length) {
      return 1
    }

    return daily.reduce((acc, entry) => Math.max(acc, (entry.input_tokens || 0) + (entry.output_tokens || 0)), 1)
  }, [daily])

  if (!totals) {
    return (
      <div className="min-h-0 flex-1">
        {loading ? (
          <PageLoader className="min-h-48" label={cc.loadingUsage} />
        ) : (
          <EmptyPanel
            action={
              <Button onClick={onRefresh} size="xs" variant="text">
                {cc.retry}
              </Button>
            }
            description={cc.noUsage(period)}
          />
        )}
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto pb-2">
      {error && (
        <span className="inline-flex items-center gap-1 text-[length:var(--conversation-caption-font-size)] text-destructive">
          <AlertCircle className="size-3.5" />
          {error}
        </span>
      )}

      <div className="grid grid-cols-2 gap-x-4 gap-y-4 border-b border-(--ui-stroke-tertiary) pb-5 sm:grid-cols-4">
        <UsageStat label={cc.statSessions} value={formatInteger(totals.total_sessions)} />
        <UsageStat label={cc.statApiCalls} value={formatInteger(totals.total_api_calls)} />
        <UsageStat
          label={cc.statTokens}
          value={`${formatTokens(totals.total_input)} / ${formatTokens(totals.total_output)}`}
        />
        <UsageStat
          hint={totals.total_actual_cost > 0 ? cc.actualCost(formatCost(totals.total_actual_cost)) : undefined}
          label={cc.statCost}
          value={formatCost(totals.total_estimated_cost)}
        />
      </div>

      <section>
        <div className="mb-2 flex items-baseline justify-between">
          <span className="text-[0.625rem] font-medium uppercase tracking-[0.08em] text-(--ui-text-tertiary)">
            {cc.dailyTokens}
          </span>
          <span className="flex items-center gap-3 text-[0.65rem] text-(--ui-text-tertiary)">
            <span className="inline-flex items-center gap-1">
              <span className="size-2 rounded-[1px] bg-[color:var(--dt-primary)]/60" /> {cc.input}
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="size-2 rounded-[1px] bg-emerald-500/70" /> {cc.output}
            </span>
          </span>
        </div>
        {daily.length === 0 ? (
          <div className="grid h-24 place-items-center text-[length:var(--conversation-caption-font-size)] text-(--ui-text-tertiary)">
            {cc.noDailyActivity}
          </div>
        ) : (
          <>
            <div className="flex h-24 items-end gap-px">
              {daily.map(entry => {
                const inputH = Math.round(((entry.input_tokens || 0) / maxTokens) * 96)
                const outputH = Math.round(((entry.output_tokens || 0) / maxTokens) * 96)

                return (
                  <div
                    className="group relative flex h-24 min-w-0 flex-1 flex-col justify-end"
                    key={entry.day}
                    title={`${entry.day} · in ${formatTokens(entry.input_tokens)} · out ${formatTokens(entry.output_tokens)}`}
                  >
                    <div
                      className="w-full rounded-t-[1px] bg-[color:var(--dt-primary)]/50"
                      style={{ height: Math.max(inputH, entry.input_tokens > 0 ? 1 : 0) }}
                    />
                    <div
                      className="w-full bg-emerald-500/60"
                      style={{ height: Math.max(outputH, entry.output_tokens > 0 ? 1 : 0) }}
                    />
                  </div>
                )
              })}
            </div>
            <div className="mt-1 flex justify-between text-[0.6rem] text-(--ui-text-tertiary)">
              <span>{daily[0]?.day}</span>
              <span>{daily[daily.length - 1]?.day}</span>
            </div>
          </>
        )}
      </OverlayCard>

      <div className="grid min-h-0 gap-x-8 gap-y-5 border-t border-(--ui-stroke-tertiary) pt-5 sm:grid-cols-2">
        <UsageList
          emptyLabel={cc.noModelUsage}
          rows={byModel.slice(0, 6).map(entry => ({
            key: entry.model,
            label: entry.model,
            value: `${formatTokens((entry.input_tokens || 0) + (entry.output_tokens || 0))} · ${formatCost(entry.estimated_cost)}`
          }))}
          title={cc.topModels}
        />
        <UsageList
          emptyLabel={cc.noSkillActivity}
          rows={topSkills.slice(0, 6).map(entry => ({
            key: entry.skill,
            label: entry.skill,
            value: cc.actions(entry.total_count.toLocaleString())
          }))}
          title={cc.topSkills}
        />
      </div>
    </div>
  )
}

function UsageStat({ hint, label, value }: { hint?: string; label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[0.65rem] font-medium uppercase tracking-[0.12em] text-muted-foreground">{label}</div>
      <div className="mt-0.5 truncate text-sm font-semibold tracking-tight text-foreground">{value}</div>
      {hint && <div className="mt-0.5 truncate text-[0.62rem] text-muted-foreground/80">{hint}</div>}
    </div>
  )
}
