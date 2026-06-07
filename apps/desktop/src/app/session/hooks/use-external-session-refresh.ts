import { useEffect, useRef } from 'react'

import { getSessionMessages as fetchSessionMessages } from '@/hermes'
import {
  type ChatMessage,
  chatMessageText,
  preserveLocalAssistantErrors,
  toChatMessages
} from '@/lib/chat-messages'
import type { SessionMessage, SessionMessagesResponse } from '@/types/hermes'

import type { ClientSessionState } from '../../types'

const DEFAULT_EXTERNAL_SESSION_REFRESH_MS = 4_000
const MIN_EXTERNAL_SESSION_REFRESH_MS = 1_000

interface ExternalSessionRefreshCallbacks {
  getRuntimeState: (runtimeSessionId: string) => ClientSessionState | undefined
  getSessionMessages: (storedSessionId: string) => Promise<SessionMessagesResponse>
  refreshSessions: () => Promise<void>
  updateSessionState: (
    sessionId: string,
    updater: (state: ClientSessionState) => ClientSessionState,
    storedSessionId?: null | string
  ) => ClientSessionState | unknown
}

interface ExternalSessionRefreshOptions extends Omit<ExternalSessionRefreshCallbacks, 'getSessionMessages'> {
  activeSessionId: null | string
  gatewayState: string
  getSessionMessages?: (storedSessionId: string) => Promise<SessionMessagesResponse>
  pollMs?: number
  selectedStoredSessionId: null | string
}

interface RefreshExternalSessionSnapshotOptions extends ExternalSessionRefreshCallbacks {
  lastRemoteRevision: Map<string, string>
  runtimeSessionId: string
  storedSessionId: string
}

function safeContent(value: unknown): string {
  if (typeof value === 'string') {
    return value
  }

  if (value === null || value === undefined) {
    return ''
  }

  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

export function sessionMessageRevision(messages: readonly SessionMessage[]): string {
  const last = messages.at(-1)

  if (!last) {
    return '0'
  }

  return [messages.length, last.role, last.timestamp ?? '', safeContent(last.content ?? last.text)].join(':')
}

export function chatMessageRevision(messages: readonly ChatMessage[]): string {
  const last = messages.at(-1)

  if (!last) {
    return '0'
  }

  return [messages.length, last.role, last.timestamp ?? '', chatMessageText(last)].join(':')
}

export async function refreshExternalSessionSnapshot({
  getRuntimeState,
  getSessionMessages,
  lastRemoteRevision,
  refreshSessions,
  runtimeSessionId,
  storedSessionId,
  updateSessionState
}: RefreshExternalSessionSnapshotOptions): Promise<boolean> {
  const state = getRuntimeState(runtimeSessionId)

  // Local sends already drive their own live stream. Do not fight the active
  // run by replacing messages with the persisted snapshot mid-turn.
  if (state?.busy || state?.awaitingResponse) {
    return false
  }

  const latest = await getSessionMessages(storedSessionId)
  const stateAfterRead = getRuntimeState(runtimeSessionId)

  if (stateAfterRead?.busy || stateAfterRead?.awaitingResponse) {
    return false
  }

  const remoteRevision = sessionMessageRevision(latest.messages)
  const localRevision = stateAfterRead ? chatMessageRevision(stateAfterRead.messages) : null
  const previousRemoteRevision = lastRemoteRevision.get(storedSessionId)
  const firstSeen = previousRemoteRevision === undefined

  lastRemoteRevision.set(storedSessionId, remoteRevision)

  if (firstSeen ? localRevision === remoteRevision : previousRemoteRevision === remoteRevision) {
    return false
  }

  updateSessionState(
    runtimeSessionId,
    current => ({
      ...current,
      messages: preserveLocalAssistantErrors(toChatMessages(latest.messages), current.messages)
    }),
    storedSessionId
  )
  await refreshSessions().catch(() => undefined)

  return true
}

export function useExternalSessionRefresh({
  activeSessionId,
  gatewayState,
  getRuntimeState,
  getSessionMessages = fetchSessionMessages,
  pollMs = DEFAULT_EXTERNAL_SESSION_REFRESH_MS,
  refreshSessions,
  selectedStoredSessionId,
  updateSessionState
}: ExternalSessionRefreshOptions) {
  const callbacksRef = useRef({ getRuntimeState, getSessionMessages, refreshSessions, updateSessionState })
  const inFlightRef = useRef(false)
  const lastRemoteRevisionRef = useRef(new Map<string, string>())

  callbacksRef.current = { getRuntimeState, getSessionMessages, refreshSessions, updateSessionState }

  useEffect(() => {
    if (gatewayState !== 'open' || !activeSessionId || !selectedStoredSessionId) {
      return undefined
    }

    let cancelled = false
    const intervalMs = Math.max(MIN_EXTERNAL_SESSION_REFRESH_MS, pollMs)

    const poll = async () => {
      if (inFlightRef.current) {
        return
      }

      inFlightRef.current = true

      try {
        await refreshExternalSessionSnapshot({
          ...callbacksRef.current,
          getSessionMessages: async storedSessionId => {
            const latest = await callbacksRef.current.getSessionMessages(storedSessionId)

            if (cancelled) {
              throw new Error('external session refresh cancelled')
            }

            return latest
          },
          lastRemoteRevision: lastRemoteRevisionRef.current,
          runtimeSessionId: activeSessionId,
          storedSessionId: selectedStoredSessionId
        })

        if (cancelled) {
          return
        }
      } catch {
        // Best-effort read repair. The normal gateway stream and manual Cmd+R
        // remain available if a transient API read fails.
      } finally {
        inFlightRef.current = false
      }
    }

    void poll()
    const handle = window.setInterval(() => void poll(), intervalMs)

    return () => {
      cancelled = true
      window.clearInterval(handle)
    }
  }, [activeSessionId, gatewayState, pollMs, selectedStoredSessionId])
}
