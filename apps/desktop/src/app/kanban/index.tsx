import { useCallback, useEffect, useMemo, useState } from 'react'
import type * as React from 'react'

import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { getKanbanBoards, getKanbanTasks } from '@/hermes'
import { cn } from '@/lib/utils'
import type { KanbanBoard, KanbanTask, KanbanTasksResponse } from '@/types/hermes'

const COLUMNS = [
  { id: 'todo', label: 'Todo' },
  { id: 'running', label: 'Running' },
  { id: 'review', label: 'Review' },
  { id: 'done', label: 'Done' }
] as const

type KanbanColumnId = (typeof COLUMNS)[number]['id']

function taskColumn(status: string): KanbanColumnId | 'hidden' {
  if (status === 'done') {
    return 'done'
  }
  if (status === 'running') {
    return 'running'
  }
  if (status === 'review') {
    return 'review'
  }
  if (status === 'archived') {
    return 'hidden'
  }
  return 'todo'
}

function latestLog(task: KanbanTask): string {
  const event = task.recent_events?.[0]
  if (event?.message) {
    return event.message
  }
  if (event?.kind) {
    return event.kind
  }
  if (task.last_failure_error) {
    return task.last_failure_error
  }
  if (task.result) {
    return task.result
  }
  return ''
}

function taskProgress(task: KanbanTask): number | null {
  if (typeof task.progress === 'number') {
    return Math.max(0, Math.min(100, Math.round(task.progress)))
  }
  if (task.status === 'running') {
    return 0
  }
  return null
}

function relativeTaskTime(task: KanbanTask): string {
  const stamp = task.completed_at ?? task.started_at ?? task.updated_at ?? task.created_at
  if (!stamp) {
    return 'just now'
  }

  const elapsed = Math.max(0, Math.floor(Date.now() / 1000) - stamp)
  if (elapsed < 60) {
    return `${elapsed}s ago`
  }
  if (elapsed < 3600) {
    return `${Math.floor(elapsed / 60)}m ago`
  }
  if (elapsed < 86_400) {
    return `${Math.floor(elapsed / 3600)}h ago`
  }
  return `${Math.floor(elapsed / 86_400)}d ago`
}

export function KanbanBoardIcon(props: React.ComponentProps<'svg'>) {
  return (
    <svg aria-hidden="true" fill="none" viewBox="0 0 16 16" {...props}>
      <path d="M2.75 3.25h10.5M3.25 5.75h2.5v6.5h-2.5zM6.75 5.75h2.5v4.5h-2.5zM10.25 5.75h2.5v3h-2.5z" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M3.5 3.25h1.25M7.25 3.25H8.5M11 3.25h1.25" stroke="currentColor" strokeLinecap="round" />
      <path d="M7.25 11.75h1.5" opacity="0.62" stroke="currentColor" strokeLinecap="round" />
    </svg>
  )
}

export function KanbanView() {
  const [boards, setBoards] = useState<KanbanBoard[]>([])
  const [selectedBoardSlug, setSelectedBoardSlug] = useState('')
  const [payload, setPayload] = useState<KanbanTasksResponse | null>(null)
  const [filter, setFilter] = useState('')
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null)
  const [compact, setCompact] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const applyTaskPayload = useCallback((result: KanbanTasksResponse) => {
    setPayload(result)
    setSelectedTaskId(current => current && result.tasks.some(task => task.id === current) ? current : result.tasks[0]?.id || null)
  }, [])

  useEffect(() => {
    let alive = true

    setLoading(true)
    getKanbanBoards()
      .then(result => {
        if (!alive) {
          return
        }
        setBoards(result.boards)
        const initialSlug = result.boards[0]?.slug || 'default'
        setSelectedBoardSlug(current => current || initialSlug)
        return getKanbanTasks(initialSlug).then(result => {
          if (alive) {
            applyTaskPayload(result)
          }
        })
      })
      .catch(err => {
        if (alive) {
          setError(err instanceof Error ? err.message : 'Failed to load kanban boards')
        }
      })
      .finally(() => {
        if (alive) {
          setLoading(false)
        }
      })

    return () => {
      alive = false
    }
  }, [applyTaskPayload])

  const refreshTasks = useCallback(() => {
    if (!selectedBoardSlug) {
      return Promise.resolve()
    }

    setLoading(true)
    setError(null)

    return getKanbanTasks(selectedBoardSlug)
      .then(applyTaskPayload)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load kanban tasks'))
      .finally(() => setLoading(false))
  }, [applyTaskPayload, selectedBoardSlug])

  useEffect(() => {
    void refreshTasks()
  }, [refreshTasks])

  const selectedBoard = useMemo(
    () => boards.find(board => board.slug === selectedBoardSlug) ?? boards[0],
    [boards, selectedBoardSlug]
  )

  const visibleTasks = useMemo(() => {
    const needle = filter.trim().toLowerCase()
    const tasks = payload?.tasks ?? []

    if (!needle) {
      return tasks
    }

    return tasks.filter(task => `${task.id} ${task.title} ${task.status} ${latestLog(task)}`.toLowerCase().includes(needle))
  }, [filter, payload?.tasks])

  const tasksByColumn = useMemo(() => {
    const map: Record<KanbanColumnId, KanbanTask[]> = { done: [], review: [], running: [], todo: [] }

    for (const task of visibleTasks) {
      const column = taskColumn(task.status)
      if (column !== 'hidden') {
        map[column].push(task)
      }
    }

    return map
  }, [visibleTasks])

  const selectedTask = useMemo(
    () => (payload?.tasks ?? []).find(task => task.id === selectedTaskId) ?? null,
    [payload?.tasks, selectedTaskId]
  )
  const counts = payload?.counts ?? selectedBoard?.counts ?? { blocked: 0, done: 0, review: 0, running: 0, todo: 0 }

  return (
    <div className="relative flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-(--ui-chat-surface-background) pt-(--titlebar-height) text-foreground">
      <div className="flex min-h-0 flex-1 flex-col gap-3 px-4 pb-3 pt-3">
        <header className="flex shrink-0 items-start justify-between gap-3 border-b border-(--ui-stroke-secondary) pb-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <KanbanBoardIcon className="size-4 shrink-0 text-(--ui-text-tertiary)" />
              <h1 className="truncate text-[0.9375rem] font-medium tracking-[-0.01em] text-foreground">Kanban Viewer</h1>
              <select
                aria-label="Board"
                className="h-6 rounded-md border border-(--ui-stroke-tertiary) bg-(--ui-bg-card) px-2 text-[0.75rem] text-(--ui-text-secondary) outline-none hover:bg-(--ui-control-hover-background) focus:border-(--ui-stroke-primary)"
                onChange={event => setSelectedBoardSlug(event.target.value)}
                value={selectedBoardSlug}
              >
                {boards.length ? boards.map(board => <option key={board.slug} value={board.slug}>{board.name || board.slug}</option>) : <option value={selectedBoardSlug}>{selectedBoard?.name || 'Default'}</option>}
              </select>
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.75rem] text-(--ui-text-tertiary)">
              <span>Done: {counts.done}</span>
              <span>Running: {counts.running}</span>
              <span>Todo: {counts.todo}</span>
              <span>Blocked: {counts.blocked}</span>
            </div>
          </div>

          <div className="flex min-w-0 shrink-0 items-center gap-1.5">
            <label className="flex h-7 min-w-44 items-center gap-1.5 rounded-md border border-(--ui-stroke-secondary) bg-(--ui-bg-card) px-2 text-(--ui-text-tertiary) focus-within:border-(--ui-stroke-tertiary)">
              <Codicon name="search" size="0.75rem" />
              <input
                className="min-w-0 flex-1 bg-transparent text-[0.75rem] text-foreground placeholder:text-(--ui-text-tertiary) focus:outline-none"
                onChange={event => setFilter(event.target.value)}
                placeholder="Filter tasks…"
                type="text"
                value={filter}
              />
            </label>
            <Button aria-label="Refresh kanban board" className="h-7 px-2 text-[0.75rem]" onClick={() => void refreshTasks()} size="sm" variant="ghost">Refresh</Button>
            <Button aria-label="Dispatch kanban workers unavailable in viewer" className="h-7 px-2 text-[0.75rem]" disabled size="sm" title="Dispatch workers from the CLI for now" variant="ghost">Dispatch</Button>
            <Button aria-label="Toggle compact kanban density" className="h-7 px-2 text-[0.75rem]" onClick={() => setCompact(value => !value)} size="sm" variant={compact ? 'secondary' : 'ghost'}>Compact</Button>
          </div>
        </header>

        {error && <div className="rounded-md border border-[color-mix(in_srgb,var(--ui-red)_28%,var(--ui-stroke-secondary))] bg-[color-mix(in_srgb,var(--ui-red)_6%,var(--ui-bg-card))] px-3 py-2 text-[0.75rem] text-(--ui-text-secondary)">{error}</div>}

        <div className="grid min-h-0 flex-1 grid-cols-4 gap-2.5 overflow-hidden">
          {COLUMNS.map(column => (
            <section
              aria-label={`${column.label} tasks`}
              className="flex min-h-0 flex-col rounded-lg border border-(--ui-stroke-secondary) bg-(--ui-bg-card)/60"
              key={column.id}
            >
              <div className="flex h-8 shrink-0 items-center justify-between border-b border-(--ui-stroke-secondary) px-2.5 text-[0.75rem] text-(--ui-text-tertiary)">
                <span className="font-medium text-(--ui-text-secondary)">{column.label}</span>
                <span className="font-mono text-[0.6875rem] text-(--ui-text-quaternary)">{tasksByColumn[column.id].length}</span>
              </div>
              <div className={cn('min-h-0 flex-1 overflow-y-auto p-1.5', compact ? 'space-y-1' : 'space-y-1.5')}>
                {tasksByColumn[column.id].map(task => (
                  <TaskRow
                    compact={compact}
                    key={task.id}
                    onSelect={() => setSelectedTaskId(task.id)}
                    selected={task.id === selectedTaskId}
                    task={task}
                  />
                ))}
                {!loading && tasksByColumn[column.id].length === 0 && (
                  <div className="grid h-20 place-items-center rounded-md text-[0.75rem] text-(--ui-text-quaternary)">No tasks</div>
                )}
              </div>
            </section>
          ))}
        </div>

        {selectedTask && (
          <aside aria-label="Selected task inspector" className="grid shrink-0 grid-cols-[minmax(0,1fr)_auto] gap-3 rounded-lg border border-(--ui-stroke-secondary) bg-(--ui-bg-card)/55 px-3 py-2 text-[0.75rem] text-(--ui-text-secondary)">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="rounded border border-(--ui-stroke-tertiary) bg-(--ui-bg-card) px-1.5 py-0.5 font-mono text-[0.6875rem] text-(--ui-text-tertiary)">{selectedTask.id}</span>
                <span className="truncate text-foreground">{selectedTask.title}</span>
                <span className="text-(--ui-text-tertiary)">{selectedTask.status}</span>
              </div>
              <div className="mt-1 truncate text-(--ui-text-tertiary)">{latestLog(selectedTask) || 'No recent log'}</div>
            </div>
            <div className="self-center whitespace-nowrap font-mono text-[0.6875rem] text-(--ui-text-tertiary)">HUD overlay compile · {taskProgress(selectedTask) ?? 0}%</div>
          </aside>
        )}
      </div>
    </div>
  )
}

interface TaskRowProps {
  task: KanbanTask
  selected: boolean
  compact: boolean
  onSelect: () => void
}

function TaskRow({ compact, onSelect, selected, task }: TaskRowProps) {
  const progress = taskProgress(task)
  const log = latestLog(task)
  const done = taskColumn(task.status) === 'done'

  return (
    <button
      className={cn(
        'group/task w-full cursor-pointer rounded-md border border-(--ui-stroke-secondary) bg-(--ui-bg-card) text-left transition-colors hover:border-(--ui-stroke-tertiary) hover:bg-(--ui-control-hover-background)',
        compact ? 'px-2 py-1.5' : 'px-2 py-2',
        task.status === 'running' && '[border-left-color:var(--ui-cyan)]',
        task.status === 'review' && '[border-left-color:var(--ui-yellow)]',
        task.status === 'blocked' && '[border-left-color:var(--ui-red)]',
        selected && 'border-(--ui-stroke-tertiary) bg-(--ui-control-active-background)',
        done && 'opacity-55'
      )}
      onClick={onSelect}
      type="button"
    >
      <div className="flex items-center gap-1.5">
        {done && <Codicon className="shrink-0 text-(--ui-text-tertiary)" name="check" size="0.75rem" />}
        <span className="shrink-0 rounded border border-(--ui-stroke-tertiary) bg-(--ui-bg-card) px-1.5 py-0.5 font-mono text-[0.6875rem] leading-none text-(--ui-text-tertiary)">{task.id}</span>
        <span className="truncate text-[0.765625rem] leading-4 text-(--ui-text-secondary) group-hover/task:text-foreground">{task.title}</span>
      </div>
      <div className="mt-1 flex items-center gap-2 text-[0.6875rem] text-(--ui-text-tertiary)">
        <span>{task.status}</span>
        <span>·</span>
        <span>{relativeTaskTime(task)}</span>
        {progress !== null && <span className="ml-auto font-mono">{progress}%</span>}
      </div>
      {progress !== null && (
        <div className="mt-1.5 h-px overflow-hidden rounded-full bg-(--ui-stroke-secondary)">
          <div className="h-full bg-(--ui-cyan) opacity-60" style={{ width: `${progress}%` }} />
        </div>
      )}
      {log && <div className="mt-1 truncate text-[0.6875rem] text-(--ui-text-quaternary)">{log}</div>}
    </button>
  )
}
