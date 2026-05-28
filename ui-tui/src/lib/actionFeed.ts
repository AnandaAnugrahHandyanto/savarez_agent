import { compactPreview } from './text.js'

export type ActionStatus = 'error' | 'running' | 'success'

export const ACTION_FEED_VISIBLE_LIMIT = 5

export interface ParsedActionCall {
  action: string
  subject: string
  title: string
}

export interface FoldedActionDetail {
  hiddenLines: number
  preview: string
}

const CALL_RE = /^(.*?)(?:\("([\s\S]*)"\))?$/
const DURATION_RE = / \(\d+(?:\.\d)?s\)$/

const cleanSubject = (value = '') =>
  value
    .replace(/^['"]|['"]$/g, '')
    .replace(/\\n/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

const tailPath = (value: string) => {
  const cleaned = cleanSubject(value)

  if (!cleaned) {
    return ''
  }

  const parts = cleaned.split('/').filter(Boolean)
  return parts.length > 2 ? `…/${parts.slice(-2).join('/')}` : cleaned
}

const quoted = (value: string) => (value ? `"${compactPreview(cleanSubject(value), 56)}"` : '')

const ACTIONS: Record<string, (subject: string) => ParsedActionCall> = {
  'Browser Back': () => ({ action: 'Went back', subject: '', title: 'Went back' }),
  'Browser Click': subject => ({ action: 'Clicked', subject: quoted(subject), title: ['Clicked', quoted(subject)].filter(Boolean).join(' ') }),
  'Browser Console': subject => ({ action: 'Inspected console', subject: quoted(subject), title: ['Inspected console', quoted(subject)].filter(Boolean).join(' ') }),
  'Browser Navigate': subject => ({ action: 'Opened', subject: quoted(subject), title: ['Opened', quoted(subject)].filter(Boolean).join(' ') }),
  'Browser Press': subject => ({ action: 'Pressed key', subject: quoted(subject), title: ['Pressed key', quoted(subject)].filter(Boolean).join(' ') }),
  'Browser Scroll': subject => ({ action: 'Scrolled', subject: quoted(subject), title: ['Scrolled', quoted(subject)].filter(Boolean).join(' ') }),
  'Browser Snapshot': () => ({ action: 'Read page snapshot', subject: '', title: 'Read page snapshot' }),
  'Browser Type': subject => ({ action: 'Typed', subject: quoted(subject), title: ['Typed', quoted(subject)].filter(Boolean).join(' ') }),
  'Delegate Task': subject => ({ action: 'Delegated', subject: quoted(subject), title: ['Delegated', quoted(subject)].filter(Boolean).join(' ') }),
  'Execute Code': subject => ({ action: 'Ran Python', subject: quoted(subject), title: ['Ran Python', quoted(subject)].filter(Boolean).join(' ') }),
  Patch: subject => ({ action: 'Edited', subject: tailPath(subject), title: ['Edited', tailPath(subject)].filter(Boolean).join(' ') }),
  'Read File': subject => ({ action: 'Read', subject: tailPath(subject), title: ['Read', tailPath(subject)].filter(Boolean).join(' ') }),
  'Search Files': subject => ({ action: 'Searched', subject: quoted(subject), title: ['Searched', quoted(subject)].filter(Boolean).join(' ') }),
  Terminal: subject => ({ action: 'Ran', subject: quoted(subject), title: ['Ran', quoted(subject)].filter(Boolean).join(' ') }),
  Todo: () => ({ action: 'Updated todos', subject: '', title: 'Updated todos' }),
  'Write File': subject => ({ action: 'Wrote', subject: tailPath(subject), title: ['Wrote', tailPath(subject)].filter(Boolean).join(' ') })
}

export const parseActionCall = (call: string): ParsedActionCall => {
  const body = String(call || '').replace(DURATION_RE, '').trim()
  const match = body.match(CALL_RE)
  const rawName = (match?.[1] ?? body).trim()
  const subject = match?.[2] ?? ''
  const formatter = ACTIONS[rawName]

  if (formatter) {
    return formatter(subject)
  }

  const fallbackSubject = quoted(subject)
  return {
    action: rawName || 'Tool',
    subject: fallbackSubject,
    title: [rawName || 'Tool', fallbackSubject].filter(Boolean).join(' ')
  }
}

export const actionStatusGlyph = (status: ActionStatus) => {
  if (status === 'running') {
    return '●'
  }

  return status === 'error' ? '✗' : '✓'
}

export const foldActionDetail = (detail: string, maxLines = 4, maxChars = 420): FoldedActionDetail => {
  const raw = String(detail || '').trim()

  if (!raw) {
    return { hiddenLines: 0, preview: '' }
  }

  const lines = raw.split('\n')
  const visible: string[] = []
  let used = 0

  for (const line of lines) {
    const next = visible.length ? used + 1 + line.length : used + line.length

    if (visible.length >= maxLines || next > maxChars) {
      break
    }

    visible.push(line)
    used = next
  }

  if (!visible.length) {
    visible.push(compactPreview(lines[0] ?? raw, maxChars))
  }

  const hiddenLines = Math.max(0, lines.length - visible.length)
  return { hiddenLines, preview: visible.join('\n') }
}

export interface ActionFeedItemLike {
  label: string
  status: ActionStatus
}

const IMPORTANT_ACTION_LABEL_RE = /^(?:Browser (?:Click|Navigate|Type)|Delegate Task|Execute Code|Patch|Terminal|Todo|Write File)/

export const isImportantActionLabel = (label: string): boolean => IMPORTANT_ACTION_LABEL_RE.test(label)

export const selectVisibleActionFeedItems = <T extends ActionFeedItemLike>(
  items: readonly T[],
  limit = ACTION_FEED_VISIBLE_LIMIT
): { hidden: number; items: T[] } => {
  if (items.length <= limit) {
    return { hidden: 0, items: [...items] }
  }

  const keep = new Set<number>()

  items.forEach((item, index) => {
    if (item.status !== 'success' || isImportantActionLabel(item.label)) {
      keep.add(index)
    }
  })

  for (let index = Math.max(0, items.length - 2); index < items.length; index += 1) {
    keep.add(index)
  }

  for (let index = items.length - 1; keep.size < Math.min(limit, items.length) && index >= 0; index -= 1) {
    keep.add(index)
  }

  const selected = [...keep].sort((a, b) => a - b).slice(-limit)

  return {
    hidden: Math.max(0, items.length - selected.length),
    items: selected.map(index => items[index]!)
  }
}
