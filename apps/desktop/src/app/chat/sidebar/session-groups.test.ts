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
  it('keeps Telegram topic groups above workspace groups even when workspace sessions are newer', () => {
    const sessions = [
      baseSession({ id: 'workspace', cwd: '/tmp/hermes-agent', started_at: 300 }),
      baseSession({
        id: 'topic',
        origin: {
          display_label: 'Dolly Main Projects / ▸ HW-external tilbud',
          group_key: 'telegram:topic:external',
          platform: 'telegram'
        },
        started_at: 100
      })
    ]

    const groups = sessionGroupsFor(sessions)

    expect(groups.map(group => group.label)).toEqual(['Dolly Main Projects / ▸ HW-external tilbud', 'hermes-agent'])
  })
})
