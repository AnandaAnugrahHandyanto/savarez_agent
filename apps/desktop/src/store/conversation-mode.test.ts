// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  $conversationModeBySession,
  clearConversationMode,
  getConversationMode,
  setConversationMode,
  toggleConversationMode
} from '@/store/conversation-mode'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const resetAtom = () => $conversationModeBySession.set({})

// ---------------------------------------------------------------------------
// getConversationMode
// ---------------------------------------------------------------------------

describe('getConversationMode', () => {
  beforeEach(resetAtom)
  afterEach(resetAtom)

  it('returns "guidance" for an unknown session', () => {
    expect(getConversationMode('some-session')).toBe('guidance')
  })

  it('returns "guidance" for null', () => {
    expect(getConversationMode(null)).toBe('guidance')
  })

  it('returns "guidance" for undefined', () => {
    expect(getConversationMode(undefined)).toBe('guidance')
  })

  it('returns "guidance" for empty string', () => {
    expect(getConversationMode('')).toBe('guidance')
  })

  it('returns the stored mode', () => {
    $conversationModeBySession.set({ 'sid-1': 'queue' })
    expect(getConversationMode('sid-1')).toBe('queue')
  })
})

// ---------------------------------------------------------------------------
// setConversationMode
// ---------------------------------------------------------------------------

describe('setConversationMode', () => {
  // Use a fake localStorage so we don't pollute the test environment
  let storage: Record<string, string> = {}

  beforeEach(() => {
    storage = {}
    vi.spyOn(window.localStorage, 'getItem').mockImplementation((k: string) => storage[k] ?? null)
    vi.spyOn(window.localStorage, 'setItem').mockImplementation((k: string, v: string) => {
      storage[k] = v
    })
    vi.spyOn(window.localStorage, 'removeItem').mockImplementation((k: string) => {
      delete storage[k]
    })
    resetAtom()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    resetAtom()
  })

  it('sets guidance mode', () => {
    setConversationMode('sid-1', 'guidance')
    expect(getConversationMode('sid-1')).toBe('guidance')
  })

  it('sets queue mode', () => {
    setConversationMode('sid-1', 'queue')
    expect(getConversationMode('sid-1')).toBe('queue')
  })

  it('persists to localStorage', () => {
    setConversationMode('sid-persist', 'queue')
    // The store writes JSON to the well-known key in jsdom's real localStorage
    const raw = localStorage.getItem('hermes.desktop.conversationMode.v1')
    expect(raw).toBeTruthy()
    const parsed = JSON.parse(raw ?? '{}')
    expect(parsed['sid-persist']).toBe('queue')
    // Clean up
    localStorage.removeItem('hermes.desktop.conversationMode.v1')
  })

  it('does not update atom or storage if mode is unchanged', () => {
    setConversationMode('sid-1', 'queue')
    const snapshot1 = $conversationModeBySession.get()
    setConversationMode('sid-1', 'queue')
    const snapshot2 = $conversationModeBySession.get()

    expect(snapshot1).toBe(snapshot2) // same object reference — no re-set
  })

  it('is a no-op for empty session id', () => {
    setConversationMode('', 'queue')
    expect(Object.keys($conversationModeBySession.get()).length).toBe(0)
  })

  it('does not affect other sessions', () => {
    setConversationMode('sid-1', 'queue')
    setConversationMode('sid-2', 'guidance')

    expect(getConversationMode('sid-1')).toBe('queue')
    expect(getConversationMode('sid-2')).toBe('guidance')
  })
})

// ---------------------------------------------------------------------------
// toggleConversationMode
// ---------------------------------------------------------------------------

describe('toggleConversationMode', () => {
  beforeEach(resetAtom)
  afterEach(resetAtom)

  it('toggles from guidance to queue', () => {
    setConversationMode('sid-1', 'guidance')
    toggleConversationMode('sid-1')
    expect(getConversationMode('sid-1')).toBe('queue')
  })

  it('toggles from queue to guidance', () => {
    setConversationMode('sid-1', 'queue')
    toggleConversationMode('sid-1')
    expect(getConversationMode('sid-1')).toBe('guidance')
  })

  it('starts from "guidance" default for an unknown session', () => {
    toggleConversationMode('sid-new')
    expect(getConversationMode('sid-new')).toBe('queue')
  })
})

// ---------------------------------------------------------------------------
// clearConversationMode
// ---------------------------------------------------------------------------

describe('clearConversationMode', () => {
  beforeEach(resetAtom)
  afterEach(resetAtom)

  it('removes a stored mode', () => {
    setConversationMode('sid-1', 'queue')
    clearConversationMode('sid-1')
    expect('sid-1' in $conversationModeBySession.get()).toBe(false)
    expect(getConversationMode('sid-1')).toBe('guidance')
  })

  it('is a no-op for a non-existent session', () => {
    const before = $conversationModeBySession.get()
    clearConversationMode('does-not-exist')
    expect($conversationModeBySession.get()).toBe(before)
  })
})
