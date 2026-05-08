import { OSC52_CLIPBOARD_QUERY } from './osc52.js'
import type { TerminalProbeResult } from './terminalCapabilities.js'

export type Querier = {
  flush: () => Promise<void>
  send: <T>(query: { match: (r: unknown) => r is T; request: string }) => Promise<T | undefined>
}

export type TerminalProbeOptions = {
  allowOsc52Read?: boolean
  timeoutMs?: number
}

type ProbeQuery<T> = {
  match: (r: unknown) => r is T
  request: string
}

type XtversionResponse = string | { name: string }
type Da2Response = string | { params: number[] }
type DecrpmResponse = string | { mode: number; status: number }
type KittyKeyboardResponse = string | { flags: number }
type Osc52Response = string | { code: number; data: string }

const DEFAULT_TIMEOUT_MS = 300
const PROBE_TIMEOUT = Symbol('terminal-probe-timeout')

// eslint-disable-next-line no-control-regex
const XTVERSION_RAW_RE = /^\x1bP>\|([\s\S]*?)(?:\x07|\x1b\\)$/
// eslint-disable-next-line no-control-regex
const DA2_RAW_RE = /^\x1b\[>([\d;]*)c$/
// eslint-disable-next-line no-control-regex
const DECRPM_RAW_RE = /^\x1b\[\?(\d+);(\d+)\$y$/
// eslint-disable-next-line no-control-regex
const KITTY_RAW_RE = /^\x1b\[\?(\d+)u$/
// eslint-disable-next-line no-control-regex
const OSC52_RAW_RE = /^\x1b\]52;c;([\s\S]*?)(?:\x07|\x1b\\)$/

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null

const hasNonEmptyString = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0

const makeQuery = <T>(request: string, match: (r: unknown) => r is T): ProbeQuery<T> => ({ request, match })

const xtversionQuery = makeQuery<XtversionResponse>('\x1b[>0q', (value: unknown): value is XtversionResponse => {
  if (hasNonEmptyString(value)) {
    return true
  }

  return isRecord(value) && hasNonEmptyString(value.name)
})

const da2Query = makeQuery<Da2Response>('\x1b[>c', (value: unknown): value is Da2Response => {
  if (typeof value === 'string') {
    return DA2_RAW_RE.test(value) || hasNonEmptyString(value)
  }

  return isRecord(value) && Array.isArray(value.params) && value.params.every(param => typeof param === 'number')
})

const decrqmQuery = (mode: number) =>
  makeQuery<DecrpmResponse>(`\x1b[?${mode}$p`, (value: unknown): value is DecrpmResponse => {
    if (isRecord(value)) {
      const rawMode = value.mode
      const rawStatus = value.status

      return typeof rawMode === 'number' && rawMode === mode && typeof rawStatus === 'number'
    }

    if (hasNonEmptyString(value)) {
      const match = DECRPM_RAW_RE.exec(value)

      return !!match && Number(match[1]) === mode && Number(match[2]) >= 0
    }

    return false
  })

const kittyKeyboardQuery = makeQuery<KittyKeyboardResponse>('\x1b[?u', (value: unknown): value is KittyKeyboardResponse => {
  if (hasNonEmptyString(value)) {
    return true
  }

  return isRecord(value) && typeof value.flags === 'number'
})

const osc52ReadQuery = makeQuery<Osc52Response>(OSC52_CLIPBOARD_QUERY, (value: unknown): value is Osc52Response => {
  if (hasNonEmptyString(value)) {
    return true
  }

  return isRecord(value) && typeof value.code === 'number' && value.code === 52 && typeof value.data === 'string'
})

const extractXtversionName = (value: unknown): string | undefined => {
  if (typeof value === 'string') {
    const raw = XTVERSION_RAW_RE.exec(value)?.[1] ?? value
    const trimmed = raw.trim()

    return trimmed.length ? trimmed : undefined
  }

  if (isRecord(value) && hasNonEmptyString(value.name)) {
    return value.name.trim()
  }

  return undefined
}

const extractBracketedPaste = (value: unknown): boolean | undefined => {
  if (typeof value === 'string') {
    const match = DECRPM_RAW_RE.exec(value)

    if (!match || Number(match[1]) !== 2004) {
      return undefined
    }

    return Number(match[2]) === 1 || Number(match[2]) === 3
  }

  if (!isRecord(value) || typeof value.mode !== 'number' || value.mode !== 2004 || typeof value.status !== 'number') {
    return undefined
  }

  return value.status === 1 || value.status === 3
}

const extractKittyKeyboardFlags = (value: unknown): number | undefined => {
  if (typeof value === 'string') {
    const match = KITTY_RAW_RE.exec(value)

    return match ? Number(match[1]) : undefined
  }

  if (isRecord(value) && typeof value.flags === 'number') {
    return value.flags
  }

  return undefined
}

const extractOsc52Read = (value: unknown): boolean | undefined => {
  if (typeof value === 'string') {
    return OSC52_RAW_RE.test(value) ? true : undefined
  }

  if (isRecord(value) && typeof value.code === 'number' && value.code === 52) {
    return true
  }

  return undefined
}

const withTimeout = async <T>(task: Promise<T>, timeoutMs: number): Promise<T | typeof PROBE_TIMEOUT> => {
  let timer: ReturnType<typeof setTimeout> | undefined

  try {
    const timeout = new Promise<typeof PROBE_TIMEOUT>(resolve => {
      timer = setTimeout(() => resolve(PROBE_TIMEOUT), timeoutMs)
    })

    return await Promise.race([task, timeout])
  } catch {
    return PROBE_TIMEOUT
  } finally {
    if (timer !== undefined) {
      clearTimeout(timer)
    }
  }
}

/** Wrap a Querier so that once timed-out, all future sent queries return `undefined`
 *  and flush() resolves immediately. This prevents unbounded queue growth when the
 *  terminal stops responding mid-probe. */
const gatedQuerier = (base: Querier): { querier: Querier; abort: () => void } => {
  let dead = false
  const abort = (): void => {
    dead = true
  }
  const querier: Querier = {
    send: <T>(query: { match: (r: unknown) => r is T; request: string }): Promise<T | undefined> => {
      if (dead) {
        return Promise.resolve(undefined)
      }
      return base.send(query)
    },
    flush: (): Promise<void> => {
      if (dead) {
        return Promise.resolve()
      }
      return base.flush()
    },
  }
  return { querier, abort }
}

const safeFlush = async (querier: Querier, timeoutMs: number): Promise<boolean> => {
  return (await withTimeout(Promise.resolve().then(() => querier.flush()), timeoutMs)) !== PROBE_TIMEOUT
}

type ProbeStepResult<T> = { value: T | undefined; timedOut: boolean }

const probeStep = async <T>(querier: Querier, query: ProbeQuery<T>, timeoutMs: number): Promise<ProbeStepResult<T>> => {
  const result = await withTimeout(Promise.resolve().then(() => querier.send(query)), timeoutMs)
  const flushOk = await safeFlush(querier, timeoutMs)

  const timedOut = result === PROBE_TIMEOUT || !flushOk

  return { value: timedOut ? undefined : result, timedOut }
}

export async function probeTerminalCapabilities(
  baseQuerier: Querier,
  options: TerminalProbeOptions = {}
): Promise<TerminalProbeResult> {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS
  const result: TerminalProbeResult = {}

  const { querier, abort } = gatedQuerier(baseQuerier)

  const initialFlush = await safeFlush(querier, timeoutMs)

  if (!initialFlush) {
    abort()
    return result
  }

  const xtversion = await probeStep(querier, xtversionQuery, timeoutMs)

  if (xtversion.timedOut) {
    abort()
    return result
  }

  const xtversionName = extractXtversionName(xtversion.value)

  if (xtversionName !== undefined) {
    result.xtversionName = xtversionName
  }

  const da2Result = await probeStep(querier, da2Query, timeoutMs)

  if (da2Result.timedOut) {
    abort()
    return result
  }

  const bracketedPaste = await probeStep(querier, decrqmQuery(2004), timeoutMs)

  if (bracketedPaste.timedOut) {
    abort()
    return result
  }

  const pasteEnabled = extractBracketedPaste(bracketedPaste.value)

  if (pasteEnabled !== undefined) {
    result.bracketedPaste = pasteEnabled
  }

  const focus1004 = await probeStep(querier, decrqmQuery(1004), timeoutMs)

  if (focus1004.timedOut) {
    abort()
    return result
  }

  const sync2026 = await probeStep(querier, decrqmQuery(2026), timeoutMs)

  if (sync2026.timedOut) {
    abort()
    return result
  }

  const kittyKeyboard = await probeStep(querier, kittyKeyboardQuery, timeoutMs)

  if (kittyKeyboard.timedOut) {
    abort()
    return result
  }

  const kittyKeyboardFlags = extractKittyKeyboardFlags(kittyKeyboard.value)

  if (kittyKeyboardFlags !== undefined) {
    result.kittyKeyboardFlags = kittyKeyboardFlags
  }

  if (options.allowOsc52Read) {
    const osc52Read = await probeStep(querier, osc52ReadQuery, timeoutMs)

    if (osc52Read.timedOut) {
      abort()
      return result
    }

    const osc52Supported = extractOsc52Read(osc52Read.value)

    if (osc52Supported !== undefined) {
      result.osc52Read = true
      result.osc52ReadSupported = true
      result.osc52WriteHint = true
    }
  }

  return result
}
