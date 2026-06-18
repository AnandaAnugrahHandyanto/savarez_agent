'use strict'

const MESSAGE_SEND_RESTART_BLOCK_MS = 15_000

function safeDecodeChunk(chunk) {
  if (chunk === null || chunk === undefined) {
    return ''
  }

  if (Buffer.isBuffer(chunk)) {
    return chunk.toString('utf8')
  }

  if (chunk instanceof Uint8Array) {
    return Buffer.from(chunk).toString('utf8')
  }

  try {
    return String(chunk)
  } catch {
    return ''
  }
}

function createMessageSendRestartGuard({ graceMs = MESSAGE_SEND_RESTART_BLOCK_MS, now = () => Date.now() } = {}) {
  let activeCount = 0
  let lastFailureAt = 0

  const snapshot = () => ({
    activeCount,
    blockingRestart: activeCount > 0 || (lastFailureAt > 0 && now() - lastFailureAt < graceMs),
    lastFailureAt: lastFailureAt || null
  })

  return {
    snapshot,
    record(payload = {}) {
      switch (payload.state) {
        case 'begin':
          activeCount += 1
          break
        case 'failure':
          activeCount = Math.max(0, activeCount - 1)
          lastFailureAt = now()
          break
        case 'success':
          activeCount = Math.max(0, activeCount - 1)
          break
        default:
          break
      }

      return snapshot()
    },
    restartBlockReason() {
      const current = snapshot()

      if (current.activeCount > 0) {
        return `message-send-active:${current.activeCount}`
      }

      if (current.blockingRestart) {
        return 'message-send-recent-failure'
      }

      return null
    }
  }
}

module.exports = {
  MESSAGE_SEND_RESTART_BLOCK_MS,
  createMessageSendRestartGuard,
  safeDecodeChunk
}
