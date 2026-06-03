import type { SessionInfo } from '@/hermes'

export interface SidebarSessionGroup {
  id: string
  label: string
  path: null | string
  sessions: SessionInfo[]
}

const baseName = (path: string) =>
  path
    .replace(/[/\\]+$/, '')
    .split(/[/\\]/)
    .filter(Boolean)
    .pop()

export function sessionGroupingLabel(session: SessionInfo): { id: string; label: string; path: null | string } {
  const originLabel = session.origin?.display_label?.trim()
  const originGroupKey = session.origin?.group_key?.trim()

  if (originLabel && originGroupKey) {
    return { id: originGroupKey, label: originLabel, path: null }
  }

  const path = session.cwd?.trim() || ''
  const id = path || '__no_workspace__'
  const label = baseName(path) || path || 'No workspace'

  return { id, label, path: path || null }
}

export function sessionGroupsFor(sessions: SessionInfo[]): SidebarSessionGroup[] {
  const groups = new Map<string, SidebarSessionGroup>()

  for (const session of sessions) {
    const key = sessionGroupingLabel(session)
    const group = groups.get(key.id) ?? { ...key, sessions: [] }
    group.sessions.push(session)
    groups.set(key.id, group)
  }

  // Groups keep recency order (Map insertion = first-seen in the recency-sorted
  // input, so an active project/topic floats up), but rows *within* a group sort
  // by creation time so they don't reshuffle every time a message lands — keeps
  // muscle memory intact.
  for (const group of groups.values()) {
    group.sessions.sort((a, b) => b.started_at - a.started_at)
  }

  return [...groups.values()]
}
