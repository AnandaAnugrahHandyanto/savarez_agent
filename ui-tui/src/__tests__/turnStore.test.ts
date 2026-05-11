import { beforeEach, describe, expect, it } from 'vitest'

import {
  archiveDoneTodos,
  archiveTodosAtTurnEnd,
  getTurnState,
  hydrateDelegationActiveSubagents,
  patchTurnState,
  resetTurnState,
  toggleTodoCollapsed
} from '../app/turnStore.js'

describe('turnStore live progress helpers', () => {
  beforeEach(() => resetTurnState())

  it('archives completed todos into a transcript trail and clears the live anchor', () => {
    patchTurnState({
      todos: [
        { content: 'prep', id: 'prep', status: 'completed' },
        { content: 'serve', id: 'serve', status: 'completed' }
      ]
    })

    expect(archiveTodosAtTurnEnd()).toEqual([
      {
        kind: 'trail',
        role: 'system',
        text: '',
        todoCollapsedByDefault: true,
        todos: [
          { content: 'prep', id: 'prep', status: 'completed' },
          { content: 'serve', id: 'serve', status: 'completed' }
        ]
      }
    ])
    expect(getTurnState().todos).toEqual([])
  })

  it('archives incomplete todos with an incomplete flag so the hint renders', () => {
    patchTurnState({
      todos: [
        { content: 'cook', id: 'cook', status: 'completed' },
        { content: 'serve', id: 'serve', status: 'in_progress' },
        { content: 'eat', id: 'eat', status: 'pending' }
      ]
    })

    const archived = archiveTodosAtTurnEnd()
    expect(archived).toHaveLength(1)
    expect(archived[0]!.todoIncomplete).toBe(true)
    expect(archived[0]!.todos?.map(t => t.id)).toEqual(['cook', 'serve', 'eat'])
    expect(getTurnState().todos).toEqual([])
  })

  it('returns nothing when there are no todos at turn end', () => {
    expect(archiveTodosAtTurnEnd()).toEqual([])
    expect(archiveDoneTodos()).toEqual([])
  })

  it('tracks collapsed state independently of todo content', () => {
    toggleTodoCollapsed()
    expect(getTurnState().todoCollapsed).toBe(true)

    toggleTodoCollapsed()
    expect(getTurnState().todoCollapsed).toBe(false)
  })

  it('hydrates active delegation rows into the live subagent list', () => {
    hydrateDelegationActiveSubagents([
      {
        depth: 1,
        goal: 'inspect delegate_task',
        model: 'openai/gpt-5.4',
        parent_id: 'root-agent',
        started_at: 1715400000,
        status: 'running',
        subagent_id: 'sa-live-1',
        tool_count: 3
      }
    ])

    expect(getTurnState().subagents).toEqual([
      {
        depth: 1,
        goal: 'inspect delegate_task',
        id: 'sa-live-1',
        index: 0,
        model: 'openai/gpt-5.4',
        notes: [],
        parentId: 'root-agent',
        startedAt: 1715400000 * 1000,
        status: 'running',
        taskCount: 1,
        thinking: [],
        toolCount: 3,
        tools: []
      }
    ])
  })

  it('preserves richer local subagent details when delegation.status only refreshes activity metadata', () => {
    patchTurnState({
      subagents: [
        {
          depth: 1,
          goal: 'inspect delegate_task',
          id: 'sa-live-1',
          index: 7,
          model: 'openai/gpt-5.4',
          notes: ['tool batch ready'],
          parentId: 'root-agent',
          startedAt: 1715400000 * 1000,
          status: 'running',
          summary: 'kept locally',
          taskCount: 1,
          thinking: ['reading source'],
          toolCount: 1,
          tools: ['read cli.py']
        }
      ]
    })

    hydrateDelegationActiveSubagents([
      {
        depth: 1,
        goal: 'inspect delegate_task',
        started_at: 1715400005,
        status: 'running',
        subagent_id: 'sa-live-1',
        tool_count: 4
      }
    ])

    expect(getTurnState().subagents).toEqual([
      {
        depth: 1,
        goal: 'inspect delegate_task',
        id: 'sa-live-1',
        index: 7,
        model: 'openai/gpt-5.4',
        notes: ['tool batch ready'],
        parentId: 'root-agent',
        startedAt: 1715400005 * 1000,
        status: 'running',
        summary: 'kept locally',
        taskCount: 1,
        thinking: ['reading source'],
        toolCount: 4,
        tools: ['read cli.py']
      }
    ])
  })
})
