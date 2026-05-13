import { shortCwd } from './paths.js'

const ANSI_CSI_RE = /\x1b\[[0-?]*[ -/]*[@-~]/g
const CONTROL_RE = /[\x00-\x1f\x7f]/g

export interface TerminalTitleParts {
  cwd?: string | null
  marker: string
  model?: string | null
  sessionTitle?: string | null
}

const cleanSegment = (value: null | string | undefined, max = 80) => {
  const cleaned = (value ?? '')
    .replace(ANSI_CSI_RE, '')
    .replace(CONTROL_RE, ' ')
    .replace(/\s+/g, ' ')
    .trim()

  return cleaned.length <= max ? cleaned : `${cleaned.slice(0, Math.max(0, max - 1))}…`
}

export const buildTerminalTitle = ({ cwd, marker, model, sessionTitle }: TerminalTitleParts) => {
  const title = cleanSegment(sessionTitle, 48)
  const shortModel = cleanSegment(model?.replace(/^.*\//, ''), 80)
  const shortPath = cwd ? shortCwd(cwd, 24) : ''
  const parts = [title || shortModel, title && shortModel ? shortModel : '', shortPath].filter(Boolean)

  return parts.length ? `${marker} ${parts.join(' · ')}` : 'Hermes'
}
