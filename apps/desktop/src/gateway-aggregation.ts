import type { DesktopConnectionRegistryEntry } from '@/global'
import type {
  DashboardAgent,
  DashboardAgentsResponse,
  DashboardConversation,
  DashboardConversationsResponse,
  DashboardProject,
  DashboardProjectsResponse,
  PaginatedSessions,
  SessionInfo,
  StatusResponse
} from '@/types/hermes'

export interface GatewayReadResult {
  agents?: DashboardAgentsResponse
  connection: DesktopConnectionRegistryEntry
  conversations?: DashboardConversationsResponse
  error?: string
  errors?: Partial<Record<'agents' | 'conversations' | 'projects' | 'sessions' | 'status', string>>
  projects?: DashboardProjectsResponse
  sessions?: PaginatedSessions
  status?: StatusResponse
}

export interface GatewayAggregateState {
  error?: string
  gateway_id: string
  name: string
  ok: boolean
  state: string
}

export interface AggregatedGatewayReadModel {
  agents: DashboardAgent[]
  conversations: DashboardConversation[]
  gatewayStates: GatewayAggregateState[]
  projects: DashboardProject[]
  sessions: SessionInfo[]
  sessionsTotal: number
}

const compositeId = (gatewayId: string, id: string) => `${gatewayId}::${id}`
const asText = (value: unknown) => (typeof value === 'string' ? value : '')

function normalizeGatewayState(statusState: unknown, error?: string): string {
  if (error) {
    const lower = error.toLowerCase()

    return lower.includes('offline') || lower.includes('unreachable') || lower.includes('connection') || lower.includes('fetch')
      ? 'offline'
      : 'degraded'
  }

  const state = asText(statusState).toLowerCase()

  if (state === 'running' || state === 'open' || state === 'ready' || state === 'connected') {
    return 'connected'
  }

  if (state === 'stopped' || state === 'offline' || state === 'closed' || state === 'error') {
    return 'offline'
  }

  return state || 'unknown'
}

function partialErrorText(errors: GatewayReadResult['errors']): string | undefined {
  const parts = Object.entries(errors ?? {})
    .filter((entry): entry is [string, string] => Boolean(entry[1]))
    .map(([key, value]) => `${key}: ${value}`)

  return parts.length ? parts.join('; ') : undefined
}

export function aggregateGatewayReadModels(results: GatewayReadResult[]): AggregatedGatewayReadModel {
  const agents: DashboardAgent[] = []
  const conversations: DashboardConversation[] = []
  const projects: DashboardProject[] = []
  const sessions: SessionInfo[] = []
  const gatewayStates: GatewayAggregateState[] = []
  let sessionsTotal = 0

  for (const result of results) {
    const gatewayId = result.connection.id
    const error = result.error || partialErrorText(result.errors)

    const state = normalizeGatewayState(
      result.status?.gateway_state ?? result.status?.gateway?.state ?? (result.status ? 'running' : 'unknown'),
      error
    )

    gatewayStates.push({
      gateway_id: gatewayId,
      name: result.connection.name || gatewayId,
      ok: !error,
      state,
      ...(error ? { error } : {})
    })

    for (const session of result.sessions?.sessions ?? []) {
      sessions.push({
        ...session,
        _lineage_root_id: session._lineage_root_id ? compositeId(gatewayId, session._lineage_root_id) : session._lineage_root_id,
        gateway_id: gatewayId,
        id: compositeId(gatewayId, session.id)
      })
    }

    sessionsTotal += result.sessions?.total ?? result.sessions?.sessions?.length ?? 0

    for (const agent of result.agents?.agents ?? []) {
      agents.push({
        ...agent,
        gateway_id: gatewayId,
        id: compositeId(gatewayId, agent.id)
      })
    }

    for (const conversation of result.conversations?.conversations ?? []) {
      conversations.push({
        ...conversation,
        gateway_id: gatewayId,
        id: compositeId(gatewayId, conversation.id),
        session_ids: conversation.session_ids.map(id => compositeId(gatewayId, id))
      })
    }

    for (const project of result.projects?.projects ?? []) {
      projects.push({
        ...project,
        conversation_id: compositeId(gatewayId, project.conversation_id),
        gateway_id: gatewayId,
        id: compositeId(gatewayId, project.id)
      })
    }
  }

  return { agents, conversations, gatewayStates, projects, sessions, sessionsTotal }
}
