const { resolveTestWsUrl } = require('./connection-config.cjs')
const { probeGatewayWebSocket } = require('./gateway-ws-probe.cjs')

const DEFAULT_STATUS_TIMEOUT_MS = 8_000
const DEFAULT_READY_TIMEOUT_MS = 45_000
const DEFAULT_RETRY_DELAY_MS = 500

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

/**
 * Verify that a remote Hermes backend is actually usable for desktop chat.
 *
 * /api/status is intentionally public, so it only proves the gateway is
 * reachable. Desktop chat is carried by /api/ws, which authenticates via the
 * renderer's WebSocket credential path: token mode uses ?token=..., OAuth mode
 * first mints a fresh single-use ws ticket and uses ?ticket=.... This helper
 * checks both legs before the main process declares a remote backend ready.
 */
async function waitForRemoteHermes(remote, deps = {}) {
  if (!remote || !remote.baseUrl) {
    throw new Error('Remote Hermes backend is not configured. Switch to Local or configure a remote gateway.')
  }
  if (typeof deps.fetchJson !== 'function') {
    throw new Error('waitForRemoteHermes: fetchJson dependency is required.')
  }

  const deadline = Date.now() + (deps.readyTimeoutMs ?? DEFAULT_READY_TIMEOUT_MS)
  const retryDelayMs = deps.retryDelayMs ?? DEFAULT_RETRY_DELAY_MS
  let lastError = null

  while (Date.now() < deadline) {
    try {
      return await checkRemoteHermesOnce(remote, deps)
    } catch (error) {
      lastError = error
      await sleep(retryDelayMs)
    }
  }

  throw new Error(`Remote Hermes backend did not become ready: ${lastError?.message || 'timeout'}`)
}

async function checkRemoteHermesOnce(remote, deps = {}) {
  const fetchJson = deps.fetchJson
  const statusTimeoutMs = deps.statusTimeoutMs ?? DEFAULT_STATUS_TIMEOUT_MS
  const authMode = remote.authMode === 'oauth' ? 'oauth' : 'token'
  const token = authMode === 'oauth' ? null : remote.token || null

  await fetchJson(`${remote.baseUrl}/api/status`, token, { timeoutMs: statusTimeoutMs })

  const wsUrl = await resolveTestWsUrl(remote.baseUrl, authMode, token, { mintTicket: deps.mintTicket })
  if (!wsUrl) {
    throw new Error(
      'Remote Hermes backend is reachable, but no saved session token is available for /api/ws. ' +
        'Refresh the token or switch to Local.'
    )
  }

  const probeWebSocket = deps.probeWebSocket || probeGatewayWebSocket
  const probe = await probeWebSocket(wsUrl, { WebSocketImpl: deps.WebSocketImpl })
  if (!probe.ok) {
    throw new Error(formatRemoteWebSocketFailure(authMode, probe.reason))
  }

  // OAuth WS tickets are single-use; the probe consumes the ticket it opens.
  // Return a newly minted renderer URL after a successful probe so Desktop does
  // not hand the renderer a consumed or nearly-expired readiness ticket.
  if (authMode === 'oauth') {
    return {
      wsUrl: await resolveTestWsUrl(remote.baseUrl, authMode, token, { mintTicket: deps.mintTicket })
    }
  }

  return { wsUrl }
}

function formatRemoteWebSocketFailure(authMode, reason) {
  const detail = reason ? ` ${reason}` : ''
  if (authMode === 'oauth') {
    return (
      'Remote Hermes backend is reachable, but the live /api/ws chat connection failed.' +
      detail +
      ' Sign in again from Settings → Gateway, or switch to Local.'
    )
  }
  return (
    'Remote Hermes backend is reachable, but the saved token could not open the live /api/ws chat connection.' +
    detail +
    ' Refresh the token or switch to Local.'
  )
}

module.exports = {
  DEFAULT_READY_TIMEOUT_MS,
  DEFAULT_RETRY_DELAY_MS,
  DEFAULT_STATUS_TIMEOUT_MS,
  checkRemoteHermesOnce,
  formatRemoteWebSocketFailure,
  waitForRemoteHermes
}
