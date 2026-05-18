import { atom } from 'nanostores'
import { useSyncExternalStore } from 'react'

import type { DelegationStatusResponse } from '../gatewayTypes.js'
import { isTodoDone } from '../lib/liveProgress.js'
import type { ActiveTool, ActivityItem, Msg, SubagentProgress, TodoItem } from '../types.js'

const buildTurnState = (): TurnState => ({
  activity: [],
  outcome: '',
  reasoning: '',
  reasoningActive: false,
  reasoningStreaming: false,
  reasoningTokens: 0,
  streamPendingTools: [],
  streamSegments: [],
  streaming: '',
  subagents: [],
  todoCollapsed: false,
  todos: [],
  toolTokens: 0,
  tools: [],
  turnTrail: []
})

export const $turnState = atom<TurnState>(buildTurnState())

export const getTurnState = () => $turnState.get()

const subscribeTurn = (cb: () => void) => $turnState.listen(() => cb())

export const useTurnSelector = <T>(selector: (state: TurnState) => T): T =>
  useSyncExternalStore(
    subscribeTurn,
    () => selector($turnState.get()),
    () => selector($turnState.get())
  )

export const patchTurnState = (next: Partial<TurnState> | ((state: TurnState) => TurnState)) =>
  $turnState.set(typeof next === 'function' ? next($turnState.get()) : { ...$turnState.get(), ...next })

export const toggleTodoCollapsed = () => patchTurnState(state => ({ ...state, todoCollapsed: !state.todoCollapsed }))

export const archiveDoneTodos = () => archiveTodosAtTurnEnd()

export const archiveTodosAtTurnEnd = () => {
  const state = $turnState.get()

  if (!state.todos.length) {
    return []
  }

  const done = isTodoDone(state.todos)

  const msg: Msg = {
    kind: 'trail',
    role: 'system',
    text: '',
    todos: state.todos,
    ...(done ? { todoCollapsedByDefault: true } : { todoIncomplete: true })
  }

  patchTurnState({ todoCollapsed: false, todos: [] })

  return [msg]
}

export const resetTurnState = () => $turnState.set(buildTurnState())

const ACTIVE_STATUS = new Set<SubagentProgress['status']>(['queued', 'running'])

const normalizeDelegationStartedAt = (value: unknown): number | undefined => {
  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    return undefined
  }

  // Gateway payloads use UNIX seconds; the TUI stores ms timestamps.
  return value < 1e12 ? value * 1000 : value
}

const normalizeDelegationStatus = (value: unknown, fallback: SubagentProgress['status']): SubagentProgress['status'] => {
  switch (value) {
    case 'completed':

    case 'failed':

    case 'interrupted':

    case 'queued':

    case 'running':
      return value

    default:
      return fallback
  }
}

export const hydrateDelegationActiveSubagents = (
  active: DelegationStatusResponse['active'] | null | undefined
) => {
  if (!Array.isArray(active) || active.length === 0) {
    return
  }

  patchTurnState(state => {
    let changed = false
    let next = state.subagents

    for (const [index, raw] of active.entries()) {
      const id = typeof raw?.subagent_id === 'string' ? raw.subagent_id.trim() : ''

      if (!id) {
        continue
      }

      const existing = next.find(item => item.id === id)

      const base: SubagentProgress =
        existing ?? {
          depth: typeof raw?.depth === 'number' ? raw.depth : 0,
          goal: typeof raw?.goal === 'string' && raw.goal.trim() ? raw.goal : 'subagent',
          id,
          index,
          notes: [],
          parentId: typeof raw?.parent_id === 'string' ? raw.parent_id : null,
          startedAt: normalizeDelegationStartedAt(raw?.started_at) ?? Date.now(),
          status: normalizeDelegationStatus(raw?.status, 'running'),
          taskCount: 1,
          thinking: [],
          toolCount: typeof raw?.tool_count === 'number' ? raw.tool_count : 0,
          tools: []
        }

      const nextItem: SubagentProgress = {
        ...base,
        depth: typeof raw?.depth === 'number' ? raw.depth : base.depth,
        goal: typeof raw?.goal === 'string' && raw.goal.trim() ? raw.goal : base.goal,
        index: existing?.index ?? base.index,
        model: typeof raw?.model === 'string' && raw.model.trim() ? raw.model : base.model,
        parentId: typeof raw?.parent_id === 'string' ? raw.parent_id : base.parentId,
        startedAt: normalizeDelegationStartedAt(raw?.started_at) ?? base.startedAt,
        status: normalizeDelegationStatus(raw?.status, ACTIVE_STATUS.has(base.status) ? base.status : 'running'),
        toolCount: typeof raw?.tool_count === 'number' ? raw.tool_count : base.toolCount
      }

      const same =
        existing &&
        existing.depth === nextItem.depth &&
        existing.goal === nextItem.goal &&
        existing.index === nextItem.index &&
        existing.model === nextItem.model &&
        existing.parentId === nextItem.parentId &&
        existing.startedAt === nextItem.startedAt &&
        existing.status === nextItem.status &&
        existing.toolCount === nextItem.toolCount

      if (same) {
        continue
      }

      if (next === state.subagents) {
        next = [...state.subagents]
      }

      changed = true

      if (existing) {
        const existingIndex = next.findIndex(item => item.id === id)

        next[existingIndex] = nextItem
      } else {
        next.push(nextItem)
      }
    }

    if (!changed) {
      return state
    }

    next.sort((a, b) => a.depth - b.depth || a.index - b.index)

    return { ...state, subagents: next }
  })
}

export interface TurnState {
  activity: ActivityItem[]
  outcome: string
  reasoning: string
  reasoningActive: boolean
  reasoningStreaming: boolean
  reasoningTokens: number
  streamPendingTools: string[]
  streamSegments: Msg[]
  streaming: string
  subagents: SubagentProgress[]
  todoCollapsed: boolean
  todos: TodoItem[]
  toolTokens: number
  tools: ActiveTool[]
  turnTrail: string[]
}
