export interface TerminalTitleInput {
  busy: boolean
  fallbackLabel?: string
  model?: string
  status?: string
  title?: string
}

const CLEAN_STATUS_RE = /\s+/g
const GENERIC_BUSY_STATUSES = new Set(['ready', 'running…', 'running...', 'summoning hermes…'])

const clean = (value?: string): string => String(value ?? '').replace(CLEAN_STATUS_RE, ' ').trim()
const shortModel = (value?: string): string => clean(value).replace(/^.*\//, '')

export function buildTerminalTitle({ busy, fallbackLabel = 'Hermes', model, status, title }: TerminalTitleInput): string {
  const topic = clean(title)
  const modelLabel = shortModel(model)
  const activity = clean(status)
  const showActivity = busy && activity && !GENERIC_BUSY_STATUSES.has(activity.toLowerCase())
  const fallbackTopic = modelLabel ? `${busy ? '⏳' : '✓'} ${modelLabel}` : ''

  if (topic && showActivity) {
    return `${topic} · ${activity} — ${fallbackLabel}`
  }
  if (topic) {
    return `${topic} — ${fallbackLabel}`
  }
  if (fallbackTopic && showActivity) {
    return `${fallbackTopic} · ${activity} — ${fallbackLabel}`
  }
  if (fallbackTopic) {
    return `${fallbackTopic} — ${fallbackLabel}`
  }
  if (showActivity) {
    return `${activity} — ${fallbackLabel}`
  }
  return fallbackLabel
}
