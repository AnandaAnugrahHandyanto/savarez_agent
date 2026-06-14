/**
 * Shared primary-backend revalidation logic for the Electron main process.
 *
 * Kept pure and dependency-injected so wake/reconnect behavior can be tested
 * without loading Electron. A rejected cached connection promise is itself a
 * stale descriptor: remote backends have no child-process exit handler to clear
 * it, so callers must reset before the renderer retries.
 */

async function revalidatePrimaryConnection(connectionPromise, options = {}) {
  const { probeStatus, resetConnection, rememberLog } = options

  if (!connectionPromise) {
    return { ok: true, rebuilt: false }
  }

  let conn = null
  try {
    conn = await connectionPromise
  } catch {
    resetConnection?.()
    return { ok: true, rebuilt: true }
  }

  if (!conn || conn.mode !== 'remote' || !conn.baseUrl) {
    return { ok: true, rebuilt: false }
  }

  const base = conn.baseUrl.replace(/\/+$/, '')
  try {
    await probeStatus?.(`${base}/api/status`)
    return { ok: true, rebuilt: false }
  } catch {
    rememberLog?.('Cached remote Hermes backend failed liveness probe; dropping stale connection.')
    resetConnection?.()
    return { ok: true, rebuilt: true }
  }
}

module.exports = {
  revalidatePrimaryConnection
}
