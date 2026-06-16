import { describe, expect, it } from 'vitest'

import { buildWorkflowPhases } from '../components/agentsOverlay.js'
import type { SubagentProgress } from '../types.js'

const subagent = (overrides: Partial<SubagentProgress>): SubagentProgress => ({
  depth: 0,
  goal: 'worker',
  id: 'worker',
  index: 0,
  notes: [],
  parentId: null,
  status: 'running',
  taskCount: 1,
  thinking: [],
  toolCount: 0,
  tools: [],
  ...overrides
})

describe('agents overlay workflow phases', () => {
  it('keeps non-workflow agents visible in mixed workflow turns', () => {
    const phases = buildWorkflowPhases([
      subagent({
        id: 'workflow-worker',
        status: 'completed',
        workflowId: 'wf-demo',
        workflowNodeId: 'recon',
        workflowPhaseId: 'research',
        workflowPhaseTitle: 'Research',
        workflowTaskTitle: 'Map inputs'
      }),
      subagent({ goal: 'plain delegate task', id: 'plain-worker', status: 'running' })
    ])

    expect(phases.map(phase => phase.title)).toEqual(['Research', 'Other agents'])
    expect(phases[1]?.ids.has('plain-worker')).toBe(true)
    expect(phases[1]).toMatchObject({
      activeCount: 1,
      completedCount: 0,
      totalCount: 1
    })
  })
})
