import { atom } from 'nanostores'

export interface AgentMode {
  color: string
  description: string
  hidden?: boolean
  id: string
  label: string
  prompt?: string
}

export const NO_MODE_ID = 'none'

export const NO_MODE: AgentMode = {
  color: '#D7D7D7',
  description: 'No mode prompt instructions.',
  hidden: true,
  id: NO_MODE_ID,
  label: 'No Mode'
}

export const DEFAULT_AGENT_MODES: AgentMode[] = [
  NO_MODE,
  {
    color: '#9A7BC8',
    description: 'Cursor-style Multi-Task mode: parallelize independent work through subagents.',
    id: 'multitask',
    label: 'Multi-Task',
    prompt: 'Multi-Task Mode: HARD REQUIREMENT — preserve the main agent context window by using delegate_task subagents early, not as an optional last resort. For any codebase/research task that is likely to need more than 2 tool calls, touch more than 1 file, or benefit from inspection plus implementation/review, the parent agent should normally make delegate_task its first tool call. Use one batched delegate_task(tasks=[...]) call with up to 3 independent tasks whenever workstreams can run in parallel. Keep the parent as the lightweight orchestrator: retain the user goal, constraints, final decisions, edits that need direct ownership, and final verification in the main thread; send bulky repo inspection, research, implementation attempts, test failure analysis, and review passes to subagents. Each subagent prompt must be self-contained: include the exact goal, relevant paths/files/errors, constraints, allowed toolsets, expected output shape, and ask for concise findings plus verifiable handles such as files changed, commands run, test output, URLs, or IDs. If delegate_task is unavailable or the task is truly tiny/single-step, briefly say why you are not delegating; otherwise do not proceed manually before delegating. Do not delegate secrets, permission prompts, user-interactive choices, destructive/external side effects, or anything the parent cannot verify. After subagents return, synthesize only the useful results, verify important claims yourself with tools before reporting success, and avoid pasting large child transcripts into the main context.'
  },
  {
    color: '#D6B56D',
    description: 'Cursor-style Plan mode: research and propose an approach before building.',
    id: 'plan',
    label: 'Plan',
    prompt: 'Plan Mode: design the approach before coding or changing state. Ask concise clarifying questions when requirements are ambiguous, inspect enough context to understand scope, and produce a clear reviewable plan before execution.'
  },
  {
    color: '#7FAF8A',
    description: 'Cursor-style Ask mode: read-only explanation and exploration.',
    id: 'ask',
    label: 'Ask',
    prompt: 'Ask Mode: answer and explore without making edits or external changes unless the user explicitly asks to switch into execution. Use read-only inspection and explain clearly. Ask a concise clarifying question when missing context materially changes the answer.'
  },
  {
    color: '#B86B6B',
    description: 'Cursor-style Debug mode: runtime evidence, root cause, fix, verify.',
    id: 'debug',
    label: 'Debug',
    prompt: 'Debug Mode: use a systematic debugging loop. Reproduce or inspect the failure, gather runtime evidence, isolate root cause, make the smallest safe fix, and verify with real tool output. Do not paper over errors or report success without verification.'
  }
]

export const $activeModeId = atom<string>(NO_MODE_ID)
export const $agentModes = atom<AgentMode[]>(DEFAULT_AGENT_MODES)

const cycleableModes = () => $agentModes.get().filter(mode => !mode.hidden || mode.id === NO_MODE_ID)

const modeById = (id: string) => $agentModes.get().find(mode => mode.id === id)

export const getActiveMode = () => modeById($activeModeId.get()) ?? NO_MODE

export const cycleActiveMode = (): AgentMode => {
  const modes = cycleableModes()
  const current = $activeModeId.get()
  const index = Math.max(0, modes.findIndex(mode => mode.id === current))
  const next = modes[(index + 1) % modes.length] ?? NO_MODE

  $activeModeId.set(next.id)

  return next
}
