import { QueryClient } from '@tanstack/react-query'
import { renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { I18nProvider } from '@/i18n'
import { $notifications, clearNotifications } from '@/store/notifications'
import { $currentModel, $currentProvider, setCurrentModel, setCurrentProvider } from '@/store/session'

import { useModelControls } from './use-model-controls'

function wrapper({ children }: { children: ReactNode }) {
  return <I18nProvider initialLocale="en">{children}</I18nProvider>
}

function setup(requestGateway: (method: string, params?: Record<string, unknown>) => Promise<unknown>) {
  const queryClient = new QueryClient()

  return renderHook(
    () =>
      useModelControls({
        activeSessionId: 'sid-1',
        queryClient,
        requestGateway: requestGateway as <T>(method: string, params?: Record<string, unknown>) => Promise<T>
      }),
    { wrapper }
  ).result
}

describe('useModelControls.selectModel', () => {
  afterEach(() => {
    clearNotifications()
    vi.restoreAllMocks()
  })

  it('rolls back and notifies when slash.exec resolves with a structured error', async () => {
    setCurrentModel('opus-prev')
    setCurrentProvider('anthropic')

    // slash.exec RESOLVES _ok even when the backend rejected the live switch —
    // the failure rides in `result.error`, not a promise rejection.
    const requestGateway = vi.fn().mockResolvedValue({
      output: "  ✗ Model 'bad/model' not available",
      warning: 'live session sync failed: model switch failed',
      error: 'live session sync failed: model switch failed'
    })

    const result = setup(requestGateway)
    const ok = await result.current.selectModel({ model: 'bad/model', provider: 'anthropic', persistGlobal: false })

    expect(ok).toBe(false)
    // The optimistic model is restored — the UI must not sit on a model the
    // backend never selected.
    expect($currentModel.get()).toBe('opus-prev')
    expect($currentProvider.get()).toBe('anthropic')
    // ...and the user sees why.
    const notes = $notifications.get()
    expect(notes[0]?.kind).toBe('error')
    expect(notes[0]?.message).toContain('live session sync failed')
  })

  it('keeps the new model when slash.exec resolves cleanly', async () => {
    setCurrentModel('opus-prev')
    setCurrentProvider('anthropic')

    const requestGateway = vi.fn().mockResolvedValue({ output: '  ✓ Model switched: new/model' })

    const result = setup(requestGateway)
    const ok = await result.current.selectModel({ model: 'new/model', provider: 'openai', persistGlobal: false })

    expect(ok).toBe(true)
    expect($currentModel.get()).toBe('new/model')
    expect($currentProvider.get()).toBe('openai')
    expect($notifications.get()).toHaveLength(0)
  })
})
