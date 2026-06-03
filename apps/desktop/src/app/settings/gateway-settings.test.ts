import { describe, expect, it } from 'vitest'

import type { DesktopConnectionConfig } from '@/global'

import { buildGatewaySettingsPayload } from './gateway-settings'

const config: DesktopConnectionConfig = {
  schemaVersion: 2,
  activeConnectionId: 'remote-2',
  connections: [
    {
      id: 'local',
      name: 'Local gateway',
      kind: 'hermes-dashboard',
      mode: 'local',
      baseUrl: '',
      tokenPreview: null,
      tokenSet: false
    },
    {
      id: 'remote-1',
      name: 'Remote gateway 1',
      kind: 'hermes-dashboard',
      mode: 'remote',
      baseUrl: 'https://old.example/hermes',
      tokenPreview: 'tok…old',
      tokenSet: true
    },
    {
      id: 'remote-2',
      name: 'Remote gateway 2',
      kind: 'hermes-dashboard',
      mode: 'remote',
      baseUrl: 'https://stale.example/hermes',
      tokenPreview: null,
      tokenSet: false
    }
  ],
  envOverride: false,
  mode: 'remote',
  remoteTokenPreview: null,
  remoteTokenSet: false,
  remoteUrl: ''
}

describe('buildGatewaySettingsPayload', () => {
  it('applies visible remote URL and token controls to the active remote connection', () => {
    expect(
      buildGatewaySettingsPayload(config, {
        connectionTokens: {},
        remoteToken: 'new-token',
        remoteUrl: 'https://new.example/hermes'
      })
    ).toMatchObject({
      activeConnectionId: 'remote-2',
      connections: [
        { id: 'local', remoteToken: undefined },
        { id: 'remote-1', baseUrl: 'https://old.example/hermes', remoteToken: undefined },
        { id: 'remote-2', baseUrl: 'https://new.example/hermes', remoteToken: 'new-token' }
      ],
      remoteToken: 'new-token',
      remoteUrl: 'https://new.example/hermes'
    })
  })

  it('keeps per-connection card edits scoped to their own connection', () => {
    expect(
      buildGatewaySettingsPayload(config, {
        connectionTokens: { 'remote-1': 'first-token', 'remote-2': 'second-token' },
        remoteToken: '',
        remoteUrl: ''
      }).connections
    ).toEqual([
      expect.objectContaining({ id: 'local', remoteToken: undefined }),
      expect.objectContaining({ id: 'remote-1', remoteToken: 'first-token' }),
      expect.objectContaining({ id: 'remote-2', remoteToken: 'second-token' })
    ])
  })
})
