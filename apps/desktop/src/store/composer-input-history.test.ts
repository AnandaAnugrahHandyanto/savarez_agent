import { beforeEach, describe, expect, it } from 'vitest'

import {
  $perSessionBrowse,
  browseBackward,
  browseForward,
  deriveUserHistory,
  isBrowsingHistory,
  loadDraftSnapshot,
  resetBrowseState,
  saveDraftSnapshot
} from './composer-input-history'

const SESSION_A = 'session-a'
const SESSION_B = 'session-b'

// Newest-first user text ring, what the caller passes to browse*.
const HISTORY = ['third', 'second', 'first']

const MSG = (role: string, text: string) => ({ id: '', role, text })

beforeEach(() => {
  $perSessionBrowse.set({})
})

describe('deriveUserHistory', () => {
  it('returns user messages newest-first with empty/whitespace skipped', () => {
    const messages = [
      MSG('user', '   '),
      MSG('assistant', 'hi'),
      MSG('user', 'first'),
      MSG('user', 'second')
    ]

    expect(deriveUserHistory(messages, m => m.text)).toEqual(['second', 'first'])
  })
})

describe('browseBackward', () => {
  it('returns null when history is empty', () => {
    expect(browseBackward(SESSION_A, '', [])).toBeNull()
  })

  it('returns the most recent entry on first press and saves the draft', () => {
    const result = browseBackward(SESSION_A, 'unsent draft', HISTORY)

    expect(result).toBe('third')
    expect($perSessionBrowse.get()[SESSION_A]!.draftSnapshot).toBe('unsent draft')
  })

  it('moves to older entries on subsequent presses and stops at the oldest', () => {
    expect(browseBackward(SESSION_A, '', HISTORY)).toBe('third')
    expect(browseBackward(SESSION_A, '', HISTORY)).toBe('second')
    expect(browseBackward(SESSION_A, '', HISTORY)).toBe('first')
    expect(browseBackward(SESSION_A, '', HISTORY)).toBeNull()
  })

  it('uses caller-provided history, not a mirrored ring', () => {
    // The store never owns the ring — the caller passes it every press.
    // If the ring changes between presses (e.g. a new message was sent),
    // the next press sees the updated ring and the cursor continues
    // from where it was within it.
    expect(browseBackward(SESSION_A, '', ['youngest', 'older'])).toBe('youngest')

    // Caller added a new message; ring is now [brand-new, youngest, older].
    // Cursor was at 0, next press advances to 1 -> "youngest".
    expect(
      browseBackward(SESSION_A, '', ['brand-new', 'youngest', 'older'])
    ).toBe('youngest')

    // One more press -> "older".
    expect(
      browseBackward(SESSION_A, '', ['brand-new', 'youngest', 'older'])
    ).toBe('older')
  })
})

describe('browseForward', () => {
  it('returns null when not browsing', () => {
    expect(browseForward(SESSION_A, HISTORY)).toBeNull()
  })

  it('moves toward the present', () => {
    browseBackward(SESSION_A, 'draft', HISTORY) // cursor 0 -> 'third'
    browseBackward(SESSION_A, '', HISTORY) // cursor 1 -> 'second'

    expect(browseForward(SESSION_A, HISTORY)).toEqual({
      text: 'third',
      returnedToPresent: false
    })
  })

  it('restores the saved draft and resets when reaching the present', () => {
    browseBackward(SESSION_A, 'my original draft', HISTORY)

    const result = browseForward(SESSION_A, HISTORY)

    expect(result).toEqual({ text: 'my original draft', returnedToPresent: true })
    expect(isBrowsingHistory(SESSION_A)).toBe(false)
  })
})

describe('per-session isolation', () => {
  it('tracks cursor and draft independently per session', () => {
    browseBackward(SESSION_A, 'draft-a', HISTORY)
    browseBackward(SESSION_A, '', HISTORY) // older

    browseBackward(SESSION_B, 'draft-b', HISTORY)

    const a = $perSessionBrowse.get()[SESSION_A]!
    const b = $perSessionBrowse.get()[SESSION_B]!

    expect(a.cursor).toBe(1)
    expect(a.draftSnapshot).toBe('draft-a')
    expect(b.cursor).toBe(0)
    expect(b.draftSnapshot).toBe('draft-b')
  })
})

describe('resetBrowseState', () => {
  it('clears cursor and draft snapshot', () => {
    browseBackward(SESSION_A, 'draft', HISTORY)
    resetBrowseState(SESSION_A)

    const s = $perSessionBrowse.get()[SESSION_A]!

    expect(s.cursor).toBe(-1)
    expect(s.draftSnapshot).toBe('')
    expect(isBrowsingHistory(SESSION_A)).toBe(false)
  })
})

describe('draft snapshots (unmount/remount persistence)', () => {
  it('saves and restores a draft for a session', () => {
    saveDraftSnapshot(SESSION_A, 'my unsent prompt')

    expect(loadDraftSnapshot(SESSION_A)).toBe('my unsent prompt')
  })

  it('consumes the snapshot on load (one-shot restore)', () => {
    saveDraftSnapshot(SESSION_A, 'once')

    expect(loadDraftSnapshot(SESSION_A)).toBe('once')
    expect(loadDraftSnapshot(SESSION_A)).toBeNull()
  })

  it('returns null when no snapshot exists', () => {
    expect(loadDraftSnapshot(SESSION_A)).toBeNull()
  })

  it('isolates snapshots per session', () => {
    saveDraftSnapshot(SESSION_A, 'draft-a')
    saveDraftSnapshot(SESSION_B, 'draft-b')

    expect(loadDraftSnapshot(SESSION_A)).toBe('draft-a')
    expect(loadDraftSnapshot(SESSION_B)).toBe('draft-b')
  })

  it('ignores null/undefined/empty session IDs', () => {
    saveDraftSnapshot(null, 'text')
    saveDraftSnapshot(undefined, 'text')
    saveDraftSnapshot('', 'text')

    expect(loadDraftSnapshot(null)).toBeNull()
    expect(loadDraftSnapshot(undefined)).toBeNull()
    expect(loadDraftSnapshot('')).toBeNull()
  })

  it('saves empty string as a valid draft', () => {
    saveDraftSnapshot(SESSION_A, '')

    // Empty string is falsy but should be stored and returned as-is.
    // The consumer (ChatBar) checks for null, not falsiness.
    expect(loadDraftSnapshot(SESSION_A)).toBe('')
  })
})

describe('session switch behavior', () => {
  it('resets the previous session cursor and lets the new session derive its own ring', () => {
    // Session A: user browsed into the past
    browseBackward(SESSION_A, '', HISTORY)
    expect(isBrowsingHistory(SESSION_A)).toBe(true)

    // Caller switches to session B; resets A's browse state
    resetBrowseState(SESSION_A)

    // Session B's ring is derived from B's messages, not A's
    const sessionBMessages = [MSG('user', 'hello-b'), MSG('user', 'world-b')]
    const sessionBHistory = deriveUserHistory(sessionBMessages, m => m.text)

    expect(browseBackward(SESSION_B, '', sessionBHistory)).toBe('world-b')
    expect(browseBackward(SESSION_B, '', sessionBHistory)).toBe('hello-b')
    expect(isBrowsingHistory(SESSION_A)).toBe(false)
  })
})
