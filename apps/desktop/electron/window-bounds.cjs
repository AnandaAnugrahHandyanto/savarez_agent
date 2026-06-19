// Pure helpers for persisting and restoring the main window's size/position.
//
// The Electron main process owns the live BrowserWindow, but all of the
// decision logic (what is a valid saved bounds payload, and whether those
// bounds are still visible on a currently-attached display) is pure and lives
// here so it can be unit-tested without spinning up Electron. See
// window-bounds.test.cjs.

const DEFAULT_BOUNDS = Object.freeze({ width: 1220, height: 800 })

// Minimums must match the BrowserWindow `minWidth`/`minHeight` in main.cjs so
// we never restore a window smaller than the renderer can lay out.
const MIN_WIDTH = 400
const MIN_HEIGHT = 620

function isFiniteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value)
}

/**
 * Validate and normalize a raw saved-bounds payload (e.g. parsed JSON from
 * disk). Returns a clean { x, y, width, height, isMaximized } object, or null
 * when the payload is missing required fields / is malformed.
 *
 * width/height are clamped to the window minimums. x/y are optional (a
 * payload may legitimately omit them, e.g. an OS that didn't report a
 * position); when present they must be finite integers.
 */
function sanitizeBounds(raw) {
  if (!raw || typeof raw !== 'object') {
    return null
  }

  if (!isFiniteNumber(raw.width) || !isFiniteNumber(raw.height)) {
    return null
  }

  const width = Math.max(MIN_WIDTH, Math.round(raw.width))
  const height = Math.max(MIN_HEIGHT, Math.round(raw.height))

  const out = {
    width,
    height,
    isMaximized: Boolean(raw.isMaximized)
  }

  if (isFiniteNumber(raw.x) && isFiniteNumber(raw.y)) {
    out.x = Math.round(raw.x)
    out.y = Math.round(raw.y)
  }

  return out
}

/**
 * True when at least part of `bounds` overlaps the visible work area of one of
 * the supplied displays. Used to discard saved positions that would place the
 * window entirely off-screen (e.g. an external monitor that has since been
 * unplugged) so the window doesn't reopen invisible.
 *
 * `displays` is the shape returned by Electron's `screen.getAllDisplays()`:
 * each entry has a `workArea` (or `bounds`) of { x, y, width, height }.
 * A bounds with no x/y is treated as visible (the OS will place it).
 */
function isVisibleOnDisplays(bounds, displays) {
  if (!bounds) {
    return false
  }

  if (!isFiniteNumber(bounds.x) || !isFiniteNumber(bounds.y)) {
    // No stored position — let the OS/Electron pick a default placement.
    return true
  }

  if (!Array.isArray(displays) || displays.length === 0) {
    return false
  }

  const left = bounds.x
  const top = bounds.y
  const right = bounds.x + bounds.width
  const bottom = bounds.y + bounds.height

  // Require a minimum visible patch so a 1px sliver on a removed monitor
  // doesn't count as "visible".
  const MIN_VISIBLE = 48

  for (const display of displays) {
    const area = display?.workArea || display?.bounds
    if (
      !area ||
      !isFiniteNumber(area.x) ||
      !isFiniteNumber(area.y) ||
      !isFiniteNumber(area.width) ||
      !isFiniteNumber(area.height)
    ) {
      continue
    }

    const overlapX = Math.min(right, area.x + area.width) - Math.max(left, area.x)
    const overlapY = Math.min(bottom, area.y + area.height) - Math.max(top, area.y)

    if (overlapX >= MIN_VISIBLE && overlapY >= MIN_VISIBLE) {
      return true
    }
  }

  return false
}

/**
 * Compute the BrowserWindow constructor options for size/position from a saved
 * payload, falling back to defaults when the payload is missing, malformed, or
 * would land off-screen.
 *
 * Returns { width, height, x?, y?, isMaximized }. `isMaximized` is advisory —
 * the caller maximizes the window after creation rather than via constructor
 * options (Electron has no `maximized` option).
 */
function resolveInitialBounds(raw, displays, defaults = DEFAULT_BOUNDS) {
  const fallback = {
    width: defaults.width,
    height: defaults.height,
    isMaximized: false
  }

  const sanitized = sanitizeBounds(raw)
  if (!sanitized) {
    return fallback
  }

  if (!isVisibleOnDisplays(sanitized, displays)) {
    // Keep the remembered size, drop the off-screen position.
    return {
      width: sanitized.width,
      height: sanitized.height,
      isMaximized: sanitized.isMaximized
    }
  }

  return sanitized
}

module.exports = {
  DEFAULT_BOUNDS,
  MIN_WIDTH,
  MIN_HEIGHT,
  sanitizeBounds,
  isVisibleOnDisplays,
  resolveInitialBounds
}
