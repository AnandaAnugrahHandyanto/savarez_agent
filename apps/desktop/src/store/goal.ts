import { atom } from 'nanostores'

import { $gateway } from './gateway'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** The lifecycle state of an active /goal, mirroring what the backend emits. */
export type GoalLifecycleState = 'active' | 'paused' | 'waiting' | 'completed' | 'failed'

export interface SessionGoalState {
  /** Short title / goal description (first line of the /goal command). */
  title: string
  state: GoalLifecycleState
  /** The next planned action or step, if the backend emits it. */
  nextStep?: string
  /** The last time this goal state was updated (Date.now() on the client). */
  updatedAt: number
}

// ---------------------------------------------------------------------------
// Atom
// ---------------------------------------------------------------------------

/** Map of sessionId → goal state (undefined = no active goal). */
export const $goalBySession = atom<Record<string, SessionGoalState | undefined>>({})

// ---------------------------------------------------------------------------
// Writers
// ---------------------------------------------------------------------------

export function setSessionGoal(sid: string, goal: SessionGoalState | undefined): void {
  const current = $goalBySession.get()
  const existing = current[sid]

  // Skip update if nothing changed (prevents spurious re-renders).
  if (
    existing === goal ||
    (existing &&
      goal &&
      existing.state === goal.state &&
      existing.title === goal.title &&
      existing.nextStep === goal.nextStep)
  ) {
    return
  }

  if (goal === undefined) {
    if (!(sid in current)) {
      return
    }

    const next = { ...current }
    delete next[sid]
    $goalBySession.set(next)
  } else {
    $goalBySession.set({ ...current, [sid]: goal })
  }
}

export function clearSessionGoal(sid: string): void {
  setSessionGoal(sid, undefined)
}

// ---------------------------------------------------------------------------
// Goal response parser
// ---------------------------------------------------------------------------

/**
 * Parse the text response from `/goal status` (or a `session.info` goal
 * field) into a {@link SessionGoalState}.
 *
 * The backend can respond with either:
 *   a) A JSON object: `{ active, title, state, next_step, updated_at }`
 *   b) Plain text: rendered goal status.
 *
 * In case (b) we extract what we can and fall back gracefully.
 */
export function parseGoalResponse(
  raw: string | Record<string, unknown>
): SessionGoalState | undefined {
  if (!raw) {
    return undefined
  }

  // --- JSON path ---
  const obj: Record<string, unknown> =
    typeof raw === 'string'
      ? (() => {
          try {
            const parsed = JSON.parse(raw)

            return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
              ? (parsed as Record<string, unknown>)
              : {}
          } catch {
            return {}
          }
        })()
      : raw

  if (obj.active === false || obj.state === 'none' || obj.state === 'not_set') {
    return undefined
  }

  if (obj.title || obj.state) {
    const rawState = String(obj.state ?? 'active')
    const state: GoalLifecycleState = isGoalState(rawState) ? rawState : 'active'

    return {
      title: String(obj.title ?? obj.goal ?? '').trim() || 'Active goal',
      state,
      nextStep: obj.next_step ? String(obj.next_step).trim() : undefined,
      updatedAt: typeof obj.updated_at === 'number' ? obj.updated_at : Date.now()
    }
  }

  // --- Plain text fallback ---
  const text = typeof raw === 'string' ? raw.trim() : ''

  if (!text || text.toLowerCase().includes('no goal') || text.toLowerCase().includes('not set')) {
    return undefined
  }

  // Extract the first non-empty line as the title.
  const firstLine = text.split('\n').find(l => l.trim()) ?? text

  return {
    title: firstLine.slice(0, 120),
    state: 'active',
    updatedAt: Date.now()
  }
}

function isGoalState(value: string): value is GoalLifecycleState {
  return ['active', 'paused', 'waiting', 'completed', 'failed'].includes(value)
}

// ---------------------------------------------------------------------------
// Gateway refresh
// ---------------------------------------------------------------------------

/**
 * Pull the current /goal state from the backend for one session.
 *
 * Called:
 *   - On session mount (once).
 *   - After each `message.complete` event.
 *   - When the user clicks a goal action (pause/resume/end) to get the
 *     updated state immediately.
 */
export async function refreshSessionGoal(sid: string): Promise<void> {
  const gateway = $gateway.get()

  if (!sid || !gateway) {
    return
  }

  try {
    const result = await gateway.request<{ text?: string; response?: string }>(
      'slash.exec',
      { command: '/goal status', session_id: sid }
    )

    const raw = result?.text ?? result?.response ?? ''
    const goal = parseGoalResponse(raw)
    setSessionGoal(sid, goal)
  } catch {
    // Transient failure — leave the previous state as-is.
  }
}

/**
 * Send a /goal sub-command (pause/resume/end) and immediately refresh state.
 */
export async function sendGoalCommand(sid: string, subcommand: 'pause' | 'resume' | 'end'): Promise<void> {
  const gateway = $gateway.get()

  if (!sid || !gateway) {
    return
  }

  try {
    await gateway.request('slash.exec', {
      command: `/goal ${subcommand}`,
      session_id: sid
    })
  } catch {
    // best-effort
  }

  await refreshSessionGoal(sid)
}
