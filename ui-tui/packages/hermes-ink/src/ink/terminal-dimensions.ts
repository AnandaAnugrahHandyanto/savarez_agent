const DEFAULT_COLUMNS = 80
const DEFAULT_ROWS = 24
const MAX_COLUMNS = 2000
const MAX_ROWS = 1000
const MIN_COLUMNS = 1
const MIN_ROWS = 1

// Keep this package-local helper in sync with ui-tui/src/lib/terminalDimensions.ts.
type TerminalSizeSource = {
  columns?: number
  rows?: number
}

function sanitizeDimension(value: unknown, min: number, max: number, fallback: number): number {
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

function readDimension(stream: null | TerminalSizeSource | undefined, key: keyof TerminalSizeSource): unknown {
  try {
    return stream?.[key]
  } catch {
    return undefined
  }
}

export function safeColumns(stream?: null | TerminalSizeSource, fallback = DEFAULT_COLUMNS): number {
  return sanitizeDimension(readDimension(stream, 'columns'), MIN_COLUMNS, MAX_COLUMNS, fallback)
}

export function safeRows(stream?: null | TerminalSizeSource, fallback = DEFAULT_ROWS): number {
  return sanitizeDimension(readDimension(stream, 'rows'), MIN_ROWS, MAX_ROWS, fallback)
}

export function safeTerminalSize(stream?: null | TerminalSizeSource): { columns: number; rows: number } {
  return {
    columns: safeColumns(stream),
    rows: safeRows(stream)
  }
}
