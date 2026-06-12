import { cleanup, render, waitFor } from '@testing-library/react'
import type { MutableRefObject } from 'react'
import { useEffect } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ClientSessionState } from '@/app/types'
import { createClientSessionState } from '@/lib/chat-runtime'
import { $activeGatewayProfile, $newChatProfile } from '@/store/profile'
import { $currentCwd, $selectedStoredSessionId, setSessions } from '@/store/session'
import type { SessionInfo } from '@/types/hermes'

import { useSessionActions } from './use-session-actions'

const ensureGatewayProfile = vi.fn(async (_profile?: string | null) => undefined)
const getSessionMessages = vi.fn(async (_id: string, _profile?: string | null) => ({ messages: [] }))
const deleteSession = vi.fn(async (_id: string) => undefined)
const setSessionArchived = vi.fn(async (_id: string, _archived: boolean, _profile?: string | null) => undefined)

vi.mock('@/store/profile', async importOriginal => {
  const actual = await importOriginal()

  return {
    ...(actual as object),
    ensureGatewayProfile: (profile: string | null | undefined) => ensureGatewayProfile(profile)
  }
})

vi.mock('@/hermes', async importOriginal => {
  const actual = await importOriginal<Record<string, unknown>>()

  return {
    ...actual,
    deleteSession: (id: string) => deleteSession(id),
    getSessionMessages: (id: string, profile?: string | null) => getSessionMessages(id, profile),
    listAllProfileSessions: vi.fn(),
    setApiRequestProfile: vi.fn(),
    setSessionArchived: (id: string, archived: boolean, profile?: string | null) =>
      setSessionArchived(id, archived, profile)
  }
})

const RUNTIME_SESSION_ID = 'rt-new-001'

function sessionInfo(overrides: Partial<SessionInfo> = {}): SessionInfo {
  return {
    ended_at: null,
    id: 'session-a',
    input_tokens: 0,
    is_active: false,
    last_active: 0,
    message_count: 1,
    model: null,
    output_tokens: 0,
    preview: null,
    profile: 'default',
    source: 'tui',
    started_at: 0,
    title: null,
    tool_call_count: 0,
    ...overrides
  }
}

interface HarnessHandle {
  createBackendSessionForSend: (preview?: string | null) => Promise<string | null>
  resumeSession: (storedSessionId: string, replaceRoute?: boolean) => Promise<void>
}

function Harness({
  onReady,
  requestGateway
}: {
  onReady: (handle: HarnessHandle) => void
  requestGateway: <T>(method: string, params?: Record<string, unknown>) => Promise<T>
}) {
  const ref = <T,>(value: T): MutableRefObject<T> => ({ current: value })
  const activeSessionIdRef = ref<string | null>(null)
  const busyRef = ref(false)
  const creatingSessionRef = ref(false)
  const selectedStoredSessionIdRef = ref<string | null>(null)
  const sessionStateByRuntimeIdRef = ref(new Map<string, ClientSessionState>())
  const runtimeIdByStoredSessionIdRef = ref(new Map<string, string>())

  const actions = useSessionActions({
    activeSessionId: null,
    activeSessionIdRef,
    busyRef,
    creatingSessionRef,
    ensureSessionState: (_sessionId, storedSessionId) => createClientSessionState(storedSessionId ?? null),
    getRouteToken: () => 'route',
    navigate: vi.fn() as never,
    requestGateway,
    runtimeIdByStoredSessionIdRef,
    selectedStoredSessionId: null,
    selectedStoredSessionIdRef,
    sessionStateByRuntimeIdRef,
    syncSessionStateToView: vi.fn(),
    updateSessionState: (_sessionId, updater, storedSessionId) =>
      updater(createClientSessionState(storedSessionId ?? null))
  })

  const { createBackendSessionForSend, resumeSession } = actions

  useEffect(() => {
    onReady({ createBackendSessionForSend, resumeSession })
  }, [createBackendSessionForSend, onReady, resumeSession])

  return null
}

describe('useSessionActions resumeSession', () => {
  beforeEach(() => {
    setSessions(() => [
      sessionInfo({ id: 'session-a', profile: 'profile-a' }),
      sessionInfo({ id: 'session-b', profile: 'profile-b' })
    ])
    ensureGatewayProfile.mockReset()
    getSessionMessages.mockReset()
    getSessionMessages.mockResolvedValue({ messages: [] })
    deleteSession.mockReset()
    setSessionArchived.mockReset()
    $selectedStoredSessionId.set(null)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('ignores an older delayed resume so it cannot reselect the wrong sidebar session', async () => {
    let releaseFirstProfile: (() => void) | null = null
    ensureGatewayProfile.mockImplementation(async (profile?: string | null) => {
      if (profile === 'profile-a') {
        await new Promise<void>(resolve => {
          releaseFirstProfile = resolve
        })
      }
    })

    const requestGateway = vi.fn(async (method: string, params?: Record<string, unknown>) => {
      if (method === 'session.resume') {
        return {
          info: {},
          messages: [],
          session_id: `runtime-${params?.session_id}`
        }
      }

      return {}
    })

    let handle: HarnessHandle | null = null
    render(<Harness onReady={h => (handle = h)} requestGateway={requestGateway as never} />)

    const staleResume = handle!.resumeSession('session-a')
    await vi.waitFor(() => expect(releaseFirstProfile).toBeTruthy())

    await handle!.resumeSession('session-b')
    expect($selectedStoredSessionId.get()).toBe('session-b')

    releaseFirstProfile!()
    await staleResume

    expect($selectedStoredSessionId.get()).toBe('session-b')
    expect(requestGateway).toHaveBeenCalledWith('session.resume', expect.objectContaining({ session_id: 'session-b' }))
    expect(requestGateway).not.toHaveBeenCalledWith('session.resume', expect.objectContaining({ session_id: 'session-a' }))
  })
})

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

  let handle: HarnessHandle | null = null
  render(<Harness onReady={h => (handle = h)} requestGateway={requestGateway} />)
  await waitFor(() => expect(handle).not.toBeNull())
  await handle!.createBackendSessionForSend()

  return createParams
}

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
