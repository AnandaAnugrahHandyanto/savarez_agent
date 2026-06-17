import { describe, expect, it } from 'vitest'

import type { SubagentNode } from '@/store/subagents'

import { summarizeNodes } from './index'

const node = (overrides: Partial<SubagentNode>): SubagentNode => ({
  children: [],
  filesRead: [],
  filesWritten: [],
  goal: 'worker',
  id: 'worker',
  parentId: null,
  startedAt: 1,
  status: 'running',
  stream: [],
  taskCount: 1,
  taskIndex: 0,
  updatedAt: 1,
  ...overrides
})

describe('Desktop Agents workflow grouping', () => {
  it('summarizes phase task rows without counting child agents as workflow tasks', () => {
    const summary = summarizeNodes([
      node({
        id: 'workflow-task',
        status: 'completed',
        children: [node({ id: 'child-a' }), node({ id: 'child-b', status: 'completed' })]
      })
    ])

    expect(summary).toEqual({
      activeCount: 0,
      completedCount: 1,
      failedCount: 0,
      totalCount: 1
    })
  })
})
