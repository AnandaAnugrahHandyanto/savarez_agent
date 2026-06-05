import { cleanup, render } from '@testing-library/react'
import type { MutableRefObject } from 'react'
import { useEffect } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { $sessions, setConnection, setSessions } from '@/store/session'
import type { ComposerAttachment } from '@/store/composer'
import type { SessionInfo } from '@/types/hermes'

import { usePromptActions } from './use-prompt-actions'

vi.mock('@/hermes', () => ({
  getProfiles: vi.fn(async () => ({ profiles: [] })),
  setApiRequestProfile: vi.fn(),
  transcribeAudio: vi.fn()
}))

// The active id the desktop holds is the *runtime* session id from
// session.create — deliberately distinct from the stored DB id here, because
// that mismatch is the bug: the REST renameSession endpoint resolves against
// the stored sessions table and 404s on a runtime id. session.title accepts
// the runtime id directly.
const RUNTIME_SESSION_ID = 'rt-abc123'

function sessionInfo(overrides: Partial<SessionInfo> = {}): SessionInfo {
  return {
    ended_at: null,
    id: RUNTIME_SESSION_ID,
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
  submitText: (text: string, options?: { attachments?: ComposerAttachment[] }) => Promise<boolean>
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
  const activeSessionIdRef: MutableRefObject<string | null> = { current: RUNTIME_SESSION_ID }
  const selectedStoredSessionIdRef: MutableRefObject<string | null> = { current: RUNTIME_SESSION_ID }
  const busyRef = { current: false }

  const actions = usePromptActions({
    activeSessionId: RUNTIME_SESSION_ID,
    activeSessionIdRef,
    branchCurrentSession: async () => true,
    busyRef,
    createBackendSessionForSend: async () => RUNTIME_SESSION_ID,
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

function setRemoteConnection() {
  setConnection({
    authMode: 'token',
    baseUrl: 'https://remote.example',
    isFullscreen: false,
    logs: [],
    mode: 'remote',
    nativeOverlayWidth: 0,
    source: 'settings',
    token: 'redacted',
    windowButtonPosition: null,
    wsUrl: 'wss://remote.example/ws'
  })
}

function localTextAttachment(overrides: Partial<ComposerAttachment> = {}): ComposerAttachment {
  return {
    id: 'file:/Users/mark/Desktop/note.txt',
    kind: 'file',
    label: 'note.txt',
    localPath: '/Users/mark/Desktop/note.txt',
    path: '/Users/mark/Desktop/note.txt',
    refText: '@file:/Users/mark/Desktop/note.txt',
    ...overrides
  }
}

describe('usePromptActions /title', () => {
  beforeEach(() => {
    setSessions(() => [sessionInfo()])
  })

  afterEach(() => {
    cleanup()
    setConnection(null)
    vi.restoreAllMocks()
  })

  it('renames via the session.title RPC (with the runtime id), updates the sidebar store, and refreshes', async () => {
    const refreshSessions = vi.fn(async () => undefined)
    const requestGateway = vi.fn(async (method: string) =>
      (method === 'session.title' ? { pending: false, title: 'New title' } : {}) as never
    )

    let handle: HarnessHandle | null = null
    render(<Harness onReady={h => (handle = h)} refreshSessions={refreshSessions} requestGateway={requestGateway} />)

    await handle!.submitText('/title New title')

    // Routes through session.title with the runtime session id — NOT the slash
    // worker (slash.exec) and NOT the REST endpoint. This is the path that
    // resolves the runtime id and persists reliably across platforms.
    expect(requestGateway).toHaveBeenCalledWith('session.title', {
      session_id: RUNTIME_SESSION_ID,
      title: 'New title'
    })
    expect(requestGateway).not.toHaveBeenCalledWith('slash.exec', expect.anything())
    expect(refreshSessions).toHaveBeenCalledTimes(1)
    expect($sessions.get()[0]?.title).toBe('New title')
  })

  it('reports the queued state when the session row is not persisted yet', async () => {
    const refreshSessions = vi.fn(async () => undefined)
    const requestGateway = vi.fn(async (method: string) =>
      (method === 'session.title' ? { pending: true, title: 'Fresh chat' } : {}) as never
    )

    let handle: HarnessHandle | null = null
    render(<Harness onReady={h => (handle = h)} refreshSessions={refreshSessions} requestGateway={requestGateway} />)

    await handle!.submitText('/title Fresh chat')

    expect(requestGateway).toHaveBeenCalledWith('session.title', {
      session_id: RUNTIME_SESSION_ID,
      title: 'Fresh chat'
    })
    // Even when queued, the sidebar reflects the chosen title optimistically.
    expect(refreshSessions).toHaveBeenCalledTimes(1)
    expect($sessions.get()[0]?.title).toBe('Fresh chat')
  })

  it('falls through to the slash worker for a bare /title (show current title)', async () => {
    const refreshSessions = vi.fn(async () => undefined)
    const requestGateway = vi.fn(async () => ({ output: 'Title: Old title' }) as never)

    let handle: HarnessHandle | null = null
    render(<Harness onReady={h => (handle = h)} refreshSessions={refreshSessions} requestGateway={requestGateway} />)

    await handle!.submitText('/title')

    expect(requestGateway).not.toHaveBeenCalledWith('session.title', expect.anything())
    expect(requestGateway).toHaveBeenCalledWith('slash.exec', expect.objectContaining({ command: 'title' }))
  })

  it('surfaces a rename error without touching the sidebar store', async () => {
    const refreshSessions = vi.fn(async () => undefined)
    const requestGateway = vi.fn(async (method: string) => {
      if (method === 'session.title') {
        throw new Error('Title too long')
      }

      return {} as never
    })

    let handle: HarnessHandle | null = null
    render(<Harness onReady={h => (handle = h)} refreshSessions={refreshSessions} requestGateway={requestGateway} />)

    await handle!.submitText('/title way too long title')

    expect(requestGateway).toHaveBeenCalledWith('session.title', expect.objectContaining({ title: 'way too long title' }))
    expect(refreshSessions).not.toHaveBeenCalled()
    expect($sessions.get()[0]?.title).toBe('Old title')
  })
})

describe('usePromptActions remote local attachments', () => {
  afterEach(() => {
    cleanup()
    setConnection(null)
    vi.restoreAllMocks()
  })

  it('inlines Desktop-local text attachments before submitting to a remote backend', async () => {
    setRemoteConnection()

    const readFileText = vi.fn(async () => ({
      binary: false,
      byteSize: 22,
      language: 'markdown',
      mimeType: 'text/markdown',
      path: '/Users/mark/Desktop/note.txt',
      text: '# Note\nhello remote',
      truncated: false
    }))
    Object.defineProperty(window, 'hermesDesktop', {
      configurable: true,
      value: { readFileText }
    })

    const refreshSessions = vi.fn(async () => undefined)
    const requestGateway = vi.fn(async () => ({}) as never)

    let handle: HarnessHandle | null = null
    render(<Harness onReady={h => (handle = h)} refreshSessions={refreshSessions} requestGateway={requestGateway} />)

    const submitted = await handle!.submitText('review this', { attachments: [localTextAttachment()] })

    expect(submitted).toBe(true)
    expect(readFileText).toHaveBeenCalledWith('/Users/mark/Desktop/note.txt')
    expect(requestGateway).toHaveBeenCalledWith(
      'prompt.submit',
      expect.objectContaining({
        session_id: RUNTIME_SESSION_ID,
        text: expect.stringContaining('Attached local file: note.txt')
      })
    )
    const promptSubmit = requestGateway.mock.calls
      .map(call => call as unknown[])
      .find(call => call[0] === 'prompt.submit')?.[1] as { text: string } | undefined
    if (!promptSubmit) {
      throw new Error('prompt.submit call missing')
    }
    expect(promptSubmit.text).toContain('```markdown\n# Note\nhello remote\n```')
    expect(promptSubmit.text).toContain('review this')
    expect(promptSubmit.text).not.toContain('@file:/Users/mark/Desktop/note.txt')
  })

  it('fails visibly instead of sending an unreadable remote @file for binary local files', async () => {
    setRemoteConnection()

    Object.defineProperty(window, 'hermesDesktop', {
      configurable: true,
      value: {
        readFileText: vi.fn(async () => ({
          binary: true,
          byteSize: 12,
          language: 'text',
          mimeType: 'application/octet-stream',
          path: '/Users/mark/Desktop/blob.bin',
          text: '',
          truncated: false
        }))
      }
    })

    const refreshSessions = vi.fn(async () => undefined)
    const requestGateway = vi.fn(async () => ({}) as never)

    let handle: HarnessHandle | null = null
    render(<Harness onReady={h => (handle = h)} refreshSessions={refreshSessions} requestGateway={requestGateway} />)

    const submitted = await handle!.submitText('review this', {
      attachments: [localTextAttachment({ label: 'blob.bin', localPath: '/Users/mark/Desktop/blob.bin' })]
    })

    expect(submitted).toBe(false)
    expect(requestGateway).not.toHaveBeenCalledWith('prompt.submit', expect.anything())
  })
})
