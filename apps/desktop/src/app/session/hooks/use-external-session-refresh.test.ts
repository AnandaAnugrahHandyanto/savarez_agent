import { describe, expect, it, vi } from 'vitest'

import { type ChatMessage, textPart } from '@/lib/chat-messages'
import type { SessionMessage, SessionMessagesResponse } from '@/types/hermes'

import type { ClientSessionState } from '../../types'

import { refreshExternalSessionSnapshot } from './use-external-session-refresh'

const remoteMessages = (messages: SessionMessage[]): SessionMessagesResponse => ({
  messages,
  session_id: 'stored-1'
})

const clientState = (messages: ChatMessage[], extra: Partial<ClientSessionState> = {}): ClientSessionState =>
  ({
    awaitingResponse: false,
    branch: '',
    busy: false,
    cwd: '',
    interrupted: false,
    messages,
    pendingBranchGroup: null,
    sawAssistantPayload: false,
    storedSessionId: 'stored-1',
    streamId: null,
    ...extra
  }) as ClientSessionState

describe('refreshExternalSessionSnapshot', () => {
  it('hydrates the active desktop session when stored messages change outside the app', async () => {
    const local = clientState([
      {
        id: 'local-user-1',
        parts: [textPart('old')],
        role: 'user',
        timestamp: 1
      }
    ])

    const getRuntimeState = vi.fn(() => local)

    const getSessionMessages = vi.fn(async () =>
      remoteMessages([
        { content: 'old', role: 'user', timestamp: 1 },
        { content: 'phone update', role: 'user', timestamp: 2 }
      ])
    )

    const refreshSessions = vi.fn(async () => undefined)

    const updateSessionState = vi.fn((sessionId, updater, storedSessionId) => {
      const next = updater(local)

      return { sessionId, state: next, storedSessionId }
    })

    const refreshed = await refreshExternalSessionSnapshot({
      getRuntimeState,
      getSessionMessages,
      lastRemoteRevision: new Map(),
      refreshSessions,
      runtimeSessionId: 'runtime-1',
      storedSessionId: 'stored-1',
      updateSessionState
    })

    expect(refreshed).toBe(true)
    expect(updateSessionState).toHaveBeenCalledTimes(1)

    const [runtimeId, updater, storedId] = updateSessionState.mock.calls[0] as [
      string,
      (state: ClientSessionState) => ClientSessionState,
      string
    ]

    const hydrated = updater(local)
    expect(runtimeId).toBe('runtime-1')
    expect(storedId).toBe('stored-1')
    expect(hydrated.messages.map((message: ChatMessage) => message.role)).toEqual(['user', 'user'])
    expect(hydrated.messages.at(-1)?.parts).toEqual([textPart('phone update')])
    expect(refreshSessions).toHaveBeenCalledTimes(1)
  })

  it('does not rehydrate unchanged revisions on each poll tick', async () => {
    const local = clientState([
      {
        id: 'local-user-1',
        parts: [textPart('same')],
        role: 'user',
        timestamp: 1
      }
    ])

    const lastRemoteRevision = new Map<string, string>([['stored-1', '1:user:1:same']])
    const getSessionMessages = vi.fn(async () => remoteMessages([{ content: 'same', role: 'user', timestamp: 1 }]))

    const updateSessionState = vi.fn((sessionId, updater, storedSessionId) => ({
      sessionId,
      state: updater(local),
      storedSessionId
    }))

    const refreshed = await refreshExternalSessionSnapshot({
      getRuntimeState: () => local,
      getSessionMessages,
      lastRemoteRevision,
      refreshSessions: vi.fn(async () => undefined),
      runtimeSessionId: 'runtime-1',
      storedSessionId: 'stored-1',
      updateSessionState
    })

    expect(refreshed).toBe(false)
    expect(getSessionMessages).toHaveBeenCalled()
    expect(updateSessionState).not.toHaveBeenCalled()
  })

  it('does not repeatedly rehydrate when the remote revision is unchanged after an initial repair', async () => {
    const local = clientState([])
    const lastRemoteRevision = new Map<string, string>()
    const getSessionMessages = vi.fn(async () => remoteMessages([{ content: 'phone update', role: 'user', timestamp: 2 }]))
    const refreshSessions = vi.fn(async () => undefined)

    const updateSessionState = vi.fn((sessionId, updater, storedSessionId) => ({
      sessionId,
      state: updater(local),
      storedSessionId
    }))

    const options = {
      getRuntimeState: () => local,
      getSessionMessages,
      lastRemoteRevision,
      refreshSessions,
      runtimeSessionId: 'runtime-1',
      storedSessionId: 'stored-1',
      updateSessionState
    }

    await expect(refreshExternalSessionSnapshot(options)).resolves.toBe(true)
    await expect(refreshExternalSessionSnapshot(options)).resolves.toBe(false)

    expect(updateSessionState).toHaveBeenCalledTimes(1)
    expect(refreshSessions).toHaveBeenCalledTimes(1)
  })

  it('does not overwrite a session that becomes busy while refresh is in flight', async () => {
    const idle = clientState([
      {
        id: 'local-user-1',
        parts: [textPart('old')],
        role: 'user',
        timestamp: 1
      }
    ])

    const busy = clientState([
      ...idle.messages,
      {
        id: 'optimistic-user-2',
        parts: [textPart('new prompt')],
        role: 'user',
        timestamp: 2
      }
    ], { awaitingResponse: true })

    let runtimeState = idle

    const getSessionMessages = vi.fn(async () => {
      runtimeState = busy

      return remoteMessages([
        { content: 'old', role: 'user', timestamp: 1 },
        { content: 'phone update', role: 'user', timestamp: 2 }
      ])
    })

    const updateSessionState = vi.fn()

    const refreshed = await refreshExternalSessionSnapshot({
      getRuntimeState: () => runtimeState,
      getSessionMessages,
      lastRemoteRevision: new Map(),
      refreshSessions: vi.fn(async () => undefined),
      runtimeSessionId: 'runtime-1',
      storedSessionId: 'stored-1',
      updateSessionState
    })

    expect(refreshed).toBe(false)
    expect(updateSessionState).not.toHaveBeenCalled()
  })

  it('skips polling while the active session is busy', async () => {
    const local = clientState([], { busy: true })
    const getSessionMessages = vi.fn(async () => remoteMessages([{ content: 'busy update', role: 'user', timestamp: 1 }]))

    const refreshed = await refreshExternalSessionSnapshot({
      getRuntimeState: () => local,
      getSessionMessages,
      lastRemoteRevision: new Map(),
      refreshSessions: vi.fn(async () => undefined),
      runtimeSessionId: 'runtime-1',
      storedSessionId: 'stored-1',
      updateSessionState: vi.fn()
    })

    expect(refreshed).toBe(false)
    expect(getSessionMessages).not.toHaveBeenCalled()
  })
})
