import { useStore } from '@nanostores/react'
import type { ReactNode } from 'react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { Loader } from '@/components/ui/loader'
import { Tip } from '@/components/ui/tooltip'
import { getSessionChanges } from '@/hermes'
import type { SessionChangesResponse, SessionTurnChange, SessionTurnChangeFile } from '@/hermes'
import { useI18n } from '@/i18n'
import { normalizeOrLocalPreviewTarget } from '@/lib/local-preview'
import { cn } from '@/lib/utils'
import { notifyError } from '@/store/notifications'
import { type PreviewTarget, setSessionPreviewTarget } from '@/store/preview'
import { $currentCwd } from '@/store/session'

interface ChangesPanelProps {
  profile?: string | null
  sessionId: string | null
}

const STATUS_META: Record<SessionTurnChangeFile['status'], { label: string; className: string; icon: string }> = {
  added: { label: 'A', className: 'text-emerald-300 bg-emerald-400/10 border-emerald-400/20', icon: 'add' },
  conflict: { label: '!', className: 'text-red-300 bg-red-400/10 border-red-400/20', icon: 'warning' },
  copied: { label: 'C', className: 'text-sky-300 bg-sky-400/10 border-sky-400/20', icon: 'copy' },
  deleted: { label: 'D', className: 'text-red-300 bg-red-400/10 border-red-400/20', icon: 'trash' },
  modified: { label: 'M', className: 'text-amber-200 bg-amber-400/10 border-amber-400/20', icon: 'edit' },
  renamed: { label: 'R', className: 'text-blue-200 bg-blue-400/10 border-blue-400/20', icon: 'arrow-swap' },
  untracked: { label: 'U', className: 'text-violet-200 bg-violet-400/10 border-violet-400/20', icon: 'untracked' }
}

function shortName(path: string) {
  return path.split(/[\\/]/).filter(Boolean).pop() || path
}

function parentName(path: string) {
  const parts = path.split(/[\\/]/).filter(Boolean)

  return parts.length > 1 ? parts.slice(0, -1).join('/') : ''
}

function fileKey(turn: SessionTurnChange, file: SessionTurnChangeFile) {
  return `${turn.id}:${file.path}:${file.messageId ?? ''}`
}

function newestTurn(turns: SessionTurnChange[]) {
  return turns.length ? turns[turns.length - 1] : null
}

function diffPreviewTarget(turn: SessionTurnChange, file: SessionTurnChangeFile): PreviewTarget {
  return {
    binary: file.binary,
    diffLines: file.diff,
    kind: 'file',
    label: `Δ ${shortName(file.path)}`,
    language: 'diff',
    path: file.path,
    previewKind: 'diff',
    source: file.path,
    url: `hermes-diff://${turn.id}/${encodeURIComponent(file.path)}${file.messageId ? `?message=${file.messageId}` : ''}`
  }
}

export function ChangesPanel({ profile, sessionId }: ChangesPanelProps) {
  const { t } = useI18n()
  const r = t.rightSidebar
  const currentCwd = useStore($currentCwd).trim()
  const [changes, setChanges] = useState<SessionChangesResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [expandedTurnId, setExpandedTurnId] = useState<number | null>(null)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const loadingRef = useRef(false)

  const selected = useMemo(() => {
    if (!changes || !selectedKey) {return null}

    for (const turn of changes.turns) {
      const file = turn.files.find(candidate => fileKey(turn, candidate) === selectedKey)

      if (file) {return { turn, file }}
    }

    return null
  }, [changes, selectedKey])

  const refresh = useCallback(
    async ({ quiet = false }: { quiet?: boolean } = {}) => {
      if (!sessionId) {
        setChanges(null)
        setExpandedTurnId(null)
        setSelectedKey(null)

        return
      }

      if (loadingRef.current) {return}
      loadingRef.current = true

      if (!quiet) {setLoading(true)}

      try {
        const next = await getSessionChanges(sessionId, profile)
        setChanges(next)
        setExpandedTurnId(current => {
          if (current && next.turns.some(turn => turn.id === current)) {return current}

          return newestTurn(next.turns)?.id ?? null
        })
        setSelectedKey(current => {
          if (current && next.turns.some(turn => turn.files.some(file => fileKey(turn, file) === current))) {return current}
          const turn = newestTurn(next.turns)
          const firstFile = turn?.files[0]

          return turn && firstFile ? fileKey(turn, firstFile) : null
        })
      } catch (error) {
        if (!quiet) {notifyError(error, r.changesLoadFailed)}
      } finally {
        loadingRef.current = false

        if (!quiet) {setLoading(false)}
      }
    },
    [profile, r.changesLoadFailed, sessionId]
  )

  useEffect(() => {
    void refresh()

    if (!sessionId) {return undefined}

    const onFocus = () => void refresh({ quiet: true })
    const timer = window.setInterval(() => void refresh({ quiet: true }), 2500)
    window.addEventListener('focus', onFocus)

    return () => {
      window.clearInterval(timer)
      window.removeEventListener('focus', onFocus)
    }
  }, [refresh, sessionId])

  const openDiffTab = useCallback(
    (turn: SessionTurnChange, file: SessionTurnChangeFile) => {
      const key = fileKey(turn, file)
      setSelectedKey(key)
      setExpandedTurnId(turn.id)
      setSessionPreviewTarget(sessionId, diffPreviewTarget(turn, file), 'manual', file.path)
    },
    [sessionId]
  )

  const openFullFileTab = useCallback(
    async (turn: SessionTurnChange, file: SessionTurnChangeFile) => {
      const key = fileKey(turn, file)
      setSelectedKey(key)
      setExpandedTurnId(turn.id)

      try {
        const preview = await normalizeOrLocalPreviewTarget(file.path, currentCwd || undefined)

        if (!preview) {throw new Error(`Could not preview ${file.path}`)}
        setSessionPreviewTarget(sessionId, preview, 'manual', file.path)
      } catch (error) {
        notifyError(error, 'Could not open full file')
      }
    },
    [currentCwd, sessionId]
  )

  const totals = changes?.totals

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <RightSidebarSectionHeader>
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Codicon className="text-(--ui-text-tertiary)" name="history" size="0.8125rem" />
          <span className="truncate text-[0.67rem] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            {r.sessionChanges}
          </span>
          {totals && totals.turns > 0 && (
            <span className="rounded-full border border-border/70 px-1.5 py-0.5 text-[0.56rem] font-medium text-muted-foreground">
              {totals.turns}
            </span>
          )}
        </div>
        <Button
          aria-label={r.refreshChanges}
          className="text-sidebar-foreground/70 hover:bg-sidebar-accent! hover:text-sidebar-accent-foreground! focus-visible:ring-sidebar-ring"
          disabled={!sessionId || loading}
          onClick={() => void refresh()}
          size="icon-xs"
          variant="ghost"
        >
          <Codicon name="refresh" size="0.8125rem" spinning={loading} />
        </Button>
      </RightSidebarSectionHeader>

      {!sessionId ? (
        <ChangesEmpty body={r.changesNoSessionBody} title={r.changesNoSessionTitle} />
      ) : loading && !changes ? (
        <div aria-label={r.loadingChanges} className="grid min-h-0 flex-1 place-items-center px-3" role="status">
          <Loader aria-hidden="true" className="size-8 text-(--ui-text-tertiary)" pathSteps={180} role="presentation" strokeScale={0.68} type="spiral-search" />
        </div>
      ) : !changes || changes.turns.length === 0 ? (
        <ChangesEmpty body={r.changesCleanBody} title={r.changesCleanTitle} />
      ) : (
        <div className="flex min-h-0 flex-1 flex-col border-t border-border/40">
          <div className="grid grid-cols-4 gap-1 border-b border-border/40 p-2">
            <Metric label={r.changedTurns} value={String(totals?.turns ?? 0)} />
            <Metric label={r.changedFiles} value={String(totals?.files ?? 0)} />
            <Metric className="text-emerald-200" label={r.addedLines} value={`+${totals?.added ?? 0}`} />
            <Metric className="text-red-200" label={r.removedLines} value={`-${totals?.removed ?? 0}`} />
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {changes.turns.map((turn, index) => {
              const expanded = expandedTurnId === turn.id

              return (
                <section className="border-b border-border/30 last:border-b-0" key={turn.id}>
                  <button
                    className="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 px-2.5 py-2 text-left transition hover:bg-sidebar-accent/45"
                    onClick={() => setExpandedTurnId(expanded ? null : turn.id)}
                    type="button"
                  >
                    <Codicon className="text-muted-foreground" name={expanded ? 'chevron-down' : 'chevron-right'} size="0.72rem" />
                    <span className="min-w-0">
                      <span className="block truncate text-[0.7rem] font-medium text-foreground/90">
                        {r.turnLabel(index + 1)} · {turn.title}
                      </span>
                      <span className="block truncate text-[0.58rem] text-muted-foreground/65">
                        {turn.totals.files} {r.filesChangedInline} · +{turn.totals.added} / -{turn.totals.removed}
                      </span>
                    </span>
                    <span className="rounded-full border border-border/60 px-1.5 py-0.5 text-[0.55rem] text-muted-foreground">{turn.files.length}</span>
                  </button>

                  {expanded && (
                    <div className="pb-1">
                      {turn.files.map(file => {
                        const key = fileKey(turn, file)
                        const selectedRow = selectedKey === key

                        return (
                          <div
                            className={cn(
                              'flex items-center border-l-2 transition hover:bg-sidebar-accent/45',
                              selectedRow ? 'border-l-primary bg-sidebar-accent/55' : 'border-l-transparent'
                            )}
                            key={key}
                          >
                            <button
                              className="grid min-w-0 flex-1 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 px-4 py-1.5 text-left"
                              onClick={() => openDiffTab(turn, file)}
                              title="Open diff tab"
                              type="button"
                            >
                              <span className={cn('grid size-5 place-items-center rounded border text-[0.56rem] font-semibold', STATUS_META[file.status].className)}>
                                {STATUS_META[file.status].label}
                              </span>
                              <span className="min-w-0">
                                <span className="block truncate text-[0.72rem] text-foreground/90">{shortName(file.path)}</span>
                                <span className="block truncate text-[0.59rem] text-muted-foreground/65">{parentName(file.path) || file.toolName || file.status}</span>
                              </span>
                              <span className="flex items-center gap-1 font-mono text-[0.58rem]">
                                {file.added > 0 && <span className="text-emerald-300">+{file.added}</span>}
                                {file.removed > 0 && <span className="text-red-300">-{file.removed}</span>}
                                {file.added === 0 && file.removed === 0 && <span className="text-muted-foreground/45">—</span>}
                              </span>
                            </button>
                            <Tip label={file.status === 'deleted' ? 'File was deleted' : 'Open full file'}>
                              <Button
                                aria-label={`Open full file ${file.path}`}
                                className="mr-1 shrink-0 text-sidebar-foreground/70 hover:bg-sidebar-accent! hover:text-sidebar-accent-foreground! focus-visible:ring-sidebar-ring"
                                disabled={file.status === 'deleted'}
                                onClick={() => void openFullFileTab(turn, file)}
                                size="icon-xs"
                                variant="ghost"
                              >
                                <Codicon name="file" size="0.78rem" />
                              </Button>
                            </Tip>
                          </div>
                        )
                      })}
                    </div>
                  )}
                </section>
              )
            })}
          </div>

          <div className="border-t border-border/40 px-2.5 py-1.5 text-[0.58rem] text-muted-foreground/65">
            {selected ? (
              <span className="block truncate">Diff tab: {selected.file.path}</span>
            ) : (
              'Click a file to open its diff as a content tab. Use the file icon for the full file.'
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function Metric({ className, label, value }: { className?: string; label: string; value: string }) {
  return (
    <div className="rounded-md border border-border/60 bg-muted/15 px-1.5 py-1.5">
      <div className={cn('font-mono text-[0.74rem] font-semibold text-foreground/90', className)}>{value}</div>
      <div className="mt-0.5 truncate text-[0.49rem] uppercase tracking-[0.05em] text-muted-foreground/65">{label}</div>
    </div>
  )
}

function ChangesEmpty({ body, title }: { body: string; title: string }) {
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-1 px-4 text-center">
      <div className="text-[0.7rem] font-semibold uppercase tracking-[0.07em] text-muted-foreground/75">{title}</div>
      <div className="text-[0.68rem] leading-relaxed text-muted-foreground/65">{body}</div>
    </div>
  )
}

function RightSidebarSectionHeader({ children }: { children: ReactNode }) {
  return <div className="flex h-7 shrink-0 items-center px-2.5">{children}</div>
}
