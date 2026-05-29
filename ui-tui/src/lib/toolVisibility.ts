import { parseToolTrailResultLine, splitToolDuration } from './text.js'

export type ToolEntryStatus = 'done' | 'error' | 'running'

export interface ToolTrailSection {
  label: string
  text: string
}

export interface ParsedToolTrailEntry {
  call: string
  detail: string
  duration: string
  mark: '✓' | '✗'
  sections: ToolTrailSection[]
  status: Exclude<ToolEntryStatus, 'running'>
}

export interface DelegationControlState {
  maxConcurrentChildren?: number | null
  maxSpawnDepth?: number | null
  paused: boolean
}

export interface DelegationControlSummary {
  capsLabel: string
  controlsHint: string
  titleSuffix: string
}

const SECTION_HEADER = /^(Args|Result|Error):$/

export const parseToolSections = (detail: string): ToolTrailSection[] => {
  const lines = detail.split('\n')
  const sections: ToolTrailSection[] = []
  let current: null | ToolTrailSection = null

  for (const line of lines) {
    const header = line.match(SECTION_HEADER)?.[1]

    if (header) {
      current = { label: header, text: '' }
      sections.push(current)

      continue
    }

    if (current) {
      current.text = current.text ? `${current.text}\n${line}` : line
    }
  }

  return sections.map(section => ({ ...section, text: section.text.trim() })).filter(section => section.text)
}

export const parseToolTrailEntry = (line: string): ParsedToolTrailEntry | null => {
  const parsed = parseToolTrailResultLine(line)

  if (!parsed) {
    return null
  }

  const { duration, label } = splitToolDuration(parsed.call)

  const mark = parsed.mark as '✓' | '✗'

  return {
    call: label,
    detail: parsed.detail,
    duration,
    mark,
    sections: parseToolSections(parsed.detail),
    status: mark === '✗' ? 'error' : 'done'
  }
}

export const shouldToolEntryAutoOpen = (entry: null | ParsedToolTrailEntry): boolean => entry?.status === 'error'

export const summarizeDelegationControls = (
  delegation: DelegationControlState,
  replayMode: boolean
): DelegationControlSummary => {
  const capsLabel = delegation.maxSpawnDepth
    ? `caps d${delegation.maxSpawnDepth}/${delegation.maxConcurrentChildren ?? '?'}`
    : ''

  return {
    capsLabel,
    controlsHint: replayMode ? ' · controls locked' : ` · x kill · X subtree · p ${delegation.paused ? 'resume' : 'pause'}`,
    titleSuffix: delegation.paused ? ' · ⏸ paused' : ''
  }
}
