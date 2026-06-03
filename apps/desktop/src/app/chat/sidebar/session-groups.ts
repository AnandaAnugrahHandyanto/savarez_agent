import type { GatewayAggregateState } from '@/gateway-aggregation'
import type { DashboardAgent, DashboardConversation, DashboardProject, SessionInfo } from '@/hermes'

export interface SidebarSessionGroup {
  id: string
  label: string
  path: null | string
  sessions: SessionInfo[]
}

export type SidebarControlSurfaceSectionId = 'gateways' | 'agents' | 'projects' | 'chats' | 'workspaces'

export interface SidebarControlSurfaceItem {
  id: string
  label: string
  meta?: string
  scope: SidebarEntityScope
}

export interface SidebarControlSurfaceSection {
  id: SidebarControlSurfaceSectionId
  items: SidebarControlSurfaceItem[]
  label: string
}

export type SidebarEntityScope =
  | { gatewayId: string; id: string; kind: 'gateway'; label: string; sessionIds: string[] }
  | { gatewayId?: string; id: string; kind: 'agent'; label: string; sessionIds: string[] }
  | { gatewayId?: string; id: string; kind: 'chat'; label: string; sessionIds: string[] }
  | { gatewayId?: string; id: string; kind: 'project'; label: string; sessionIds: string[] }
  | { gatewayId?: undefined; id: string; kind: 'workspace'; label: string; path: null | string; sessionIds: string[] }

interface SidebarControlSurfaceInput {
  agents: DashboardAgent[]
  gatewayStates?: GatewayAggregateState[]
  conversations: DashboardConversation[]
  projects: DashboardProject[]
  sessions: SessionInfo[]
}

const baseName = (path: string) =>
  path
    .replace(/[/\\]+$/, '')
    .split(/[/\\]/)
    .filter(Boolean)
    .pop()

const newestFirst = (a: SessionInfo, b: SessionInfo) =>
  (b.last_active || b.started_at || 0) - (a.last_active || a.started_at || 0)

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

function groupPriority(group: SidebarSessionGroup): number {
  if (group.id.includes(':') && group.path === null && group.id !== '__no_workspace__') {
    return 0
  }

  if (group.path) {
    return 1
  }

  return 2
}

export function sessionGroupsFor(sessions: SessionInfo[]): SidebarSessionGroup[] {
  const groups = new Map<string, SidebarSessionGroup>()

  for (const session of sessions) {
    const key = sessionGroupingLabel(session)
    const group = groups.get(key.id) ?? { ...key, sessions: [] }
    group.sessions.push(session)
    groups.set(key.id, group)
  }

  // Groups keep recency order inside each priority band (Telegram/chat topics
  // first, then workspaces, then unscoped/no-workspace rows), but rows *within*
  // a group sort by creation time so they don't reshuffle every time a message
  // lands — keeps muscle memory intact.
  for (const group of groups.values()) {
    group.sessions.sort((a, b) => b.started_at - a.started_at)
  }

  return [...groups.values()].sort((a, b) => groupPriority(a) - groupPriority(b))
}

function sessionIdSet(ids: readonly string[]): Set<string> {
  return new Set(ids.filter(Boolean))
}

function projectSessionIds(project: DashboardProject, conversationsById: Map<string, DashboardConversation>): string[] {
  return conversationsById.get(project.conversation_id)?.session_ids ?? []
}

function workspaceItemsFor(sessions: SessionInfo[]): SidebarControlSurfaceItem[] {
  return sessionGroupsFor([...sessions].sort(newestFirst))
    .filter(group => group.path)
    .map(group => ({
      id: `workspace:${group.id}`,
      label: group.label,
      meta: String(group.sessions.length),
      scope: {
        id: group.id,
        kind: 'workspace',
        label: group.label,
        path: group.path,
        sessionIds: group.sessions.map(s => s.id)
      }
    }))
}

export function sidebarControlSurfaceFor({
  agents,
  gatewayStates = [],
  conversations,
  projects,
  sessions
}: SidebarControlSurfaceInput): SidebarControlSurfaceSection[] {
  const conversationsById = new Map(conversations.map(conversation => [conversation.id, conversation]))
  const projectConversationIds = new Set(projects.map(project => project.conversation_id))
  const sessionIds = sessionIdSet(sessions.map(session => session.id))

  const sections: SidebarControlSurfaceSection[] = [
    {
      id: 'gateways',
      label: 'Gateways',
      items: gatewayStates.map(gateway => {
        const ids = sessions.filter(session => session.gateway_id === gateway.gateway_id).map(session => session.id)

        return {
          id: gateway.gateway_id,
          label: gateway.name,
          meta: gateway.ok ? gateway.state : `degraded · ${gateway.error || gateway.state}`,
          scope: { gatewayId: gateway.gateway_id, id: gateway.gateway_id, kind: 'gateway', label: gateway.name, sessionIds: ids }
        }
      })
    },
    {
      id: 'agents',
      label: 'Agents',
      items: agents.map(agent => ({
        id: agent.id,
        label: agent.name,
        meta: agent.gateway?.state ?? agent.provider ?? undefined,
        scope: { gatewayId: agent.gateway_id, id: agent.id, kind: 'agent', label: agent.name, sessionIds: [] }
      }))
    },
    {
      id: 'projects',
      label: 'Projects',
      items: projects.map(project => {
        const ids = projectSessionIds(project, conversationsById).filter(id => sessionIds.has(id))

        return {
          id: project.id,
          label: project.name || project.display_label || project.id,
          meta: ids.length ? String(ids.length) : undefined,
          scope: {
            id: project.id,
            gatewayId: project.gateway_id,
            kind: 'project',
            label: project.name || project.display_label || project.id,
            sessionIds: ids
          }
        }
      })
    },
    {
      id: 'chats',
      label: 'Chats',
      items: conversations
        .filter(conversation => !projectConversationIds.has(conversation.id))
        .map(conversation => {
          const ids = conversation.session_ids.filter(id => sessionIds.has(id))

          return {
            id: conversation.id,
            label: conversation.display_label || conversation.name || conversation.id,
            meta: ids.length ? String(ids.length) : conversation.platform,
            scope: {
              id: conversation.id,
              gatewayId: conversation.gateway_id,
              kind: 'chat',
              label: conversation.display_label || conversation.name || conversation.id,
              sessionIds: ids
            }
          }
        })
    },
    {
      id: 'workspaces',
      label: 'Workspaces',
      items: workspaceItemsFor(sessions)
    }
  ]

  return sections.map(section => ({ ...section, items: section.items.slice(0, 12) }))
}

export function sessionsForScope(sessions: SessionInfo[], scope: SidebarEntityScope | null): SessionInfo[] {
  if (!scope) {
    return sessions
  }

  if (scope.kind === 'workspace') {
    return sessions.filter(session => (session.cwd?.trim() || null) === scope.path)
  }

  if (!scope.sessionIds.length) {
    return []
  }

  const ids = sessionIdSet(scope.sessionIds)

  return sessions.filter(session => ids.has(session.id))
}
