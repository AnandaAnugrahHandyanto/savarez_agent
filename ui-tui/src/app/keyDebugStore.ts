import { appendFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

type KeyDebugSink = (line: string) => void

const envEnabled = /^(1|true|yes|on)$/i.test(process.env.HERMES_TUI_DEBUG_KEYS ?? '')

let enabled = envEnabled
let sink: KeyDebugSink | null = null
let logPath: string | null = envEnabled
  ? (process.env.HERMES_TUI_DEBUG_KEYS_FILE ?? join(tmpdir(), 'hermes-tui-keys.log'))
  : null

const FLAGS = [
  'return',
  'ctrl',
  'meta',
  'super',
  'shift',
  'option',
  'escape',
  'tab',
  'backspace',
  'delete',
  'upArrow',
  'downArrow',
  'leftArrow',
  'rightArrow'
]

function formatValue(value: string | undefined) {
  return value === undefined ? 'undefined' : JSON.stringify(value)
}

function formatCodes(value: string | undefined) {
  if (!value) {
    return ''
  }

  return ` codes=${Array.from(value)
    .map(ch => ch.codePointAt(0)?.toString(16).padStart(2, '0') ?? '??')
    .join(' ')}`
}

export function isKeyDebugEnabled() {
  return enabled
}

export function keyDebugDestination() {
  if (sink) {
    return 'transcript'
  }

  return logPath ?? 'stderr'
}

export function setKeyDebugEnabled(next: boolean) {
  enabled = next

  if (next && !sink && !logPath) {
    logPath = join(tmpdir(), 'hermes-tui-keys.log')
  }
}

export function setKeyDebugSink(next: KeyDebugSink | null) {
  sink = next
}

export function toggleKeyDebug() {
  enabled = !enabled

  return enabled
}

export function emitKeyDebug(
  source: string,
  input: string,
  key: Record<string, unknown>,
  raw?: string,
  detail?: string
) {
  if (!enabled) {
    return
  }

  const flags = FLAGS.filter(flag => key[flag] === true)
  const line = [
    `[key-debug] ${source}`,
    `input=${formatValue(input)}${formatCodes(input)}`,
    `raw=${formatValue(raw)}${formatCodes(raw)}`,
    `flags=${flags.length ? flags.join(',') : 'none'}`,
    detail
  ]
    .filter(Boolean)
    .join(' ')

  if (sink) {
    sink(line)
  } else if (logPath) {
    appendFileSync(logPath, `${line}\n`)
  } else {
    process.stderr.write(`${line}\n`)
  }
}
