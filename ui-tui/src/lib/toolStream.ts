import { parseToolTrailResultLine } from './text.js'

export type ToolStreamTone = 'active' | 'analysis' | 'ambient' | 'draft' | 'error' | 'success'

export interface ToolStreamTrailClassification {
  detail: string
  label: string
  mark?: '✓' | '✗'
  rune: string
  tone: ToolStreamTone
}

export interface ToolStreamSummaryInput {
  active?: number
  completed?: number
  failed?: number
  tokensLabel?: string
}

export function toolStreamRune(tone: ToolStreamTone) {
  switch (tone) {
    case 'active':
      return '⚙'

    case 'analysis':
      return '◐'

    case 'draft':
      return '✎'

    case 'error':
      return '✗'

    case 'success':
      return '✔'

    case 'ambient':
      return '◇'
  }
}

export function classifyToolStreamTrailLine(line: string): ToolStreamTrailClassification {
  const parsed = parseToolTrailResultLine(line)

  if (parsed) {
    const mark = parsed.mark === '✗' ? '✗' : '✓'
    const tone = mark === '✗' ? 'error' : 'success'

    return {
      detail: parsed.detail,
      label: parsed.call,
      mark,
      rune: toolStreamRune(tone),
      tone
    }
  }

  if (line.startsWith('drafting ')) {
    const label = line.slice(9).replace(/…$/, '').trim()

    return {
      detail: 'drafting...',
      label,
      rune: toolStreamRune('draft'),
      tone: 'draft'
    }
  }

  if (line === 'analyzing tool output…') {
    return {
      detail: '',
      label: line,
      rune: toolStreamRune('analysis'),
      tone: 'analysis'
    }
  }

  return {
    detail: '',
    label: line,
    rune: toolStreamRune('ambient'),
    tone: 'ambient'
  }
}

export function buildToolStreamSummary({
  active = 0,
  completed = 0,
  failed = 0,
  tokensLabel
}: ToolStreamSummaryInput) {
  const parts: string[] = []

  if (active > 0) {
    parts.push(`${active} live`)
  }

  if (completed > 0) {
    parts.push(`${completed} done`)
  }

  if (failed > 0) {
    parts.push(`${failed} failed`)
  }

  if (tokensLabel) {
    parts.push(tokensLabel)
  }

  return parts.join(' · ')
}
