import type { DesktopConnectionRegistryEntry } from '@/global'
import type { DashboardProject, SessionInfo } from '@/types/hermes'

export interface RouteSelectionInput {
  connections: DesktopConnectionRegistryEntry[]
  projects: DashboardProject[]
  selectedGatewayId?: null | string
  selectedProjectId?: null | string
}

export type RouteSelectionResult =
  | {
      ok: true
      gatewayId: string
      projectId?: string
      target?: {
        chat_id: string
        conversation_id: string
        platform: string
        topic_id: string
      }
    }
  | {
      ok: false
      gatewayIds?: string[]
      message: string
      reason: 'ambiguous-project' | 'missing-gateway' | 'unknown-gateway' | 'unknown-project' | 'wrong-gateway'
    }

export interface RouteRequestOptionsInput {
  gatewayId: string
  session?: SessionInfo | null
}

export interface RouteRequestOptions {
  gatewayId: string
  params: Record<string, unknown>
}

const compositePrefix = (gatewayId: string) => `${gatewayId}::`

export function stripGatewayCompositeId(id: string, gatewayId: string): string {
  return id.startsWith(compositePrefix(gatewayId)) ? id.slice(compositePrefix(gatewayId).length) : id
}

function baseProjectId(projectId: string): string {
  const [gatewayId, rest] = projectId.split('::', 2)

  return rest && gatewayId ? rest : projectId
}

function projectMatchesSelection(project: DashboardProject, selectedProjectId: string): boolean {
  if (project.id === selectedProjectId) {
    return true
  }

  return baseProjectId(project.id) === selectedProjectId
}

export function resolveRouteSelection({
  connections,
  projects,
  selectedGatewayId,
  selectedProjectId
}: RouteSelectionInput): RouteSelectionResult {
  const gatewayId = selectedGatewayId?.trim()

  if (!gatewayId) {
    return { ok: false, reason: 'missing-gateway', message: 'Select one gateway before sending.' }
  }

  if (!connections.some(connection => connection.id === gatewayId)) {
    return { ok: false, reason: 'unknown-gateway', message: `Selected gateway ${gatewayId} is not configured.` }
  }

  const projectId = selectedProjectId?.trim()

  if (!projectId) {
    return { ok: true, gatewayId }
  }

  const matches = projects.filter(project => projectMatchesSelection(project, projectId))

  if (!matches.length) {
    return { ok: false, reason: 'unknown-project', message: 'Selected project is no longer available.' }
  }

  const matchGatewayIds = [...new Set(matches.map(project => project.gateway_id).filter((id): id is string => Boolean(id)))]

  if (!projectId.includes('::') && matchGatewayIds.length > 1) {
    const label = matches[0]?.name || matches[0]?.display_label || projectId

    return {
      ok: false,
      reason: 'ambiguous-project',
      message: `Project ${label} exists on multiple gateways. Choose the gateway-specific project row before sending.`,
      gatewayIds: matchGatewayIds
    }
  }

  const project = matches.find(candidate => candidate.gateway_id === gatewayId)

  if (!project) {
    return {
      ok: false,
      reason: 'wrong-gateway',
      message: 'Selected project belongs to a different gateway. Choose a project from the selected gateway.'
    }
  }

  return {
    ok: true,
    gatewayId,
    projectId: project.id,
    target: {
      chat_id: project.chat_id,
      conversation_id: project.conversation_id,
      platform: project.platform,
      topic_id: project.topic_id
    }
  }
}

export function routeRequestOptionsForSession({ gatewayId, session }: RouteRequestOptionsInput): RouteRequestOptions {
  const params: Record<string, unknown> = {}

  if (session?.id) {
    params.session_id = stripGatewayCompositeId(session.id, gatewayId)
  }

  return { gatewayId, params }
}
