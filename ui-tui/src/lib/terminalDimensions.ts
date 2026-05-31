/**
 * Sanitize terminal dimensions reported by the host.
 *
 * Some environments report bogus window sizes. The motivating case (WSL,
 * reported by @northframe_17) is `columns=131072, rows=1` — a width that
 * overflows any sane layout and a height of one row that makes the TUI
 * unusable. Node's own `stdout.columns || 80` fallback only catches
 * `0`/`NaN`/`undefined`, so a positive-but-absurd value sails straight into
 * the Ink renderer, which then allocates a 131072-cell-wide screen buffer.
 *
 * We clamp each dimension independently to a sane range. Out-of-range or
 * non-finite values fall back to the conventional 80x24 default rather than
 * the raw garbage.
 */

export const DEFAULT_COLUMNS = 80
export const DEFAULT_ROWS = 24

// Upper bounds are generous (ultrawide multi-monitor terminals, tmux panes
// spanning huge displays) but well below the WSL garbage value. Anything
// beyond these is treated as a broken probe.
export const MAX_COLUMNS = 2000
export const MAX_ROWS = 1000
export const MIN_COLUMNS = 1
export const MIN_ROWS = 1

/**
 * Clamp a single reported dimension into `[min, max]`.
 *
 * Returns a sanitized fallback when the value is non-finite or `<= 0` (the classic
 * "no size yet" signal). A positive value above `max` is clamped to `max`,
 * not replaced by the fallback — an oversized-but-finite report is more
 * likely a real-but-large terminal than a missing one, and clamping keeps
 * the layout sane either way.
 */
export function sanitizeDimension(value: unknown, min: number, max: number, fallback: number): number {
  const safeFallback =
    typeof fallback === 'number' && Number.isFinite(fallback) && fallback > 0
      ? Math.min(max, Math.max(min, Math.floor(fallback)))
      : min

  if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
    return safeFallback
  }

  const rounded = Math.floor(value)

  if (rounded < min) {
    return safeFallback
  }

  if (rounded > max) {
    return max
  }

  return rounded
}

export interface SanitizedTerminalSize {
  columns: number
  rows: number
}

/** Sanitize a (columns, rows) pair using the TUI's bounds. */
export function sanitizeTerminalSize(columns: unknown, rows: unknown): SanitizedTerminalSize {
  return {
    columns: sanitizeDimension(columns, MIN_COLUMNS, MAX_COLUMNS, DEFAULT_COLUMNS),
    rows: sanitizeDimension(rows, MIN_ROWS, MAX_ROWS, DEFAULT_ROWS)
  }
}

export interface TerminalSizeSource {
  columns?: number
  rows?: number
}

function readDimension(stream: null | TerminalSizeSource | undefined, key: keyof TerminalSizeSource): unknown {
  try {
    return stream?.[key]
  } catch {
    return undefined
  }
}

/** Read a sanitized terminal width without mutating the host stream. */
export function safeColumns(stream?: null | TerminalSizeSource, fallback = DEFAULT_COLUMNS): number {
  return sanitizeDimension(readDimension(stream, 'columns'), MIN_COLUMNS, MAX_COLUMNS, fallback)
}

/** Read a sanitized terminal height without mutating the host stream. */
export function safeRows(stream?: null | TerminalSizeSource, fallback = DEFAULT_ROWS): number {
  return sanitizeDimension(readDimension(stream, 'rows'), MIN_ROWS, MAX_ROWS, fallback)
}

/** Read sanitized terminal dimensions without mutating the host stream. */
export function safeTerminalSize(stream?: null | TerminalSizeSource): SanitizedTerminalSize {
  return {
    columns: safeColumns(stream),
    rows: safeRows(stream)
  }
}
