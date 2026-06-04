/* @vitest-environment jsdom */
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  deleteEnvVar,
  getEnvVars,
  getHermesConfig,
  getHermesConfigRecord,
  getKanbanBoard,
  getToolsetConfig,
  listAggregatedGatewayData,
  listKanbanBoards,
  revealEnvVar,
  saveHermesConfig,
  selectToolsetProvider,
  setEnvVar,
  toggleToolset
} from './hermes'

describe('gateway-scoped desktop API helpers', () => {
  const api = vi.fn()

  beforeEach(() => {
    api.mockReset()
    window.hermesDesktop = {
      api,
      applyConnectionConfig: vi.fn(),
      getBootProgress: vi.fn(),
      getConnection: vi.fn(),
      getConnectionConfig: vi.fn(),
      saveConnectionConfig: vi.fn(),
      testConnectionConfig: vi.fn(),
      notify: vi.fn()
    } as unknown as typeof window.hermesDesktop
  })

  it('routes config reads and writes through the selected gateway id', async () => {
    api.mockResolvedValueOnce({ model: { provider: 'openrouter' } })
    api.mockResolvedValueOnce({ model: { provider: 'openrouter' } })
    api.mockResolvedValueOnce({ ok: true })

    await getHermesConfig('dolly')
    await getHermesConfigRecord('dolly')
    await saveHermesConfig({ model: { provider: 'openrouter' } }, 'dolly')

    expect(api).toHaveBeenNthCalledWith(1, { gatewayId: 'dolly', path: '/api/config' })
    expect(api).toHaveBeenNthCalledWith(2, { gatewayId: 'dolly', path: '/api/config' })
    expect(api).toHaveBeenNthCalledWith(3, {
      body: { config: { model: { provider: 'openrouter' } } },
      gatewayId: 'dolly',
      method: 'PUT',
      path: '/api/config'
    })
  })

  it('routes kanban board reads through the selected gateway id', async () => {
    api.mockResolvedValueOnce({ boards: [] })
    api.mockResolvedValueOnce({ columns: [] })

    await listKanbanBoards('local')
    await getKanbanBoard({ board: 'board-a', gatewayId: 'local' })

    expect(api).toHaveBeenNthCalledWith(1, { gatewayId: 'local', path: '/api/plugins/kanban/boards' })
    expect(api).toHaveBeenNthCalledWith(2, { gatewayId: 'local', path: '/api/plugins/kanban/board?board=board-a' })
  })

  it('marks dashboard entity endpoints optional during aggregated gateway reads', async () => {
    window.hermesDesktop.getConnectionConfig = vi.fn().mockResolvedValue({
      activeConnectionId: 'remote-1',
      connections: [{ id: 'remote-1', mode: 'remote', name: 'Remote', tokenSet: true }],
      schemaVersion: 2
    })
    api.mockImplementation(({ path }) => {
      if (path === '/api/status') {
        return Promise.resolve({ gateway_state: 'running' })
      }

      if (path.startsWith('/api/sessions')) {
        return Promise.resolve({ limit: 40, offset: 0, sessions: [], total: 0 })
      }

      return Promise.resolve({ __hermesOptionalApiError: `404: missing ${path}` })
    })

    const result = await listAggregatedGatewayData(40)

    expect(api).toHaveBeenCalledWith({ gatewayId: 'remote-1', path: '/api/status' })
    expect(api).toHaveBeenCalledWith({ gatewayId: 'remote-1', optional: true, path: '/api/agents' })
    expect(api).toHaveBeenCalledWith({ gatewayId: 'remote-1', optional: true, path: '/api/conversations' })
    expect(api).toHaveBeenCalledWith({ gatewayId: 'remote-1', optional: true, path: '/api/projects' })
    expect(result.agents).toEqual([])
    expect(result.conversations).toEqual([])
    expect(result.projects).toEqual([])
    expect(result.gatewayStates[0]).toMatchObject({ ok: false, state: 'degraded' })
  })

  it('routes env and toolset settings through the selected gateway id', async () => {
    api.mockResolvedValue({ ok: true })

    await getEnvVars('dolly')
    await setEnvVar('OPENROUTER_API_KEY', '[REDACTED]', 'dolly')
    await revealEnvVar('OPENROUTER_API_KEY', 'dolly')
    await deleteEnvVar('OPENROUTER_API_KEY', 'dolly')
    await toggleToolset('web', true, 'dolly')
    await getToolsetConfig('web', 'dolly')
    await selectToolsetProvider('tts', 'ElevenLabs', 'dolly')

    expect(api).toHaveBeenNthCalledWith(1, { gatewayId: 'dolly', path: '/api/env' })
    expect(api).toHaveBeenNthCalledWith(2, {
      body: { key: 'OPENROUTER_API_KEY', value: '[REDACTED]' },
      gatewayId: 'dolly',
      method: 'PUT',
      path: '/api/env'
    })
    expect(api).toHaveBeenNthCalledWith(3, {
      body: { key: 'OPENROUTER_API_KEY' },
      gatewayId: 'dolly',
      method: 'POST',
      path: '/api/env/reveal'
    })
    expect(api).toHaveBeenNthCalledWith(4, {
      body: { key: 'OPENROUTER_API_KEY' },
      gatewayId: 'dolly',
      method: 'DELETE',
      path: '/api/env'
    })
    expect(api).toHaveBeenNthCalledWith(5, {
      body: { enabled: true },
      gatewayId: 'dolly',
      method: 'PUT',
      path: '/api/tools/toolsets/web'
    })
    expect(api).toHaveBeenNthCalledWith(6, {
      gatewayId: 'dolly',
      path: '/api/tools/toolsets/web/config'
    })
    expect(api).toHaveBeenNthCalledWith(7, {
      body: { provider: 'ElevenLabs' },
      gatewayId: 'dolly',
      method: 'PUT',
      path: '/api/tools/toolsets/tts/provider'
    })
  })
})
