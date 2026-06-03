import { useStore } from '@nanostores/react'
import { useCallback, useEffect, useRef } from 'react'

import { HermesGateway } from '@/hermes'
import { $gatewayState, setConnection } from '@/store/session'

export interface GatewayRequestOptions {
  gatewayId?: string
}

export function useGatewayRequest() {
  const gatewayState = useStore($gatewayState)
  const gatewayRef = useRef<HermesGateway | null>(null)
  const gatewayByIdRef = useRef<Map<string, HermesGateway>>(new Map())

  const connectionRef = useRef<Awaited<ReturnType<NonNullable<typeof window.hermesDesktop>['getConnection']>> | null>(
    null
  )

  const gatewayStateRef = useRef(gatewayState)
  const reconnectingRef = useRef<Promise<HermesGateway | null> | null>(null)
  const reconnectingByIdRef = useRef<Map<string, Promise<HermesGateway | null>>>(new Map())

  useEffect(() => {
    gatewayStateRef.current = gatewayState
  }, [gatewayState])

  const ensureGatewayOpen = useCallback(async (gatewayId?: string) => {
    const trimmedGatewayId = gatewayId?.trim()
    const existing = trimmedGatewayId ? (gatewayByIdRef.current.get(trimmedGatewayId) ?? new HermesGateway()) : gatewayRef.current

    if (!existing) {
      return null
    }

    if (!trimmedGatewayId && gatewayStateRef.current === 'open') {
      return existing
    }

    if (trimmedGatewayId && gatewayByIdRef.current.has(trimmedGatewayId)) {
      return existing
    }

    if (trimmedGatewayId) {
      const current = reconnectingByIdRef.current.get(trimmedGatewayId)

      if (current) {
        return current
      }

      const reconnecting = (async () => {
        const desktop = window.hermesDesktop

        if (!desktop) {
          return null
        }

        try {
          const conn = await desktop.getConnection(trimmedGatewayId)
          await existing.connect(conn.wsUrl)
          gatewayByIdRef.current.set(trimmedGatewayId, existing)

          return existing
        } finally {
          reconnectingByIdRef.current.delete(trimmedGatewayId)
        }
      })()

      reconnectingByIdRef.current.set(trimmedGatewayId, reconnecting)

      return reconnecting
    }

    if (reconnectingRef.current) {
      return reconnectingRef.current
    }

    reconnectingRef.current = (async () => {
      const desktop = window.hermesDesktop

      if (!desktop) {
        return null
      }

      try {
        const conn = await desktop.getConnection()
        connectionRef.current = conn
        setConnection(conn)
        await existing.connect(conn.wsUrl)

        return existing
      } catch {
        connectionRef.current = null
        setConnection(null)

        return null
      } finally {
        reconnectingRef.current = null
      }
    })()

    return reconnectingRef.current
  }, [])

  const requestGateway = useCallback(
    async <T>(method: string, params: Record<string, unknown> = {}, options: GatewayRequestOptions = {}) => {
      const gatewayId = options.gatewayId?.trim()
      let gateway = gatewayId ? gatewayByIdRef.current.get(gatewayId) : gatewayRef.current

      if (!gateway && gatewayId) {
        gateway = await ensureGatewayOpen(gatewayId)
      }

      if (!gateway) {
        throw new Error('Hermes gateway unavailable')
      }

      try {
        return await gateway.request<T>(method, params)
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error)

        if (!/not connected|connection closed/i.test(message)) {
          throw error
        }

        if (gatewayId) {
          gatewayByIdRef.current.delete(gatewayId)
        }

        const recovered = await ensureGatewayOpen(gatewayId)

        if (!recovered) {
          throw error
        }

        return recovered.request<T>(method, params)
      }
    },
    [ensureGatewayOpen]
  )

  return { connectionRef, gatewayRef, requestGateway }
}
