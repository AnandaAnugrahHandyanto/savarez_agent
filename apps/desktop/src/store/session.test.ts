import { beforeEach, describe, expect, it } from 'vitest'

import type { SessionInfo } from '@/types/hermes'

import {
  $workingSessionIds,
  $workingSessionMeta,
  mergeWorkingSessions,
  noteWorkingSessionMeta,
  setSessionWorking,
  type WorkingSessionMeta
} from './session'

function session(id: string, overrides: Partial<SessionInfo> = {}): SessionInfo {
  return {
    cwd: null,
    ended_at: null,
    id,
    input_tokens: 0,
    is_active: true,
    last_active: 1_000,
    message_count: 3,
    model: 'anthropic/claude-opus-4.8',
    output_tokens: 0,
    preview: 'hello',
    source: 'tui',
    started_at: 1_000,
    title: 'Real session',
    tool_call_count: 0,
    ...overrides
  }
}

describe('mergeWorkingSessions', () => {
  it('returns the original list unchanged when nothing is working', () => {
    const sessions = [session('a'), session('b')]

    expect(mergeWorkingSessions(sessions, [], {})).toBe(sessions)
  })

  it('returns the original list when every working session is already loaded', () => {
    const sessions = [session('a'), session('b')]

    expect(mergeWorkingSessions(sessions, ['a'], {})).toBe(sessions)
  })

  it('synthesizes a row for a working session missing from the loaded list', () => {
    const sessions = [session('a')]

    const meta: Record<string, WorkingSessionMeta> = {
      ghost: { cwd: '/work/proj', model: 'openai/gpt-5.4', startedAt: 2_000 }
    }

    const merged = mergeWorkingSessions(sessions, ['ghost'], meta)

    expect(merged).toHaveLength(2)
    // synthetic row is prepended so a recent working session is visible
    expect(merged[0].id).toBe('ghost')
    expect(merged[0].cwd).toBe('/work/proj')
    expect(merged[0].model).toBe('openai/gpt-5.4')
    expect(merged[0].message_count).toBe(0)
    expect(merged[0].title).toBeNull()
    expect(merged[0].started_at).toBe(2_000)
    expect(merged[1].id).toBe('a')
  })

  it('falls back to nulls when no meta is recorded for the working session', () => {
    const merged = mergeWorkingSessions([], ['ghost'], {})

    expect(merged).toHaveLength(1)
    expect(merged[0].id).toBe('ghost')
    expect(merged[0].cwd).toBeNull()
    expect(merged[0].model).toBeNull()
    expect(typeof merged[0].started_at).toBe('number')
  })

  it('only synthesizes the unloaded working ids', () => {
    const sessions = [session('a')]
    const merged = mergeWorkingSessions(sessions, ['a', 'ghost'], {})

    expect(merged.map(s => s.id)).toEqual(['ghost', 'a'])
  })
})

describe('working-session meta lifecycle', () => {
  beforeEach(() => {
    $workingSessionIds.set([])
    $workingSessionMeta.set({})
  })

  it('records meta and preserves startedAt across updates', () => {
    noteWorkingSessionMeta('s1', { cwd: '/a', model: 'm1' })
    const first = $workingSessionMeta.get().s1
    expect(first.cwd).toBe('/a')
    expect(first.model).toBe('m1')

    noteWorkingSessionMeta('s1', { cwd: '/b', model: 'm2' })
    const second = $workingSessionMeta.get().s1
    expect(second.cwd).toBe('/b')
    expect(second.model).toBe('m2')
    // age must stay stable so the row doesn't flicker its timestamp
    expect(second.startedAt).toBe(first.startedAt)
  })

  it('drops meta when the session stops working', () => {
    noteWorkingSessionMeta('s1', { cwd: '/a', model: 'm1' })
    setSessionWorking('s1', true)
    expect($workingSessionMeta.get().s1).toBeDefined()

    setSessionWorking('s1', false)
    expect($workingSessionMeta.get().s1).toBeUndefined()
    expect($workingSessionIds.get()).not.toContain('s1')
  })

  it('ignores empty session ids', () => {
    noteWorkingSessionMeta(null, { cwd: '/a' })
    noteWorkingSessionMeta(undefined, { cwd: '/a' })
    expect($workingSessionMeta.get()).toEqual({})
  })
})
