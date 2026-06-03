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
import type { DesktopConnectionRegistryEntry } from '@/global'

export interface GatewayReadResult {
  agents?: DashboardAgentsResponse
  connection: DesktopConnectionRegistryEntry
  conversations?: DashboardConversationsResponse
  error?: string
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

export function aggregateGatewayReadModels(results: GatewayReadResult[]): AggregatedGatewayReadModel {
  const agents: DashboardAgent[] = []
  const conversations: DashboardConversation[] = []
  const projects: DashboardProject[] = []
  const sessions: SessionInfo[] = []
  const gatewayStates: GatewayAggregateState[] = []
  let sessionsTotal = 0

  for (const result of results) {
    const gatewayId = result.connection.id
    const state = result.error
      ? 'degraded'
      : result.status?.gateway_state ?? result.status?.gateway?.state ?? (result.status ? 'running' : 'unknown')

    gatewayStates.push({
      error: result.error,
      gateway_id: gatewayId,
      name: result.connection.name || gatewayId,
      ok: !result.error,
      state: asText(state) || 'unknown'
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
