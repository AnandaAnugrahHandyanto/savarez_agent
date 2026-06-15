import { QueryClient } from '@tanstack/react-query'
import { renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createClientSessionState } from '@/lib/chat-runtime'

import { useMessageStream } from './use-message-stream'

vi.mock('@/i18n', () => ({
  translateNow: vi.fn((key: string) => key)
}))

vi.mock('@/store/native-notifications', () => ({
  dispatchNativeNotification: vi.fn()
}))

vi.mock('@/lib/completion-sound', () => ({
  playCompletionSound: vi.fn()
}))

describe('useMessageStream', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  function setupSessionState() {
    const sessionId = 'runtime-1'
    const stateById = new Map([[sessionId, createClientSessionState('stored-1')]])
    const sessionStateByRuntimeIdRef = {
      current: stateById
    }

    const updateSessionState = vi.fn((targetSessionId: string, updater: (state: ReturnType<typeof createClientSessionState>) => ReturnType<typeof createClientSessionState>) => {
      const current = stateById.get(targetSessionId) ?? createClientSessionState(null)
      const next = updater(current)
      stateById.set(targetSessionId, next)
      return next
    })

    return { sessionId, stateById, sessionStateByRuntimeIdRef, updateSessionState }
  }

  it('keeps message.complete status=error as an inline error and skips hydrate fallback', () => {
    const hydrateFromStoredSession = vi.fn(async () => undefined)
    const refreshSessions = vi.fn(async () => undefined)
    const refreshHermesConfig = vi.fn(async () => undefined)
    const { sessionId, stateById, sessionStateByRuntimeIdRef, updateSessionState } = setupSessionState()

    const { result } = renderHook(() =>
      useMessageStream({
        activeSessionIdRef: { current: sessionId },
        hydrateFromStoredSession,
        queryClient: new QueryClient(),
        refreshHermesConfig,
        refreshSessions,
        sessionStateByRuntimeIdRef,
        updateSessionState
      })
    )

    result.current.completeAssistantMessage(sessionId, 'Error: HTTP 400: The requested model is not supported.', {
      status: 'error'
    })

    expect(hydrateFromStoredSession).not.toHaveBeenCalled()
    expect(refreshSessions).toHaveBeenCalled()
    expect(stateById.get(sessionId)?.messages).toEqual([
      expect.objectContaining({
        role: 'assistant',
        error: 'Error: HTTP 400: The requested model is not supported.'
      })
    ])
  })

  it('still hydrates normal completions when no assistant payload was streamed', () => {
    const hydrateFromStoredSession = vi.fn(async () => undefined)
    const refreshSessions = vi.fn(async () => undefined)
    const refreshHermesConfig = vi.fn(async () => undefined)
    const { sessionId, sessionStateByRuntimeIdRef, updateSessionState } = setupSessionState()

    const { result } = renderHook(() =>
      useMessageStream({
        activeSessionIdRef: { current: sessionId },
        hydrateFromStoredSession,
        queryClient: new QueryClient(),
        refreshHermesConfig,
        refreshSessions,
        sessionStateByRuntimeIdRef,
        updateSessionState
      })
    )

    result.current.completeAssistantMessage(sessionId, 'Normal assistant reply.', {
      status: 'complete'
    })

    expect(hydrateFromStoredSession).toHaveBeenCalledWith(3, 'stored-1', sessionId)
  })
})
