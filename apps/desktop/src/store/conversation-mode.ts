import { atom } from 'nanostores'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Per-conversation interaction mode:
 *
 * - `guidance` (default): Hermes processes each message immediately with a
 *   full response. Suitable for /goal, debugging loops, research workflows.
 *
 * - `queue`: Each submitted message is appended to the queue instead of sent
 *   immediately. Hermes acknowledges items briefly. Suitable for dropping
 *   multiple tasks without triggering a full response per item.
 */
export type ConversationMode = 'guidance' | 'queue'

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'hermes.desktop.conversationMode.v1'

const load = (): Record<string, ConversationMode> => {
  if (typeof window === 'undefined') {
    return {}
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : null

    return parsed && typeof parsed === 'object' && !Array.isArray(parsed)
      ? (parsed as Record<string, ConversationMode>)
      : {}
  } catch {
    return {}
  }
}

const save = (state: Record<string, ConversationMode>): void => {
  if (typeof window === 'undefined') {
    return
  }

  try {
    if (Object.keys(state).length === 0) {
      window.localStorage.removeItem(STORAGE_KEY)
    } else {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    }
  } catch {
    // best-effort: storage may be unavailable
  }
}

// ---------------------------------------------------------------------------
// Atom
// ---------------------------------------------------------------------------

export const $conversationModeBySession = atom<Record<string, ConversationMode>>(load())

// ---------------------------------------------------------------------------
// Accessors
// ---------------------------------------------------------------------------

/** Get the current conversation mode for a session (defaults to `guidance`). */
export function getConversationMode(sid: string | null | undefined): ConversationMode {
  const trimmed = sid?.trim()

  if (!trimmed) {
    return 'guidance'
  }

  return $conversationModeBySession.get()[trimmed] ?? 'guidance'
}

/** Set the conversation mode for a session and persist it. */
export function setConversationMode(sid: string, mode: ConversationMode): void {
  const trimmed = sid.trim()

  if (!trimmed) {
    return
  }

  const current = $conversationModeBySession.get()

  if (current[trimmed] === mode) {
    return
  }

  const next = { ...current, [trimmed]: mode }
  $conversationModeBySession.set(next)
  save(next)
}

/** Toggle between guidance ↔ queue for a session. */
export function toggleConversationMode(sid: string): void {
  const current = getConversationMode(sid)
  setConversationMode(sid, current === 'guidance' ? 'queue' : 'guidance')
}

/** Remove the stored mode for a session (e.g. on session delete). */
export function clearConversationMode(sid: string): void {
  const trimmed = sid.trim()

  if (!trimmed) {
    return
  }

  const current = $conversationModeBySession.get()

  if (!(trimmed in current)) {
    return
  }

  const next = { ...current }
  delete next[trimmed]
  $conversationModeBySession.set(next)
  save(next)
}
