import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import {
  $goalBySession,
  clearSessionGoal,
  parseGoalResponse,
  setSessionGoal,
  type SessionGoalState
} from '@/store/goal'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeGoal = (overrides: Partial<SessionGoalState> = {}): SessionGoalState => ({
  title: 'Fix the auth bug',
  state: 'active',
  updatedAt: Date.now(),
  ...overrides
})

// ---------------------------------------------------------------------------
// parseGoalResponse
// ---------------------------------------------------------------------------

describe('parseGoalResponse', () => {
  it('returns undefined for empty/falsy input', () => {
    expect(parseGoalResponse('')).toBeUndefined()
    expect(parseGoalResponse({})).toBeUndefined()
  })

  it('returns undefined when JSON reports active=false', () => {
    expect(parseGoalResponse(JSON.stringify({ active: false, title: 'test' }))).toBeUndefined()
  })

  it('returns undefined when state is "none"', () => {
    expect(parseGoalResponse({ state: 'none', title: 'test' })).toBeUndefined()
  })

  it('parses a full JSON object with all fields', () => {
    const raw = {
      title: 'Refactor auth layer',
      state: 'active',
      next_step: 'Write unit tests for JWTMiddleware',
      updated_at: 1_700_000_000
    }
    const result = parseGoalResponse(raw)

    expect(result).toBeDefined()
    expect(result!.title).toBe('Refactor auth layer')
    expect(result!.state).toBe('active')
    expect(result!.nextStep).toBe('Write unit tests for JWTMiddleware')
    expect(result!.updatedAt).toBe(1_700_000_000)
  })

  it('parses a JSON string', () => {
    const raw = JSON.stringify({ title: 'Fix bug', state: 'paused' })
    const result = parseGoalResponse(raw)

    expect(result).toBeDefined()
    expect(result!.title).toBe('Fix bug')
    expect(result!.state).toBe('paused')
  })

  it('defaults unknown state to "active"', () => {
    const result = parseGoalResponse({ title: 'Test', state: 'UNKNOWN_VALUE' })

    expect(result!.state).toBe('active')
  })

  it('falls back to plain text, extracting first line as title', () => {
    const raw = 'Implement the OAuth flow\nNext: add token refresh'
    const result = parseGoalResponse(raw)

    expect(result).toBeDefined()
    expect(result!.title).toContain('Implement the OAuth flow')
    expect(result!.state).toBe('active')
  })

  it('returns undefined for "no goal" plain text', () => {
    expect(parseGoalResponse('No goal is currently set.')).toBeUndefined()
    expect(parseGoalResponse('No goal active.')).toBeUndefined()
  })

  it('handles paused state', () => {
    const result = parseGoalResponse({ title: 'Deploy feature', state: 'paused' })

    expect(result!.state).toBe('paused')
  })

  it('handles completed state', () => {
    const result = parseGoalResponse({ title: 'Done', state: 'completed' })

    expect(result!.state).toBe('completed')
  })

  it('handles failed state', () => {
    const result = parseGoalResponse({ title: 'Failed task', state: 'failed' })

    expect(result!.state).toBe('failed')
  })

  it('truncates extremely long plain-text titles to 120 chars', () => {
    const longText = 'x'.repeat(200)
    const result = parseGoalResponse(longText)

    expect(result!.title.length).toBeLessThanOrEqual(120)
  })
})

// ---------------------------------------------------------------------------
// setSessionGoal / clearSessionGoal
// ---------------------------------------------------------------------------

describe('setSessionGoal', () => {
  beforeEach(() => {
    $goalBySession.set({})
  })

  afterEach(() => {
    $goalBySession.set({})
  })

  it('adds a goal for a session', () => {
    const goal = makeGoal()
    setSessionGoal('sid-1', goal)

    expect($goalBySession.get()['sid-1']).toEqual(goal)
  })

  it('updates an existing goal', () => {
    const original = makeGoal({ state: 'active' })
    setSessionGoal('sid-1', original)

    const updated = makeGoal({ state: 'paused', updatedAt: original.updatedAt + 1 })
    setSessionGoal('sid-1', updated)

    expect($goalBySession.get()['sid-1']?.state).toBe('paused')
  })

  it('does not mutate other sessions', () => {
    const goal1 = makeGoal({ title: 'Goal 1' })
    const goal2 = makeGoal({ title: 'Goal 2' })
    setSessionGoal('sid-1', goal1)
    setSessionGoal('sid-2', goal2)

    expect($goalBySession.get()['sid-1']?.title).toBe('Goal 1')
    expect($goalBySession.get()['sid-2']?.title).toBe('Goal 2')
  })

  it('is a no-op if the state is identical (referential equality skipped, value equality)', () => {
    const goal = makeGoal()
    setSessionGoal('sid-1', goal)
    const before = $goalBySession.get()

    // Set the same values again — atom should not be re-set
    setSessionGoal('sid-1', { ...goal })
    const after = $goalBySession.get()

    // Same reference because the skip guard kept the old object
    expect(before).toBe(after)
  })
})

describe('clearSessionGoal', () => {
  beforeEach(() => {
    $goalBySession.set({})
  })

  afterEach(() => {
    $goalBySession.set({})
  })

  it('removes an existing goal', () => {
    setSessionGoal('sid-1', makeGoal())
    clearSessionGoal('sid-1')

    expect($goalBySession.get()['sid-1']).toBeUndefined()
    expect('sid-1' in $goalBySession.get()).toBe(false)
  })

  it('is a no-op if the session has no goal', () => {
    const before = $goalBySession.get()
    clearSessionGoal('non-existent')
    const after = $goalBySession.get()

    expect(before).toBe(after)
  })
})
