import { cleanup, render, waitFor } from '@testing-library/react'
import type { MutableRefObject } from 'react'
import { useEffect } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { chatMessageText, textPart } from '@/lib/chat-messages'
import { $activeGatewayProfile, $newChatProfile } from '@/store/profile'
import { $currentCwd } from '@/store/session'

import type { ClientSessionState } from '../../types'

import { mergeResumeInflightMessages, useSessionActions } from './use-session-actions'

vi.mock('@/hermes', async importOriginal => ({
  ...(await importOriginal<Record<string, unknown>>()),
  deleteSession: vi.fn(),
  getSessionMessages: vi.fn(),
  listAllProfileSessions: vi.fn(),
  setApiRequestProfile: vi.fn(),
  setSessionArchived: vi.fn()
}))

const RUNTIME_SESSION_ID = 'rt-new-001'

function Harness({
  onReady,
  requestGateway
}: {
  onReady: (create: (preview?: string | null) => Promise<string | null>) => void
  requestGateway: <T>(method: string, params?: Record<string, unknown>) => Promise<T>
}) {
  const ref = <T,>(value: T): MutableRefObject<T> => ({ current: value })

  const actions = useSessionActions({
    activeSessionId: null,
    activeSessionIdRef: ref<string | null>(null),
    busyRef: ref(false),
    creatingSessionRef: ref(false),
    ensureSessionState: () => ({}) as ClientSessionState,
    getRouteToken: () => 'token',
    navigate: vi.fn() as never,
    requestGateway,
    runtimeIdByStoredSessionIdRef: ref(new Map<string, string>()),
    selectedStoredSessionId: null,
    selectedStoredSessionIdRef: ref<string | null>(null),
    sessionStateByRuntimeIdRef: ref(new Map<string, ClientSessionState>()),
    syncSessionStateToView: vi.fn(),
    updateSessionState: () => ({}) as ClientSessionState
  })

  useEffect(() => {
    onReady(actions.createBackendSessionForSend)
  }, [actions.createBackendSessionForSend, onReady])

  return null
}

async function createWith(profileSetup: () => void): Promise<Record<string, unknown> | undefined> {
  let createParams: Record<string, unknown> | undefined

  const requestGateway = vi.fn(async (method: string, params?: Record<string, unknown>) => {
    if (method === 'session.create') {
      createParams = params

      return { session_id: RUNTIME_SESSION_ID, stored_session_id: null } as never
    }

    return {} as never
  })

  $currentCwd.set('')
  profileSetup()

  let create: ((preview?: string | null) => Promise<string | null>) | null = null
  render(<Harness onReady={c => (create = c)} requestGateway={requestGateway} />)
  await waitFor(() => expect(create).not.toBeNull())
  await create!()

  return createParams
}

describe('mergeResumeInflightMessages', () => {
  it('replays an active inflight turn as a pending assistant stream', () => {
    const merged = mergeResumeInflightMessages(
      [],
      [
        { id: 'local-user', role: 'user', parts: [textPart('question')] },
        { id: 'local-assistant', role: 'assistant', parts: [textPart('partial answer')], pending: true }
      ],
      {
        assistant: 'partial answer',
        started_at: 10,
        streaming: true,
        user: 'question'
      },
      true
    )

    expect(merged).not.toBeNull()
    expect(merged!.busy).toBe(true)
    expect(merged!.awaitingResponse).toBe(true)
    expect(merged!.streamId).toBe('local-assistant')
    expect(merged!.turnStartedAt).toBe(10_000)
    expect(merged!.messages).toHaveLength(2)
    expect(merged!.messages[0]?.id).toBe('local-user')
    expect(merged!.messages[1]).toMatchObject({ id: 'local-assistant', pending: true, role: 'assistant' })
    expect(chatMessageText(merged!.messages[1]!)).toBe('partial answer')
  })

  it('replays a failed inflight turn as a settled assistant error with partial text', () => {
    const merged = mergeResumeInflightMessages(
      [{ id: 'stored-user', role: 'user', parts: [textPart('question')] }],
      [],
      {
        assistant: 'partial answer',
        error: 'provider crashed',
        recoverable: true,
        status: 'error',
        streaming: false,
        user: 'question'
      },
      false
    )

    expect(merged).not.toBeNull()
    expect(merged!.busy).toBe(false)
    expect(merged!.awaitingResponse).toBe(false)
    expect(merged!.streamId).toBeNull()
    expect(merged!.messages).toHaveLength(2)
    expect(merged!.messages[1]).toMatchObject({ error: 'provider crashed', pending: false, role: 'assistant' })
    expect(chatMessageText(merged!.messages[1]!)).toBe('partial answer')
  })

  it('does not reuse a stale completed assistant message for a resumed blank stream', () => {
    const merged = mergeResumeInflightMessages(
      [
        { id: 'stored-user', role: 'user', parts: [textPart('old question')] },
        { id: 'stored-assistant', role: 'assistant', parts: [textPart('old answer')] }
      ],
      [
        { id: 'local-user', role: 'user', parts: [textPart('old question')] },
        { id: 'local-assistant', role: 'assistant', parts: [textPart('old answer')] }
      ],
      {
        assistant: '',
        streaming: true,
        user: 'new question'
      },
      true
    )

    expect(merged).not.toBeNull()
    expect(merged!.messages).toHaveLength(4)
    expect(chatMessageText(merged!.messages[0]!)).toBe('old question')
    expect(chatMessageText(merged!.messages[1]!)).toBe('old answer')
    expect(chatMessageText(merged!.messages[2]!)).toBe('new question')
    expect(chatMessageText(merged!.messages[3]!)).toBe('')
    expect(merged!.messages[3]).toMatchObject({ pending: true, role: 'assistant' })
  })
})

describe('createBackendSessionForSend profile routing', () => {
  afterEach(() => {
    cleanup()
    $newChatProfile.set(null)
    $activeGatewayProfile.set('default')
    vi.restoreAllMocks()
  })

  it('routes a plain new chat (no explicit profile) to the live gateway profile', async () => {
    // The "rubberband to default" bug: the top New Session button clears
    // $newChatProfile to null. In global-remote mode one backend serves every
    // profile, so an omitted `profile` lands the chat on the launch (default)
    // profile. The session must instead carry the active gateway profile.
    const params = await createWith(() => {
      $activeGatewayProfile.set('coder')
      $newChatProfile.set(null)
    })

    expect(params).toMatchObject({ profile: 'coder' })
  })

  it('honours an explicit per-profile "+" selection', async () => {
    const params = await createWith(() => {
      $activeGatewayProfile.set('coder')
      $newChatProfile.set('analyst')
    })

    expect(params).toMatchObject({ profile: 'analyst' })
  })

  it('passes the default profile for single-profile users (backend resolves it to launch)', async () => {
    const params = await createWith(() => {
      $activeGatewayProfile.set('default')
      $newChatProfile.set(null)
    })

    expect(params).toMatchObject({ profile: 'default' })
  })
})
