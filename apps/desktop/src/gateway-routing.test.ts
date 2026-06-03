import { describe, expect, it } from 'vitest'

import type { DesktopConnectionRegistryEntry } from '@/global'
import type { DashboardProject, SessionInfo } from '@/types/hermes'

import { resolveRouteSelection, routeRequestOptionsForSession } from './gateway-routing'

const connection = (id: string): DesktopConnectionRegistryEntry => ({
  id,
  name: id.toUpperCase(),
  mode: 'remote',
  baseUrl: `http://${id}`,
  kind: 'hermes-dashboard',
  tokenPreview: null,
  tokenSet: true
})

const project = (overrides: Partial<DashboardProject>): DashboardProject => ({
  chat_id: '-1001',
  conversation_id: 'wsl::telegram:-1001:11648',
  gateway_id: 'wsl',
  id: 'wsl::project:telegram:-1001:11648',
  name: 'Vw AI render',
  platform: 'telegram',
  source: 'telegram_topic',
  topic_id: '11648',
  ...overrides
})

const session = (overrides: Partial<SessionInfo>): SessionInfo => ({
  cwd: null,
  ended_at: null,
  id: 'wsl::session-1',
  input_tokens: 0,
  is_active: true,
  last_active: 1,
  message_count: 1,
  model: null,
  output_tokens: 0,
  preview: null,
  source: 'tui',
  started_at: 1,
  title: null,
  tool_call_count: 0,
  ...overrides
})

describe('resolveRouteSelection', () => {
  it('requires one explicit selected gateway before sending a new chat', () => {
    const resolved = resolveRouteSelection({
      connections: [connection('wsl'), connection('mac')],
      projects: [],
      selectedGatewayId: null
    })

    expect(resolved).toEqual({
      ok: false,
      reason: 'missing-gateway',
      message: 'Select one gateway before sending.'
    })
  })

  it('routes a selected project through its selected gateway only', () => {
    const resolved = resolveRouteSelection({
      connections: [connection('wsl'), connection('mac')],
      projects: [project({})],
      selectedGatewayId: 'wsl',
      selectedProjectId: 'wsl::project:telegram:-1001:11648'
    })

    expect(resolved).toEqual({
      ok: true,
      gatewayId: 'wsl',
      projectId: 'wsl::project:telegram:-1001:11648',
      target: {
        chat_id: '-1001',
        conversation_id: 'wsl::telegram:-1001:11648',
        platform: 'telegram',
        topic_id: '11648'
      }
    })
  })

  it('blocks an ambiguous project label exposed by two gateways instead of guessing', () => {
    const resolved = resolveRouteSelection({
      connections: [connection('wsl'), connection('mac')],
      projects: [
        project({ gateway_id: 'wsl', id: 'wsl::project:telegram:-1001:11648' }),
        project({
          conversation_id: 'mac::telegram:-1001:11648',
          gateway_id: 'mac',
          id: 'mac::project:telegram:-1001:11648'
        })
      ],
      selectedGatewayId: 'wsl',
      selectedProjectId: 'project:telegram:-1001:11648'
    })

    expect(resolved).toEqual({
      ok: false,
      reason: 'ambiguous-project',
      message: 'Project Vw AI render exists on multiple gateways. Choose the gateway-specific project row before sending.',
      gatewayIds: ['wsl', 'mac']
    })
  })
})

describe('routeRequestOptionsForSession', () => {
  it('uses the selected gateway id for new session create and later prompt submit calls', () => {
    expect(routeRequestOptionsForSession({ gatewayId: 'wsl' })).toEqual({ gatewayId: 'wsl', params: {} })
    expect(routeRequestOptionsForSession({ gatewayId: 'wsl', session: session({ id: 'wsl::session-1' }) })).toEqual({
      gatewayId: 'wsl',
      params: { session_id: 'session-1' }
    })
  })
})
