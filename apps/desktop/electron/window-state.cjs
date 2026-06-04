'use strict'

// Helpers for reading BrowserWindow geometry that NEVER throw when the window
// has gone away.
//
// A destroyed Electron BrowserWindow is still a non-null JS object, so optional
// chaining (`win?.isFullScreen?.()`) does NOT protect against it — calling any
// native method on a destroyed window throws "Object has been destroyed". This
// bit the boot flow: startHermes() resolves with `...getWindowState()` once the
// backend is ready, and if the window was torn down in the meantime (updater
// relaunch, gateway reconnect), querying it rejected the whole boot with
// "Desktop boot failed: Object has been destroyed". See #38468.
//
// These functions live in their own module (no `electron` import) so they can
// be unit-tested with plain fake window objects.

function isWindowLive(win) {
  if (!win) return false
  try {
    return typeof win.isDestroyed === 'function' ? !win.isDestroyed() : true
  } catch {
    // A window so far gone that even isDestroyed() throws is, definitionally,
    // not safe to query.
    return false
  }
}

function getWindowButtonPosition(win, { isMac, fallbackButtonPosition } = {}) {
  if (!isMac) return null
  if (!isWindowLive(win)) return fallbackButtonPosition
  try {
    return win.getWindowButtonPosition?.() || fallbackButtonPosition
  } catch {
    return fallbackButtonPosition
  }
}

function getWindowState(win, { isMac, nativeOverlayWidth, fallbackButtonPosition } = {}) {
  let isFullscreen = false
  if (isWindowLive(win)) {
    try {
      isFullscreen = Boolean(win.isFullScreen?.())
    } catch {
      isFullscreen = false
    }
  }

  return {
    isFullscreen,
    nativeOverlayWidth,
    windowButtonPosition: getWindowButtonPosition(win, { isMac, fallbackButtonPosition })
  }
}

module.exports = { getWindowButtonPosition, getWindowState, isWindowLive }
