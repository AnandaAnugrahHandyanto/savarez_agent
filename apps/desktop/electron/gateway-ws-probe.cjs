/**
 * gateway-ws-probe.cjs
 *
 * Lightweight live-WebSocket probe for Hermes Desktop remote gateway checks.
 * `/api/status` alone is not enough to prove the desktop can actually chat:
 * the renderer opens a separate `/api/ws` socket, so a remote URL that points
 * at an API-only endpoint (for example `/v1`) can look "ready" while the live
 * gateway socket is unusable. This helper verifies the socket opens and stays
 * open briefly before the desktop declares the remote gateway ready.
 */

const DEFAULT_GATEWAY_WS_PROBE_TIMEOUT_MS = 3_000
const DEFAULT_GATEWAY_WS_STABLE_MS = 250

function resolveProbeTiming(value, fallback) {
  const num = Number(value)
  return Number.isFinite(num) && num > 0 ? Math.floor(num) : fallback
}

function closeReason(event) {
  if (!event || typeof event !== 'object') {
    return 'unknown close event'
  }

  const code = Number.isFinite(event.code) ? `code ${event.code}` : 'unknown code'
  const reason = typeof event.reason === 'string' && event.reason.trim() ? `: ${event.reason.trim()}` : ''
  return `${code}${reason}`
}

function eventError(event) {
  if (event?.error instanceof Error) {
    return event.error
  }

  if (event instanceof Error) {
    return event
  }

  return new Error('WebSocket connection failed before the gateway became usable.')
}

function probeGatewayWebSocket(wsUrl, options = {}) {
  const target = String(wsUrl || '').trim()

  if (!target) {
    throw new Error('Gateway WebSocket URL is required.')
  }

  const WebSocketImpl = options.WebSocketImpl || globalThis.WebSocket

  if (typeof WebSocketImpl !== 'function') {
    throw new Error('WebSocket is unavailable in this runtime.')
  }

  const timeoutMs = resolveProbeTiming(options.timeoutMs, DEFAULT_GATEWAY_WS_PROBE_TIMEOUT_MS)
  const stableMs = resolveProbeTiming(options.stableMs, DEFAULT_GATEWAY_WS_STABLE_MS)

  return new Promise((resolve, reject) => {
    let socket
    let settled = false
    let deadlineTimer = null
    let stableTimer = null

    const clearTimers = () => {
      if (deadlineTimer) clearTimeout(deadlineTimer)
      if (stableTimer) clearTimeout(stableTimer)
      deadlineTimer = null
      stableTimer = null
    }

    const finish = error => {
      if (settled) return
      settled = true
      clearTimers()

      try {
        if (socket && socket.readyState < WebSocketImpl.CLOSING) {
          socket.close(1000, 'probe-complete')
        }
      } catch {
        // Best-effort cleanup only.
      }

      if (error) {
        reject(error)
      } else {
        resolve()
      }
    }

    try {
      socket = new WebSocketImpl(target)
    } catch (error) {
      finish(error instanceof Error ? error : new Error(String(error)))
      return
    }

    deadlineTimer = setTimeout(() => {
      finish(new Error(`Timed out opening live gateway WebSocket after ${timeoutMs}ms.`))
    }, timeoutMs)

    socket.onopen = () => {
      stableTimer = setTimeout(() => finish(null), stableMs)
    }

    socket.onerror = event => {
      finish(eventError(event))
    }

    socket.onclose = event => {
      finish(new Error(`Gateway WebSocket closed before becoming stable (${closeReason(event)}).`))
    }
  })
}

module.exports = {
  DEFAULT_GATEWAY_WS_PROBE_TIMEOUT_MS,
  DEFAULT_GATEWAY_WS_STABLE_MS,
  probeGatewayWebSocket
}
