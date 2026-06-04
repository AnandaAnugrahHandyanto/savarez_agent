import { useEffect, useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { getKanbanBoard, type KanbanBoardResponse, type KanbanBoardSummary, listKanbanBoards } from '@/hermes'
import { Clipboard, Loader2 } from '@/lib/icons'
import { notifyError } from '@/store/notifications'

import { includesQuery } from './helpers'
import { EmptyState, LoadingState, Pill, SectionHeading, SettingsContent } from './primitives'
import type { SearchProps } from './types'

interface KanbanSettingsProps extends SearchProps {
  gatewayId?: string
}

function taskTitle(task: unknown): string {
  if (!task || typeof task !== 'object') {
    return 'Untitled task'
  }

  const value = (task as { title?: unknown; id?: unknown }).title ?? (task as { id?: unknown }).id

  return typeof value === 'string' && value.trim() ? value : 'Untitled task'
}

function taskMeta(task: unknown): string {
  if (!task || typeof task !== 'object') {
    return ''
  }

  const t = task as { assignee?: unknown; priority?: unknown; status?: unknown }

  return [t.status, t.assignee ? `@${String(t.assignee)}` : null, t.priority !== undefined ? `p${String(t.priority)}` : null]
    .filter(Boolean)
    .join(' · ')
}

export function KanbanSettings({ gatewayId, query }: KanbanSettingsProps) {
  const [boards, setBoards] = useState<KanbanBoardSummary[] | null>(null)
  const [selectedBoard, setSelectedBoard] = useState('')
  const [board, setBoard] = useState<KanbanBoardResponse | null>(null)
  const [loadingBoard, setLoadingBoard] = useState(false)

  useEffect(() => {
    let cancelled = false

    setBoards(null)
    setBoard(null)
    setSelectedBoard('')

    listKanbanBoards(gatewayId)
      .then(result => {
        if (cancelled) {
          return
        }

        setBoards(result.boards)
        setSelectedBoard(result.current || result.boards.find(b => b.is_current)?.slug || result.boards[0]?.slug || '')
      })
      .catch(err => notifyError(err, 'Kanban boards failed to load'))

    return () => void (cancelled = true)
  }, [gatewayId])

  useEffect(() => {
    if (!selectedBoard) {
      setBoard(null)

      return
    }

    let cancelled = false
    setLoadingBoard(true)

    getKanbanBoard({ board: selectedBoard, gatewayId })
      .then(result => {
        if (!cancelled) {
          setBoard(result)
        }
      })
      .catch(err => notifyError(err, 'Kanban board failed to load'))
      .finally(() => {
        if (!cancelled) {
          setLoadingBoard(false)
        }
      })

    return () => void (cancelled = true)
  }, [gatewayId, selectedBoard])

  const visibleBoards = useMemo(() => {
    const q = query.trim().toLowerCase()

    if (!boards || !q) {
      return boards ?? []
    }

    return boards.filter(b => includesQuery(b.slug, q) || includesQuery(b.name, q))
  }, [boards, query])

  if (!boards) {
    return <LoadingState label="Loading Kanban boards..." />
  }

  return (
    <SettingsContent>
      <div className="mb-4 flex items-center justify-between gap-3">
        <SectionHeading icon={Clipboard} meta={`${boards.length} board${boards.length === 1 ? '' : 's'}`} title="Kanban" />
        <Button disabled={loadingBoard} onClick={() => selectedBoard && getKanbanBoard({ board: selectedBoard, gatewayId }).then(setBoard).catch(err => notifyError(err, 'Kanban refresh failed'))} size="sm" variant="outline">
          {loadingBoard ? <Loader2 className="size-3.5 animate-spin" /> : null}
          Refresh
        </Button>
      </div>

      <div className="grid min-h-0 gap-4 lg:grid-cols-[17rem_minmax(0,1fr)]">
        <div className="grid content-start gap-1 rounded-xl bg-background/60 p-2">
          {visibleBoards.length === 0 ? (
            <EmptyState description="No boards matched this gateway/search." title="No Kanban boards" />
          ) : (
            visibleBoards.map(b => (
              <button
                className={`rounded-md px-2 py-2 text-left transition-colors hover:bg-(--chrome-action-hover) ${selectedBoard === b.slug ? 'bg-accent/45 text-foreground' : 'text-muted-foreground'}`}
                key={b.slug}
                onClick={() => setSelectedBoard(b.slug)}
                type="button"
              >
                <div className="truncate text-sm font-medium">{b.name || b.slug}</div>
                <div className="mt-1 flex items-center gap-1.5">
                  <Pill>{b.slug}</Pill>
                  {b.is_current && <Pill tone="primary">current</Pill>}
                  {typeof b.total === 'number' && <Pill>{b.total} tasks</Pill>}
                </div>
              </button>
            ))
          )}
        </div>

        <div className="min-h-0 overflow-x-auto rounded-xl bg-background/60 p-3">
          {loadingBoard ? (
            <LoadingState label="Loading board..." />
          ) : !board ? (
            <EmptyState description="Pick a board on the left." title="No board selected" />
          ) : (
            <div className="grid min-w-[52rem] gap-3" style={{ gridTemplateColumns: `repeat(${Math.max(1, board.columns.length)}, minmax(12rem, 1fr))` }}>
              {board.columns.map(column => (
                <div className="rounded-lg bg-muted/20 p-2" key={column.name}>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{column.name}</span>
                    <Pill>{column.tasks.length}</Pill>
                  </div>
                  <div className="grid gap-2">
                    {column.tasks.slice(0, 20).map((task, index) => (
                      <div className="rounded-md bg-background/70 p-2 text-xs" key={`${column.name}-${index}`}>
                        <div className="font-medium text-foreground">{taskTitle(task)}</div>
                        {taskMeta(task) && <div className="mt-1 text-[0.68rem] text-muted-foreground">{taskMeta(task)}</div>}
                      </div>
                    ))}
                    {column.tasks.length > 20 && <div className="text-[0.68rem] text-muted-foreground">+{column.tasks.length - 20} more</div>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </SettingsContent>
  )
}
