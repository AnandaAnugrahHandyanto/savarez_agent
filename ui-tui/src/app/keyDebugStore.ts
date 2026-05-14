type KeyDebugSink = (line: string) => void

let enabled = false
let sink: KeyDebugSink | null = null

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

export function setKeyDebugEnabled(next: boolean) {
  enabled = next
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
  } else {
    process.stderr.write(`${line}\n`)
  }
}
