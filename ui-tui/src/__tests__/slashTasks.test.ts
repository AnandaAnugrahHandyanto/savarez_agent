import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { shortTaskId, taskAge, taskResultText, truncateTaskText } from '../app/slash/commands/ops.js'
import { findSlashCommand } from '../app/slash/registry.js'
import type { SlashRunCtx } from '../app/slash/types.js'
import type { PanelSection } from '../types.js'

type RpcResponses = Record<string, Record<string, unknown>>

interface Captured {
  pages: [string, string | undefined][]
  panels: [string, PanelSection[]][]
  rpcCalls: [string, Record<string, unknown> | undefined][]
  sysLines: string[]
}

/** Minimal SlashRunCtx double: canned RPC responses, captured transcript. */
const makeCtx = (responses: RpcResponses): { captured: Captured; ctx: SlashRunCtx } => {
  const captured: Captured = { pages: [], panels: [], rpcCalls: [], sysLines: [] }

  const rpc = (method: string, params?: Record<string, unknown>) => {
    captured.rpcCalls.push([method, params])

    return Promise.resolve(responses[method] ?? null)
  }

  const ctx = {
    gateway: { rpc },
    guarded:
      <T>(fn: (r: T) => void) =>
      (r: null | T): void => {
        if (r) {
          fn(r)
        }
      },
    guardedErr: (e: unknown) => captured.sysLines.push(`error: ${String(e)}`),
    sid: 'sess-test',
    stale: () => false,
    transcript: {
      page: (text: string, title?: string) => captured.pages.push([text, title]),
      panel: (title: string, sections: PanelSection[]) => captured.panels.push([title, sections]),
      sys: (text: string) => captured.sysLines.push(text)
    }
  } as unknown as SlashRunCtx

  return { captured, ctx }
}

const flush = () => new Promise<void>(resolve => setImmediate(resolve))

const runTasks = async (arg: string, responses: RpcResponses): Promise<Captured> => {
  const cmd = findSlashCommand('tasks')

  expect(cmd, '/tasks must resolve to a command').toBeDefined()

  const { captured, ctx } = makeCtx(responses)

  cmd!.run(arg, ctx, `/tasks${arg ? ` ${arg}` : ''}`)
  await flush()

  return captured
}

describe('/tasks registration', () => {
  it('resolves to its own registry-backed command, not the /agents overlay alias', () => {
    const cmd = findSlashCommand('tasks')

    expect(cmd).toBeDefined()
    expect(cmd!.name).toBe('tasks')
    expect(findSlashCommand('agents')!.name).toBe('agents')
  })
})

describe('/tasks rendering helpers', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(1_700_000_100_000))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('truncates with whitespace collapse and ellipsis', () => {
    expect(truncateTaskText('plain', 10)).toBe('plain')
    expect(truncateTaskText('multi\n  line   goal', 80)).toBe('multi line goal')
    expect(truncateTaskText('abcdefghij', 5)).toBe('abcd…')
  })

  it('keeps registry-style ids intact, caps pathological ones', () => {
    expect(shortTaskId('sa-0-1a2b3c4d')).toBe('sa-0-1a2b3c4d')
    expect(shortTaskId('x'.repeat(40))).toBe(`${'x'.repeat(17)}…`)
  })

  it('humanizes running age from now and terminal age from finished_at', () => {
    expect(taskAge(undefined)).toBe('?')
    expect(taskAge(1_700_000_010)).toBe('1m 30s')
    expect(taskAge(1_700_000_010, 1_700_000_055)).toBe('45s')
  })

  it('prefers the error message, then conventional output keys', () => {
    expect(taskResultText({ error: { message: 'boom' }, outputs: { output: 'ignored' } })).toBe('error: boom')
    expect(taskResultText({ outputs: { output: 'done' } })).toBe('done')
    expect(taskResultText({ outputs: { stdout: 'from stdout' } })).toBe('from stdout')
    expect(taskResultText({ outputs: {} })).toBe('')
  })
})

describe('/tasks command', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(1_700_000_100_000))
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders one board row per running task', async () => {
    const captured = await runTasks('', {
      'task.list': {
        tasks: [
          {
            goal: 'summarize the release notes for v2 and file follow-up issues in the tracker queue',
            intent: 'agent_task',
            last_tool: 'read_file',
            started_at: 1_700_000_010,
            status: 'running',
            task_id: 'sa-0-1a2b3c4d',
            tool_count: 7
          },
          { goal: '', intent: '', started_at: 1_700_000_095, status: 'running', task_id: 'bg_42', tool_count: 0 }
        ]
      }
    })

    expect(captured.rpcCalls).toEqual([['task.list', {}]])
    expect(captured.panels).toHaveLength(1)

    const [title, sections] = captured.panels[0]!

    expect(title).toBe('Agent tasks')

    const rows = sections[0]!.rows!

    expect(rows).toHaveLength(2)
    expect(rows[0]![0]).toBe('sa-0-1a2b3c4d · running')
    expect(rows[0]![1]).toContain('agent_task · 1m 30s · 7 tools (read_file)')
    expect(rows[0]![1]).toContain('summarize the release notes')
    expect(rows[0]![1]).toContain('…')
    expect(rows[1]![0]).toBe('bg_42 · running')
    expect(rows[1]![1]).toContain('? · 5s')
    expect(rows[1]![1]).not.toContain('tools')
    expect(rows[1]![1]).toContain('(no goal)')
  })

  it('says so when the registry is idle', async () => {
    const captured = await runTasks('', { 'task.list': { tasks: [] } })

    expect(captured.panels).toHaveLength(0)
    expect(captured.sysLines).toEqual(['no active tasks — the agent task registry is idle'])
  })

  it('status: reports a miss as data, not an error', async () => {
    const captured = await runTasks('status sa-9-deadbeef', {
      'task.status': { found: false, task_id: 'sa-9-deadbeef' }
    })

    expect(captured.rpcCalls).toEqual([['task.status', { task_id: 'sa-9-deadbeef' }]])
    expect(captured.sysLines).toEqual(['task not found: sa-9-deadbeef'])
  })

  it('status: renders a terminal snapshot with result status and truncated output', async () => {
    const captured = await runTasks('status sa-0-1a2b3c4d', {
      'task.status': {
        depth: 1,
        finished_at: 1_700_000_055,
        found: true,
        goal: 'do the thing',
        intent: 'agent_task',
        last_tool: 'bash',
        model: 'small',
        parent_task_id: 'sa-root',
        result: { error: null, outputs: { output: `done ${'x'.repeat(400)}` }, status: 'succeeded' },
        session_id: 'sess-test',
        started_at: 1_700_000_010,
        status: 'succeeded',
        task_id: 'sa-0-1a2b3c4d',
        tool_count: 3
      }
    })

    expect(captured.panels).toHaveLength(1)

    const [title, sections] = captured.panels[0]!

    expect(title).toBe('Task sa-0-1a2b3c4d')

    const rows = sections[0]!.rows!

    expect(rows).toContainEqual(['Status', 'succeeded'])
    expect(rows).toContainEqual(['Parent', 'sa-root · depth 1'])
    expect(rows).toContainEqual(['Ran for', '45s'])
    expect(rows).toContainEqual(['Tools', '3 · last: bash'])
    expect(rows).toContainEqual(['Session', 'sess-test'])

    const resultLine = sections[1]!.text!

    expect(resultLine).toContain('result: succeeded · done')
    expect(resultLine).toContain('…')
    expect(resultLine.length).toBeLessThan(330)
  })

  it('status: requires a task_id', async () => {
    const captured = await runTasks('status', {})

    expect(captured.rpcCalls).toHaveLength(0)
    expect(captured.sysLines).toEqual(['usage: /tasks status <task_id>'])
  })

  it('cancel: reports found honestly in both directions', async () => {
    const hit = await runTasks('cancel sa-0-1a2b3c4d', {
      'task.cancel': { found: true, task_id: 'sa-0-1a2b3c4d' }
    })

    expect(hit.sysLines).toEqual(['cancel signalled for sa-0-1a2b3c4d'])

    const miss = await runTasks('cancel bg_42', { 'task.cancel': { found: false, task_id: 'bg_42' } })

    expect(miss.sysLines).toEqual([
      "nothing to cancel for bg_42 — already finished, unknown, or a bg_*/preview_* run (those don't accept cancel yet)"
    ])
  })

  it('rejects unknown subcommands with usage', async () => {
    const captured = await runTasks('bogus', {})

    expect(captured.rpcCalls).toHaveLength(0)
    expect(captured.sysLines).toEqual(['usage: /tasks [status <task_id>|cancel <task_id>]'])
  })
})
