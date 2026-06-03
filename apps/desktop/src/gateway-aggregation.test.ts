import { describe, expect, it } from 'vitest'

import type {
  DashboardAgentsResponse,
  DashboardConversationsResponse,
  DashboardProjectsResponse,
  PaginatedSessions,
  StatusResponse
} from '@/types/hermes'

import { aggregateGatewayReadModels } from './gateway-aggregation'

const status = (state: string): StatusResponse =>
  ({
    active_sessions: 0,
    config_path: '',
    gateway: { running: state === 'running', state },
    gateway_state: state,
    hermes_home: '',
    version: 'test'
  }) as unknown as StatusResponse

const sessions = (id: string): PaginatedSessions => ({
  limit: 40,
  offset: 0,
  total: 1,
  sessions: [
    {
      cwd: '/work',
      ended_at: null,
      id,
      input_tokens: 0,
      is_active: false,
      last_active: 10,
      message_count: 1,
      model: null,
      output_tokens: 0,
      preview: '',
      source: 'telegram',
      started_at: 1,
      title: null,
      tool_call_count: 0
    }
  ]
})

const agents = (): DashboardAgentsResponse => ({
  agents: [{ id: 'profile:default', kind: 'hermes-profile', name: 'default', profile: 'default' }]
})

const conversations = (): DashboardConversationsResponse => ({
  conversations: [
    {
      display_label: 'Topic',
      id: 'telegram:-1001:11648',
      name: 'Topic',
      platform: 'telegram',
      session_ids: ['same-session'],
      source: ['sessions'],
      type: 'topic'
    }
  ]
})

const projects = (): DashboardProjectsResponse => ({
  projects: [
    {
      chat_id: '-1001',
      conversation_id: 'telegram:-1001:11648',
      id: 'project:telegram:-1001:11648',
      name: 'Topic',
      platform: 'telegram',
      source: 'telegram_topic',
      topic_id: '11648'
    }
  ]
})

describe('aggregateGatewayReadModels', () => {
  it('adds gateway_id and composite ids when two gateways expose colliding session ids', () => {
    const result = aggregateGatewayReadModels([
      {
        connection: { id: 'wsl', name: 'WSL', mode: 'remote', baseUrl: 'http://wsl', kind: 'hermes-dashboard', tokenPreview: null, tokenSet: true },
        status: status('running'),
        sessions: sessions('same-session'),
        agents: agents(),
        conversations: conversations(),
        projects: projects()
      },
      {
        connection: { id: 'mac', name: 'Mac', mode: 'remote', baseUrl: 'http://mac', kind: 'hermes-dashboard', tokenPreview: null, tokenSet: true },
        status: status('running'),
        sessions: sessions('same-session'),
        agents: agents(),
        conversations: conversations(),
        projects: projects()
      }
    ])

    expect(result.sessions.map(session => [session.gateway_id, session.id])).toEqual([
      ['wsl', 'wsl::same-session'],
      ['mac', 'mac::same-session']
    ])
    expect(result.conversations.map(conversation => [conversation.id, conversation.session_ids])).toEqual([
      ['wsl::telegram:-1001:11648', ['wsl::same-session']],
      ['mac::telegram:-1001:11648', ['mac::same-session']]
    ])
    expect(result.projects.map(project => [project.id, project.conversation_id])).toEqual([
      ['wsl::project:telegram:-1001:11648', 'wsl::telegram:-1001:11648'],
      ['mac::project:telegram:-1001:11648', 'mac::telegram:-1001:11648']
    ])
    expect(result.sessionsTotal).toBe(2)
  })

  it('keeps healthy gateway data when one gateway is degraded', () => {
    const result = aggregateGatewayReadModels([
      {
        connection: { id: 'wsl', name: 'WSL', mode: 'remote', baseUrl: 'http://wsl', kind: 'hermes-dashboard', tokenPreview: null, tokenSet: true },
        status: status('running'),
        sessions: sessions('healthy-session'),
        agents: agents(),
        conversations: conversations(),
        projects: projects()
      },
      {
        connection: { id: 'mac', name: 'Mac', mode: 'remote', baseUrl: 'http://mac', kind: 'hermes-dashboard', tokenPreview: null, tokenSet: true },
        error: 'offline'
      }
    ])

    expect(result.sessions.map(session => session.id)).toEqual(['wsl::healthy-session'])
    expect(result.gatewayStates).toEqual([
      { gateway_id: 'wsl', name: 'WSL', ok: true, state: 'running' },
      { error: 'offline', gateway_id: 'mac', name: 'Mac', ok: false, state: 'degraded' }
    ])
  })
})
