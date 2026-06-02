import { useCallback, useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { deleteSession, listSessions, setSessionArchived } from '@/hermes'
import { sessionTitle } from '@/lib/chat-runtime'
import { triggerHaptic } from '@/lib/haptics'
import { Archive, ArchiveOff, Loader2, Trash2 } from '@/lib/icons'
import { useT } from '@/locales'
import { notify, notifyError } from '@/store/notifications'
import { setSessions } from '@/store/session'
import type { SessionInfo } from '@/types/hermes'

import { EmptyState, ListRow, LoadingState, SectionHeading, SettingsContent } from './primitives'
import type { SearchProps } from './types'

const ARCHIVED_FETCH_LIMIT = 200

function workspaceLabel(cwd: null | string | undefined): string {
  const path = cwd?.trim()

  if (!path) {
    return ''
  }

  return (
    path
      .replace(/[/\\]+$/, '')
      .split(/[/\\]/)
      .filter(Boolean)
      .pop() ?? path
  )
}

export function SessionsSettings({ query }: SearchProps) {
  const t = useT()
  const [sessions, setLocalSessions] = useState<SessionInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)

    try {
      const result = await listSessions(ARCHIVED_FETCH_LIMIT, 0, 'only')
      setLocalSessions(result.sessions)
    } catch (err) {
      notifyError(err, t('sessions.loadFailed'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const unarchive = useCallback(async (session: SessionInfo) => {
    setBusyId(session.id)

    try {
      await setSessionArchived(session.id, false)
      setLocalSessions(prev => prev.filter(s => s.id !== session.id))
      // Surface it again in the sidebar without waiting for a full refresh.
      setSessions(prev => [{ ...session, archived: false }, ...prev.filter(s => s.id !== session.id)])
      triggerHaptic('selection')
      notify({ durationMs: 2_000, kind: 'success', message: t('sessions.restored') })
    } catch (err) {
      notifyError(err, t('sessions.unarchiveFailed'))
    } finally {
      setBusyId(null)
    }
  }, [])

  const remove = useCallback(async (session: SessionInfo) => {
    if (!window.confirm(t('sessions.deleteConfirm', { title: sessionTitle(session) }))) {
      return
    }

    setBusyId(session.id)

    try {
      await deleteSession(session.id)
      setLocalSessions(prev => prev.filter(s => s.id !== session.id))
      triggerHaptic('warning')
    } catch (err) {
      notifyError(err, t('sessions.deleteFailed'))
    } finally {
      setBusyId(null)
    }
  }, [])

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()

    if (!needle) {
      return sessions
    }

    return sessions.filter(session =>
      [sessionTitle(session), session.preview ?? '', session.cwd ?? ''].join(' ').toLowerCase().includes(needle)
    )
  }, [query, sessions])

  if (loading) {
    return <LoadingState label={t('sessions.loading')} />
  }

  return (
    <SettingsContent>
      <SectionHeading
        icon={Archive}
        meta={sessions.length ? String(sessions.length) : undefined}
        title={t('sessions.title')}
      />
      <p className="mb-2 text-[length:var(--conversation-caption-font-size)] text-(--ui-text-tertiary)">
        {t('sessions.description')}
      </p>

      {filtered.length === 0 ? (
        <EmptyState
          description={query.trim() ? t('sessions.noSearchMatch') : t('sessions.archiveHint')}
          title={t('sessions.nothingArchived')}
        />
      ) : (
        <div className="divide-y divide-border/30">
          {filtered.map(session => {
            const label = workspaceLabel(session.cwd)
            const busy = busyId === session.id

            return (
              <ListRow
                action={
                  <div className="flex items-center gap-1.5">
                    <Button
                      disabled={busy}
                      onClick={() => void unarchive(session)}
                      size="sm"
                      type="button"
                      variant="outline"
                    >
                      {busy ? <Loader2 className="size-3.5 animate-spin" /> : <ArchiveOff className="size-3.5" />}
                      <span>{t('sessions.unarchive')}</span>
                    </Button>
                    <Button
                      aria-label={t('sessions.deletePermanently')}
                      className="text-muted-foreground hover:text-destructive"
                      disabled={busy}
                      onClick={() => void remove(session)}
                      size="icon"
                      title={t('sessions.deletePermanently')}
                      type="button"
                      variant="ghost"
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                }
                description={session.preview || undefined}
                hint={label ? `${label} · ${t('sessions.messageCount', { n: session.message_count })}` : t('sessions.messageCount', { n: session.message_count })}
                key={session.id}
                title={sessionTitle(session)}
              />
            )
          })}
        </div>
      )}
    </SettingsContent>
  )
}
