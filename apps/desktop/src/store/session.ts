import { atom } from 'nanostores'

import type { ContextSuggestion } from '@/app/types'
import type { HermesConnection } from '@/global'
import type { ChatMessage } from '@/lib/chat-messages'
import type { SessionInfo, UsageStats } from '@/types/hermes'

type Updater<T> = T | ((current: T) => T)

export interface WorkingSessionMeta {
  cwd: string | null
  model: string | null
  startedAt: number
}

interface AppAtom<T> {
  get: () => T
  set: (value: T) => void
}

function updateAtom<T>(store: AppAtom<T>, next: Updater<T>) {
  store.set(typeof next === 'function' ? (next as (current: T) => T)(store.get()) : next)
}

export const $connection = atom<HermesConnection | null>(null)
export const $gatewayState = atom('idle')
export const $sessions = atom<SessionInfo[]>([])
export const $sessionsTotal = atom<number>(0)
export const $sessionsLoading = atom(true)
export const $workingSessionIds = atom<string[]>([])
// Minimal runtime metadata for sessions that are currently working but may
// not yet appear in the loaded `$sessions` list — e.g. an untitled session
// whose agent is mid-turn with zero persisted messages, which the backend
// session list (min_messages=1) filters out. Keyed by stored session id.
export const $workingSessionMeta = atom<Record<string, WorkingSessionMeta>>({})
export const $activeSessionId = atom<string | null>(null)
export const $selectedStoredSessionId = atom<string | null>(null)
export const $messages = atom<ChatMessage[]>([])
export const $freshDraftReady = atom(false)
export const $busy = atom(false)
export const $awaitingResponse = atom(false)
export const $currentModel = atom('')
export const $currentProvider = atom('')
export const $currentReasoningEffort = atom('')
export const $currentServiceTier = atom('')
export const $currentFastMode = atom(false)
export const $currentCwd = atom('')
export const $currentBranch = atom('')
export const $currentUsage = atom<UsageStats>({
  calls: 0,
  input: 0,
  output: 0,
  total: 0
})
export const $sessionStartedAt = atom<number | null>(null)
export const $turnStartedAt = atom<number | null>(null)
export const $introPersonality = atom('')
export const $currentPersonality = atom('')
export const $availablePersonalities = atom<string[]>([])
export const $introSeed = atom(0)
export const $contextSuggestions = atom<ContextSuggestion[]>([])
export const $modelPickerOpen = atom(false)

export const setConnection = (next: Updater<HermesConnection | null>) => updateAtom($connection, next)
export const setGatewayState = (next: Updater<string>) => updateAtom($gatewayState, next)
export const setSessions = (next: Updater<SessionInfo[]>) => updateAtom($sessions, next)
export const setSessionsTotal = (next: Updater<number>) => updateAtom($sessionsTotal, next)
export const setSessionsLoading = (next: Updater<boolean>) => updateAtom($sessionsLoading, next)
export const setWorkingSessionIds = (next: Updater<string[]>) => updateAtom($workingSessionIds, next)
export const setWorkingSessionMeta = (next: Updater<Record<string, WorkingSessionMeta>>) =>
  updateAtom($workingSessionMeta, next)
export const setActiveSessionId = (next: Updater<string | null>) => updateAtom($activeSessionId, next)
export const setSelectedStoredSessionId = (next: Updater<string | null>) => updateAtom($selectedStoredSessionId, next)
export const setMessages = (next: Updater<ChatMessage[]>) => updateAtom($messages, next)
export const setFreshDraftReady = (next: Updater<boolean>) => updateAtom($freshDraftReady, next)
export const setBusy = (next: Updater<boolean>) => updateAtom($busy, next)
export const setAwaitingResponse = (next: Updater<boolean>) => updateAtom($awaitingResponse, next)
export const setCurrentModel = (next: Updater<string>) => updateAtom($currentModel, next)
export const setCurrentProvider = (next: Updater<string>) => updateAtom($currentProvider, next)
export const setCurrentReasoningEffort = (next: Updater<string>) => updateAtom($currentReasoningEffort, next)
export const setCurrentServiceTier = (next: Updater<string>) => updateAtom($currentServiceTier, next)
export const setCurrentFastMode = (next: Updater<boolean>) => updateAtom($currentFastMode, next)
export const setCurrentCwd = (next: Updater<string>) => updateAtom($currentCwd, next)
export const setCurrentBranch = (next: Updater<string>) => updateAtom($currentBranch, next)
export const setCurrentUsage = (next: Updater<UsageStats>) => updateAtom($currentUsage, next)
export const setSessionStartedAt = (next: Updater<number | null>) => updateAtom($sessionStartedAt, next)
export const setTurnStartedAt = (next: Updater<number | null>) => updateAtom($turnStartedAt, next)
export const setIntroPersonality = (next: Updater<string>) => updateAtom($introPersonality, next)
export const setCurrentPersonality = (next: Updater<string>) => updateAtom($currentPersonality, next)
export const setAvailablePersonalities = (next: Updater<string[]>) => updateAtom($availablePersonalities, next)
export const setIntroSeed = (next: Updater<number>) => updateAtom($introSeed, next)
export const setContextSuggestions = (next: Updater<ContextSuggestion[]>) => updateAtom($contextSuggestions, next)
export const setModelPickerOpen = (next: Updater<boolean>) => updateAtom($modelPickerOpen, next)

export function setSessionWorking(sessionId: string | null | undefined, working: boolean) {
  if (!sessionId) {
    return
  }

  setWorkingSessionIds(current => {
    const alreadyWorking = current.includes(sessionId)

    if (working) {
      return alreadyWorking ? current : [...current, sessionId]
    }

    return alreadyWorking ? current.filter(id => id !== sessionId) : current
  })

  // Drop synthetic-row metadata once a session stops working. Its real row
  // (if any) comes back through the normal session list on the next refresh.
  if (!working) {
    setWorkingSessionMeta(current => {
      if (!(sessionId in current)) {
        return current
      }

      const { [sessionId]: _removed, ...rest } = current

      return rest
    })
  }
}

// Record just enough about a working session to render a synthetic sidebar
// row for it before it lands in the loaded session list. Idempotent: the
// startedAt timestamp is preserved across updates so the row's age is stable.
export function noteWorkingSessionMeta(
  sessionId: string | null | undefined,
  meta: { cwd?: string | null; model?: string | null }
) {
  if (!sessionId) {
    return
  }

  setWorkingSessionMeta(current => {
    const existing = current[sessionId]
    const cwd = meta.cwd ?? existing?.cwd ?? null
    const model = meta.model ?? existing?.model ?? null

    if (existing && existing.cwd === cwd && existing.model === model) {
      return current
    }

    return {
      ...current,
      [sessionId]: { cwd, model, startedAt: existing?.startedAt ?? Date.now() / 1000 }
    }
  })
}

// Merge synthetic rows for working sessions that aren't in the loaded list.
// Pure so it can be unit-tested and reused by any sidebar surface.
export function mergeWorkingSessions(
  sessions: SessionInfo[],
  workingIds: string[],
  meta: Record<string, WorkingSessionMeta>
): SessionInfo[] {
  if (!workingIds.length) {
    return sessions
  }

  const known = new Set(sessions.map(s => s.id))
  const synthetic: SessionInfo[] = []

  for (const id of workingIds) {
    if (known.has(id)) {
      continue
    }

    const info = meta[id]
    const startedAt = info?.startedAt ?? Date.now() / 1000

    synthetic.push({
      cwd: info?.cwd ?? null,
      ended_at: null,
      id,
      input_tokens: 0,
      is_active: true,
      last_active: startedAt,
      message_count: 0,
      model: info?.model ?? null,
      output_tokens: 0,
      preview: null,
      source: 'tui',
      started_at: startedAt,
      title: null,
      tool_call_count: 0
    })
  }

  return synthetic.length ? [...synthetic, ...sessions] : sessions
}
