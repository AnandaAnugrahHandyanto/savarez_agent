import { QueryClient } from '@tanstack/react-query'
import { cleanup, render, renderHook, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { getGlobalModelInfo } from '@/hermes'
import {
  $activeSessionId,
  $currentModel,
  $currentProvider,
  setCurrentModel,
  setCurrentProvider
} from '@/store/session'

import { useModelControls } from './use-model-controls'

vi.mock('@/hermes', () => ({
  getGlobalModelInfo: vi.fn(async () => ({ model: 'global-model', provider: 'global-provider' })),
  setGlobalModel: vi.fn(async () => undefined)
}))

vi.mock('@/store/notifications', () => ({
  notifyError: vi.fn()
}))

interface HarnessHandle {
  selectModel: ReturnType<typeof useModelControls>['selectModel']
}

function Harness({
  activeSessionId,
  onReady,
  queryClient,
  requestGateway
}: {
  activeSessionId: string | null
  onReady: (handle: HarnessHandle) => void
  queryClient: QueryClient
  requestGateway: <T = unknown>(method: string, params?: Record<string, unknown>) => Promise<T>
}) {
  const controls = useModelControls({ activeSessionId, queryClient, requestGateway })

  useEffect(() => {
    onReady({ selectModel: controls.selectModel })
  }, [controls.selectModel, onReady])

  return null
}

describe('useModelControls', () => {
  beforeEach(() => {
    $activeSessionId.set(null)
    setCurrentModel('old-model')
    setCurrentProvider('old-provider')
    vi.mocked(getGlobalModelInfo).mockResolvedValue({ model: 'global-model', provider: 'global-provider' })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
    $activeSessionId.set(null)
    setCurrentModel('')
    setCurrentProvider('')
  })

  it('applies the global model when there is no active runtime session', async () => {
    vi.mocked(getGlobalModelInfo).mockResolvedValue({
      model: 'openai/gpt-5.5',
      provider: 'openai-codex'
    })

    const { result } = renderHook(() =>
      useModelControls({
        activeSessionId: null,
        queryClient: new QueryClient(),
        requestGateway: vi.fn()
      })
    )

    await result.current.refreshCurrentModel()

    expect($currentModel.get()).toBe('openai/gpt-5.5')
    expect($currentProvider.get()).toBe('openai-codex')
  })

  it('does not clobber the active session footer state with global model info', async () => {
    setCurrentModel('deepseek/deepseek-v4-pro')
    setCurrentProvider('deepseek')
    $activeSessionId.set('runtime-1')
    vi.mocked(getGlobalModelInfo).mockResolvedValue({
      model: 'openai/gpt-5.5',
      provider: 'openai-codex'
    })

    const { result } = renderHook(() =>
      useModelControls({
        activeSessionId: 'runtime-1',
        queryClient: new QueryClient(),
        requestGateway: vi.fn()
      })
    )

    await result.current.refreshCurrentModel()

    expect($currentModel.get()).toBe('deepseek/deepseek-v4-pro')
    expect($currentProvider.get()).toBe('deepseek')
  })

  it('switches an active desktop session through config.set instead of the slash worker', async () => {
    const queryClient = new QueryClient()
    const requestGateway = vi.fn(async () => ({ value: 'new-model', warning: '' }) as never)
    let handle: HarnessHandle | null = null

    render(
      <Harness
        activeSessionId="session-123"
        onReady={h => (handle = h)}
        queryClient={queryClient}
        requestGateway={requestGateway}
      />
    )

    await waitFor(() => expect(handle).not.toBeNull())
    const ok = await handle!.selectModel({ model: 'new-model', persistGlobal: false, provider: 'openrouter' })

    expect(ok).toBe(true)
    expect(requestGateway).toHaveBeenCalledWith('config.set', {
      confirm_expensive_model: true,
      key: 'model',
      session_id: 'session-123',
      value: 'new-model --provider openrouter'
    })
    expect(requestGateway).not.toHaveBeenCalledWith('slash.exec', expect.anything())
    expect($currentModel.get()).toBe('new-model')
    expect($currentProvider.get()).toBe('openrouter')
  })

  it('passes --global through config.set when an active-session switch should persist globally', async () => {
    const queryClient = new QueryClient()
    const requestGateway = vi.fn(async () => ({ value: 'new-model', warning: '' }) as never)
    let handle: HarnessHandle | null = null

    render(
      <Harness
        activeSessionId="session-123"
        onReady={h => (handle = h)}
        queryClient={queryClient}
        requestGateway={requestGateway}
      />
    )

    await waitFor(() => expect(handle).not.toBeNull())
    await handle!.selectModel({ model: 'new-model', persistGlobal: true, provider: 'openrouter' })

    expect(requestGateway).toHaveBeenCalledWith('config.set', {
      confirm_expensive_model: true,
      key: 'model',
      session_id: 'session-123',
      value: 'new-model --provider openrouter --global'
    })
  })
})
