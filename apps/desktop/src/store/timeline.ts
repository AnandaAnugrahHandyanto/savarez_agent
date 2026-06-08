import { atom } from 'nanostores'

/** A user turn in the timeline — corresponds to one user message + its responses. */
export interface TimelineTurn {
  /** Stable message ID of the user message that starts this turn. */
  id: string
  /** Index of the user message in the thread's message array. */
  messageIndex: number
  /** Group index in the virtualizer (turns are grouped). */
  groupIndex: number
}

/** Ordered list of user turns for the current session. */
export const $timelineTurns = atom<TimelineTurn[]>([])

/** Index into $timelineTurns of the turn currently visible in the viewport. */
export const $activeTurnIndex = atom(0)

export function setTimelineTurns(turns: TimelineTurn[]) {
  $timelineTurns.set(turns)
}

export function setActiveTurnIndex(index: number) {
  $activeTurnIndex.set(index)
}

/**
 * Mutable ref for the virtualizer's scrollToIndex function.
 * Set by VirtualizedThread, read by TimelineDots.
 */
let _scrollToGroup: ((groupIndex: number, opts?: { align?: 'start' | 'center' | 'end'; behavior?: 'auto' | 'smooth' }) => void) | null = null

export function setTimelineScrollFn(
  fn: ((groupIndex: number, opts?: { align?: 'start' | 'center' | 'end'; behavior?: 'auto' | 'smooth' }) => void) | null
) {
  _scrollToGroup = fn
}

export function scrollToTimelineGroup(groupIndex: number) {
  _scrollToGroup?.(groupIndex, { align: 'start', behavior: 'smooth' })
}
