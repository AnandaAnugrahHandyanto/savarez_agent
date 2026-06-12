import { QueryClient } from '@tanstack/react-query'
import { act, cleanup, render } from '@testing-library/react'
import { useEffect, useRef } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ClientSessionState } from '@/app/types'
import { createClientSessionState } from '@/lib/chat-runtime'
import { $selectedStoredSessionId } from '@/store/session'
import type { RpcEvent } from '@/types/hermes'

import { useMessageStream } from './use-message-stream'

let handleEvent: (event: RpcEvent) => void = () => undefined
let updateCalls: Array<{ sessionId: string; storedSessionId?: null | string }> = []

function MessageStreamHarness({ activeSessionId = 'session-1' }: { activeSessionId?: string }) {
  const activeSessionIdRef = useRef<string | null>(activeSessionId)
  const queryClientRef = useRef(new QueryClient())
  const statesRef = useRef(new Map<string, ClientSessionState>())

  const stream = useMessageStream({
    activeSessionIdRef,
    hydrateFromStoredSession: vi.fn(async () => undefined),
    queryClient: queryClientRef.current,
    refreshHermesConfig: vi.fn(async () => undefined),
    refreshSessions: vi.fn(async () => undefined),
    updateSessionState: (sessionId, updater, storedSessionId) => {
      const previous = statesRef.current.get(sessionId) ?? createClientSessionState(null)
      const state = storedSessionId === undefined ? previous : { ...previous, storedSessionId }
      const next = updater(state)
      statesRef.current.set(sessionId, next)
      updateCalls.push({ sessionId, storedSessionId })

      return next
    }
  })

  useEffect(() => {
    handleEvent = stream.handleGatewayEvent
  }, [stream.handleGatewayEvent])

  return null
}

describe('useMessageStream session.info events', () => {
  beforeEach(() => {
    handleEvent = () => undefined
    updateCalls = []
    $selectedStoredSessionId.set(null)
  })

  afterEach(() => {
    cleanup()
    $selectedStoredSessionId.set(null)
    vi.restoreAllMocks()
  })

  it('rebinds active session state to the live session_key from the backend', () => {
    $selectedStoredSessionId.set('parent')
    render(<MessageStreamHarness activeSessionId="runtime" />)

    act(() =>
      handleEvent({
        payload: {
          running: true,
          session_key: 'continuation'
        },
        session_id: 'runtime',
        type: 'session.info'
      } as RpcEvent)
    )

    expect($selectedStoredSessionId.get()).toBe('continuation')
    expect(updateCalls).toEqual([
      { sessionId: 'runtime', storedSessionId: 'continuation' },
      { sessionId: 'runtime', storedSessionId: 'continuation' }
    ])
  })
})
