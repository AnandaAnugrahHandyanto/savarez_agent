import { describe, expect, it } from 'vitest'

import type { SessionInfo } from '@/hermes'

import { sessionGroupsFor, sessionGroupingLabel } from './session-groups'

const baseSession = (overrides: Partial<SessionInfo>): SessionInfo => ({
  archived: false,
  cwd: null,
  ended_at: null,
  id: 'session',
  input_tokens: 0,
  is_active: false,
  last_active: 100,
  message_count: 1,
  model: null,
  output_tokens: 0,
  preview: '',
  source: 'telegram',
  started_at: 100,
  title: null,
  tool_call_count: 0,
  ...overrides
})

describe('sessionGroupingLabel', () => {
  it('prefers Telegram topic/group labels over filesystem workspace labels', () => {
    const session = baseSession({
      cwd: '/home/openclaw/.hermes/hermes-agent',
      origin: {
        chat_name: 'Dolly Main Projects',
        chat_topic: '▸ HWNextApp – /finance',
        chat_type: 'group',
        display_label: 'Dolly Main Projects / ▸ HWNextApp – /finance',
        group_key: 'telegram:topic:finance',
        platform: 'telegram'
      }
    })

    expect(sessionGroupingLabel(session)).toEqual({
      id: 'telegram:topic:finance',
      label: 'Dolly Main Projects / ▸ HWNextApp – /finance',
      path: null
    })
  })

  it('falls back to workspace labels when origin metadata is unavailable', () => {
    const session = baseSession({ cwd: '/home/openclaw/.hermes/hermes-agent' })

    expect(sessionGroupingLabel(session)).toEqual({
      id: '/home/openclaw/.hermes/hermes-agent',
      label: 'hermes-agent',
      path: '/home/openclaw/.hermes/hermes-agent'
    })
  })
})

describe('sessionGroupsFor', () => {
  it('groups sessions by Telegram topic before workspace', () => {
    const sessions = [
      baseSession({
        id: 'a',
        origin: {
          display_label: 'Dolly Main Projects / ▸ HWNextApp – /finance',
          group_key: 'telegram:topic:finance',
          platform: 'telegram'
        },
        started_at: 10
      }),
      baseSession({
        id: 'b',
        origin: {
          display_label: 'Dolly Main Projects / ▸ HWNextApp – /finance',
          group_key: 'telegram:topic:finance',
          platform: 'telegram'
        },
        started_at: 20
      }),
      baseSession({ id: 'c', cwd: '/tmp/example', started_at: 30 })
    ]

    const groups = sessionGroupsFor(sessions)

    expect(groups).toHaveLength(2)
    expect(groups[0]?.label).toBe('Dolly Main Projects / ▸ HWNextApp – /finance')
    expect(groups[0]?.sessions.map(s => s.id)).toEqual(['b', 'a'])
    expect(groups[1]?.label).toBe('example')
  })
})
