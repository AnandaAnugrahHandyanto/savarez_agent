const DEFAULT_UNRESPONSIVE_LOG_DEBOUNCE_MS = 10_000

function createRendererUnresponsiveHandler({ log, now = Date.now, debounceMs = DEFAULT_UNRESPONSIVE_LOG_DEBOUNCE_MS } = {}) {
  if (typeof log !== 'function') {
    throw new TypeError('createRendererUnresponsiveHandler requires a log function')
  }

  let lastLogAt = Number.NEGATIVE_INFINITY

  return function handleRendererUnresponsive(event) {
    // Electron/Chromium owns the native "page is unresponsive" UI. Some
    // versions expose a preventable event and some do not; call it when present
    // and pair this handler with the pre-ready disable-hang-monitor switch in
    // main.cjs so Hermes keeps only its in-app warning surface.
    event?.preventDefault?.()

    const currentTime = now()
    if (currentTime - lastLogAt < debounceMs) {
      return
    }

    lastLogAt = currentTime
    log('[renderer] webContents became unresponsive; native popup suppressed')
  }
}

module.exports = {
  DEFAULT_UNRESPONSIVE_LOG_DEBOUNCE_MS,
  createRendererUnresponsiveHandler
}
