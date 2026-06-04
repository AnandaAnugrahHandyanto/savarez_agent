import { cleanup, render } from '@testing-library/react'
import type { MutableRefObject } from 'react'
import { useEffect } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { $sessions, setSessions } from '@/store/session'
import type { SessionInfo } from '@/types/hermes'

import { usePromptActions } from './use-prompt-actions'

const renameSession = vi.fn<(id: string, title: string) => Promise<{ ok: boolean; title: string }>>()

vi.mock('@/hermes', () => ({
  renameSession: (id: string, title: string) => renameSession(id, title),
  transcribeAudio: vi.fn()
}))

function sessionInfo(overrides: Partial<SessionInfo> = {}): SessionInfo {
  return {
    ended_at: null,
    id: 'session-1',
    input_tokens: 0,
    is_active: true,
    last_active: 0,
    message_count: 3,
    model: null,
    output_tokens: 0,
    preview: null,
    source: null,
    started_at: 0,
    title: 'Old title',
    tool_call_count: 0,
    ...overrides
  }
}

interface HarnessHandle {
  submitText: (text: string) => Promise<boolean>
}

function Harness({
  onReady,
  refreshSessions,
  requestGateway
}: {
  onReady: (handle: HarnessHandle) => void
  refreshSessions: () => Promise<void>
  requestGateway: <T>(method: string, params?: Record<string, unknown>) => Promise<T>
}) {
  const activeSessionIdRef: MutableRefObject<string | null> = { current: 'session-1' }
  const selectedStoredSessionIdRef: MutableRefObject<string | null> = { current: 'session-1' }
  const busyRef = { current: false }

  const actions = usePromptActions({
    activeSessionId: 'session-1',
    activeSessionIdRef,
    branchCurrentSession: async () => true,
    busyRef,
    createBackendSessionForSend: async () => 'session-1',
    handleSkinCommand: () => '',
    refreshSessions,
    requestGateway,
    selectedStoredSessionIdRef,
    startFreshSessionDraft: () => undefined,
    sttEnabled: false,
    updateSessionState: (_sessionId, updater) =>
      updater({ messages: [], busy: false, awaitingResponse: false } as never)
  })

  useEffect(() => {
    onReady({ submitText: actions.submitText })
  }, [actions.submitText, onReady])

  return null
}

describe('usePromptActions /title', () => {
  beforeEach(() => {
    renameSession.mockReset()
    setSessions(() => [sessionInfo()])
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renames via the REST endpoint, updates the sidebar store, and refreshes', async () => {
    renameSession.mockResolvedValue({ ok: true, title: 'New title' })
    const refreshSessions = vi.fn(async () => undefined)
    const requestGateway = vi.fn(async () => ({}) as never)

    let handle: HarnessHandle | null = null
    render(<Harness onReady={h => (handle = h)} refreshSessions={refreshSessions} requestGateway={requestGateway} />)

    await handle!.submitText('/title New title')

    expect(renameSession).toHaveBeenCalledWith('session-1', 'New title')
    // Must NOT go through the slash worker (the path that fails to persist /
    // refresh on Windows).
    expect(requestGateway).not.toHaveBeenCalled()
    expect(refreshSessions).toHaveBeenCalledTimes(1)
    expect($sessions.get()[0]?.title).toBe('New title')
  })

  it('falls through to the slash worker for a bare /title (show current title)', async () => {
    const refreshSessions = vi.fn(async () => undefined)
    const requestGateway = vi.fn(async () => ({ output: 'Title: Old title' }) as never)

    let handle: HarnessHandle | null = null
    render(<Harness onReady={h => (handle = h)} refreshSessions={refreshSessions} requestGateway={requestGateway} />)

    await handle!.submitText('/title')

    expect(renameSession).not.toHaveBeenCalled()
    expect(requestGateway).toHaveBeenCalledWith('slash.exec', expect.objectContaining({ command: 'title' }))
  })

  it('surfaces a rename error without touching the sidebar store', async () => {
    renameSession.mockRejectedValue(new Error('Title too long'))
    const refreshSessions = vi.fn(async () => undefined)
    const requestGateway = vi.fn(async () => ({}) as never)

    let handle: HarnessHandle | null = null
    render(<Harness onReady={h => (handle = h)} refreshSessions={refreshSessions} requestGateway={requestGateway} />)

    await handle!.submitText('/title way too long title')

    expect(renameSession).toHaveBeenCalledTimes(1)
    expect(refreshSessions).not.toHaveBeenCalled()
    expect($sessions.get()[0]?.title).toBe('Old title')
  })
})
