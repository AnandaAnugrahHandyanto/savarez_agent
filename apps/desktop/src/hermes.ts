import { JsonRpcGatewayClient } from '@hermes/shared'

import { type AggregatedGatewayReadModel, aggregateGatewayReadModels, type GatewayReadResult } from '@/gateway-aggregation'
import type { DesktopConnectionRegistryEntry } from '@/global'
import type {
  ActionResponse,
  ActionStatusResponse,
  AnalyticsResponse,
  AudioSpeakResponse,
  AudioTranscriptionResponse,
  AuxiliaryModelsResponse,
  ConfigSchemaResponse,
  CronJob,
  CronJobCreatePayload,
  CronJobUpdates,
  DashboardAgentsResponse,
  DashboardConversationsResponse,
  DashboardProjectsResponse,
  ElevenLabsVoicesResponse,
  EnvVarInfo,
  HermesConfig,
  HermesConfigRecord,
  LogsResponse,
  MessagingPlatformsResponse,
  MessagingPlatformTestResponse,
  MessagingPlatformUpdate,
  ModelAssignmentRequest,
  ModelAssignmentResponse,
  ModelInfoResponse,
  ModelOptionsResponse,
  OAuthPollResponse,
  OAuthProvidersResponse,
  OAuthStartResponse,
  OAuthSubmitResponse,
  PaginatedSessions,
  ProfileCreatePayload,
  ProfileSetupCommand,
  ProfileSoul,
  ProfilesResponse,
  SessionMessagesResponse,
  SessionSearchResponse,
  SkillInfo,
  StatusResponse,
  ToolsetConfig,
  ToolsetInfo
} from '@/types/hermes'

const DEFAULT_GATEWAY_REQUEST_TIMEOUT_MS = 30_000

export interface KanbanBoardSummary {
  archived?: boolean
  counts?: Record<string, number>
  is_current?: boolean
  name?: string
  slug: string
  total?: number
}

export interface KanbanBoardsResponse {
  boards: KanbanBoardSummary[]
  current?: string
}

export interface KanbanBoardResponse {
  columns: Array<{ name: string; tasks: unknown[] }>
  [key: string]: unknown
}

export type {
  ActionResponse,
  ActionStatusResponse,
  AnalyticsDailyEntry,
  AnalyticsModelEntry,
  AnalyticsResponse,
  AnalyticsSkillEntry,
  AnalyticsSkillsSummary,
  AnalyticsTotals,
  AudioSpeakResponse,
  AudioTranscriptionResponse,
  AuxiliaryModelsResponse,
  ConfigFieldSchema,
  ConfigSchemaResponse,
  CronJob,
  CronJobCreatePayload,
  CronJobSchedule,
  CronJobUpdates,
  DashboardAgent,
  DashboardAgentsResponse,
  DashboardConversation,
  DashboardConversationsResponse,
  DashboardGatewaySummary,
  DashboardProject,
  DashboardProjectsResponse,
  ElevenLabsVoice,
  ElevenLabsVoicesResponse,
  EnvVarInfo,
  GatewayReadyPayload,
  HermesConfig,
  HermesConfigRecord,
  LogsResponse,
  MessagingEnvVarInfo,
  MessagingHomeChannel,
  MessagingPlatformInfo,
  MessagingPlatformsResponse,
  MessagingPlatformTestResponse,
  MessagingPlatformUpdate,
  ModelAssignmentRequest,
  ModelAssignmentResponse,
  ModelInfoResponse,
  ModelOptionProvider,
  ModelOptionsResponse,
  PaginatedSessions,
  ProfileCreatePayload,
  ProfileInfo,
  ProfileSetupCommand,
  ProfileSoul,
  ProfilesResponse,
  RpcEvent,
  SessionCreateResponse,
  SessionInfo,
  SessionMessage,
  SessionMessagesResponse,
  SessionResumeResponse,
  SessionRuntimeInfo,
  SessionSearchResponse,
  SessionSearchResult,
  SkillInfo,
  StatusResponse,
  ToolsetConfig,
  ToolsetInfo
} from '@/types/hermes'

export class HermesGateway extends JsonRpcGatewayClient {
  constructor() {
    super({
      closedErrorMessage: 'Hermes gateway connection closed',
      connectErrorMessage: 'Could not connect to Hermes gateway',
      createRequestId: nextId => nextId,
      notConnectedErrorMessage: 'Hermes gateway is not connected',
      requestTimeoutMs: DEFAULT_GATEWAY_REQUEST_TIMEOUT_MS
    })
  }
}

export async function listSessions(
  limit = 40,
  minMessages = 0,
  archived: 'exclude' | 'include' | 'only' = 'exclude',
  order: 'created' | 'recent' = 'recent',
  gatewayId?: string
): Promise<PaginatedSessions> {
  const result = await window.hermesDesktop.api<PaginatedSessions>({
    gatewayId,
    path: `/api/sessions?limit=${limit}&offset=0&min_messages=${Math.max(0, minMessages)}&archived=${archived}&order=${order}`
  })

  return {
    ...result,
    sessions: result.sessions.slice(0, limit),
    offset: 0
  }
}

export function listAgents(gatewayId?: string): Promise<DashboardAgentsResponse> {
  return window.hermesDesktop.api<DashboardAgentsResponse>({
    gatewayId,
    path: '/api/agents'
  })
}

export function listConversations(gatewayId?: string): Promise<DashboardConversationsResponse> {
  return window.hermesDesktop.api<DashboardConversationsResponse>({
    gatewayId,
    path: '/api/conversations'
  })
}

export function listProjects(gatewayId?: string): Promise<DashboardProjectsResponse> {
  return window.hermesDesktop.api<DashboardProjectsResponse>({
    gatewayId,
    path: '/api/projects'
  })
}

const apiErrorMessage = (error: unknown) => (error instanceof Error ? error.message : String(error))

interface OptionalApiError {
  __hermesOptionalApiError: string
}

const isOptionalApiError = (value: unknown): value is OptionalApiError =>
  Boolean(
    value &&
      typeof value === 'object' &&
      '__hermesOptionalApiError' in value &&
      typeof (value as OptionalApiError).__hermesOptionalApiError === 'string'
  )

async function readOptionalGatewayApi<T>(gatewayId: string, path: string): Promise<T | OptionalApiError> {
  return window.hermesDesktop.api<T | OptionalApiError>({
    gatewayId,
    optional: true,
    path
  })
}

async function readOptionalGatewayData<T>(
  label: 'agents' | 'conversations' | 'projects',
  read: () => Promise<T | OptionalApiError>,
  fallback: T
): Promise<{ error?: string; label: 'agents' | 'conversations' | 'projects'; value: T }> {
  try {
    const value = await read()

    if (isOptionalApiError(value)) {
      return { error: value.__hermesOptionalApiError, label, value: fallback }
    }

    return { label, value }
  } catch (error) {
    return { error: apiErrorMessage(error), label, value: fallback }
  }
}

async function readGatewayConnection(connection: DesktopConnectionRegistryEntry, limit: number): Promise<GatewayReadResult> {
  try {
    const [status, sessions, agents, conversations, projects] = await Promise.all([
      getStatus(connection.id),
      listSessions(limit, 1, 'exclude', 'recent', connection.id),
      readOptionalGatewayData('agents', () => readOptionalGatewayApi(connection.id, '/api/agents'), { agents: [] }),
      readOptionalGatewayData('conversations', () => readOptionalGatewayApi(connection.id, '/api/conversations'), {
        conversations: []
      }),
      readOptionalGatewayData('projects', () => readOptionalGatewayApi(connection.id, '/api/projects'), { projects: [] })
    ])

    const errors: GatewayReadResult['errors'] = {}

    for (const result of [agents, conversations, projects]) {
      if (result.error) {
        errors[result.label] = result.error
      }
    }

    return {
      agents: agents.value,
      connection,
      conversations: conversations.value,
      errors: Object.keys(errors).length ? errors : undefined,
      projects: projects.value,
      sessions,
      status
    }
  } catch (error) {
    return { connection, error: apiErrorMessage(error) }
  }
}

export async function listAggregatedGatewayData(limit = 40): Promise<AggregatedGatewayReadModel> {
  const config = await window.hermesDesktop.getConnectionConfig()
  const readableConnections = config.connections.filter(connection => connection.mode === 'local' || connection.tokenSet)
  const connections = readableConnections.length ? readableConnections : config.connections
  const results = await Promise.all(connections.map(connection => readGatewayConnection(connection, limit)))

  return aggregateGatewayReadModels(results)
}

export function setSessionArchived(id: string, archived: boolean): Promise<{ ok: boolean }> {
  return window.hermesDesktop.api<{ ok: boolean }>({
    path: `/api/sessions/${encodeURIComponent(id)}`,
    method: 'PATCH',
    body: { archived }
  })
}

export function searchSessions(query: string): Promise<SessionSearchResponse> {
  return window.hermesDesktop.api<SessionSearchResponse>({
    path: `/api/sessions/search?q=${encodeURIComponent(query)}`
  })
}

export function getSessionMessages(id: string): Promise<SessionMessagesResponse> {
  return window.hermesDesktop.api<SessionMessagesResponse>({
    path: `/api/sessions/${encodeURIComponent(id)}/messages`
  })
}

export function deleteSession(id: string): Promise<{ ok: boolean }> {
  return window.hermesDesktop.api<{ ok: boolean }>({
    path: `/api/sessions/${encodeURIComponent(id)}`,
    method: 'DELETE'
  })
}

export function renameSession(id: string, title: string): Promise<{ ok: boolean; title: string }> {
  return window.hermesDesktop.api<{ ok: boolean; title: string }>({
    path: `/api/sessions/${encodeURIComponent(id)}`,
    method: 'PATCH',
    body: { title }
  })
}

export function getGlobalModelInfo(gatewayId?: string): Promise<ModelInfoResponse> {
  return window.hermesDesktop.api<ModelInfoResponse>({
    gatewayId,
    path: '/api/model/info'
  })
}

export function getStatus(gatewayId?: string): Promise<StatusResponse> {
  return window.hermesDesktop.api<StatusResponse>({
    gatewayId,
    path: '/api/status'
  })
}

export function getLogs(params: {
  component?: string
  file?: string
  level?: string
  lines?: number
}): Promise<LogsResponse> {
  const query = new URLSearchParams()

  if (params.file) {
    query.set('file', params.file)
  }

  if (typeof params.lines === 'number') {
    query.set('lines', String(params.lines))
  }

  if (params.level && params.level !== 'ALL') {
    query.set('level', params.level)
  }

  if (params.component && params.component !== 'all') {
    query.set('component', params.component)
  }

  const suffix = query.toString()

  return window.hermesDesktop.api<LogsResponse>({
    path: suffix ? `/api/logs?${suffix}` : '/api/logs'
  })
}

export function getHermesConfig(gatewayId?: string): Promise<HermesConfig> {
  return window.hermesDesktop.api<HermesConfig>({
    gatewayId,
    path: '/api/config'
  })
}

export function getHermesConfigRecord(gatewayId?: string): Promise<HermesConfigRecord> {
  return window.hermesDesktop.api<HermesConfigRecord>({
    gatewayId,
    path: '/api/config'
  })
}

export function getHermesConfigDefaults(gatewayId?: string): Promise<HermesConfigRecord> {
  return window.hermesDesktop.api<HermesConfigRecord>({
    gatewayId,
    path: '/api/config/defaults'
  })
}

export function getHermesConfigSchema(gatewayId?: string): Promise<ConfigSchemaResponse> {
  return window.hermesDesktop.api<ConfigSchemaResponse>({
    gatewayId,
    path: '/api/config/schema'
  })
}

export function saveHermesConfig(config: HermesConfigRecord, gatewayId?: string): Promise<{ ok: boolean }> {
  return window.hermesDesktop.api<{ ok: boolean }>({
    body: { config },
    gatewayId,
    method: 'PUT',
    path: '/api/config'
  })
}

export function listKanbanBoards(gatewayId?: string): Promise<KanbanBoardsResponse> {
  return window.hermesDesktop.api<KanbanBoardsResponse>({
    gatewayId,
    path: '/api/plugins/kanban/boards'
  })
}

export function getKanbanBoard({
  board,
  gatewayId,
  includeArchived,
  tenant
}: {
  board?: string
  gatewayId?: string
  includeArchived?: boolean
  tenant?: string
} = {}): Promise<KanbanBoardResponse> {
  const query = new URLSearchParams()

  if (board) {
    query.set('board', board)
  }

  if (tenant) {
    query.set('tenant', tenant)
  }

  if (includeArchived) {
    query.set('include_archived', 'true')
  }

  const suffix = query.toString()

  return window.hermesDesktop.api<KanbanBoardResponse>({
    gatewayId,
    path: suffix ? `/api/plugins/kanban/board?${suffix}` : '/api/plugins/kanban/board'
  })
}

export function getEnvVars(gatewayId?: string): Promise<Record<string, EnvVarInfo>> {
  return window.hermesDesktop.api<Record<string, EnvVarInfo>>({
    gatewayId,
    path: '/api/env'
  })
}

export function setEnvVar(key: string, value: string, gatewayId?: string): Promise<{ ok: boolean }> {
  return window.hermesDesktop.api<{ ok: boolean }>({
    body: { key, value },
    gatewayId,
    method: 'PUT',
    path: '/api/env'
  })
}

export function validateProviderCredential(
  key: string,
  value: string,
  gatewayId?: string
): Promise<{ ok: boolean; reachable: boolean; message: string }> {
  return window.hermesDesktop.api<{ ok: boolean; reachable: boolean; message: string }>({
    body: { key, value },
    gatewayId,
    method: 'POST',
    path: '/api/providers/validate'
  })
}

export function deleteEnvVar(key: string, gatewayId?: string): Promise<{ ok: boolean }> {
  return window.hermesDesktop.api<{ ok: boolean }>({
    body: { key },
    gatewayId,
    method: 'DELETE',
    path: '/api/env'
  })
}

export function revealEnvVar(key: string, gatewayId?: string): Promise<{ key: string; value: string }> {
  return window.hermesDesktop.api<{ key: string; value: string }>({
    body: { key },
    gatewayId,
    method: 'POST',
    path: '/api/env/reveal'
  })
}

export function listOAuthProviders(): Promise<OAuthProvidersResponse> {
  return window.hermesDesktop.api<OAuthProvidersResponse>({
    path: '/api/providers/oauth'
  })
}

export function startOAuthLogin(providerId: string): Promise<OAuthStartResponse> {
  return window.hermesDesktop.api<OAuthStartResponse>({
    path: `/api/providers/oauth/${encodeURIComponent(providerId)}/start`,
    method: 'POST',
    body: {}
  })
}

export function submitOAuthCode(providerId: string, sessionId: string, code: string): Promise<OAuthSubmitResponse> {
  return window.hermesDesktop.api<OAuthSubmitResponse>({
    path: `/api/providers/oauth/${encodeURIComponent(providerId)}/submit`,
    method: 'POST',
    body: { session_id: sessionId, code }
  })
}

export function pollOAuthSession(providerId: string, sessionId: string): Promise<OAuthPollResponse> {
  return window.hermesDesktop.api<OAuthPollResponse>({
    path: `/api/providers/oauth/${encodeURIComponent(providerId)}/poll/${encodeURIComponent(sessionId)}`
  })
}

export function cancelOAuthSession(sessionId: string): Promise<{ ok: boolean }> {
  return window.hermesDesktop.api<{ ok: boolean }>({
    path: `/api/providers/oauth/sessions/${encodeURIComponent(sessionId)}`,
    method: 'DELETE'
  })
}

export function getSkills(): Promise<SkillInfo[]> {
  return window.hermesDesktop.api<SkillInfo[]>({
    path: '/api/skills'
  })
}

export function toggleSkill(name: string, enabled: boolean): Promise<{ ok: boolean; name: string; enabled: boolean }> {
  return window.hermesDesktop.api<{ ok: boolean; name: string; enabled: boolean }>({
    path: '/api/skills/toggle',
    method: 'PUT',
    body: { name, enabled }
  })
}

export function getToolsets(gatewayId?: string): Promise<ToolsetInfo[]> {
  return window.hermesDesktop.api<ToolsetInfo[]>({
    gatewayId,
    path: '/api/tools/toolsets'
  })
}

export function toggleToolset(
  name: string,
  enabled: boolean,
  gatewayId?: string
): Promise<{ ok: boolean; name: string; enabled: boolean }> {
  return window.hermesDesktop.api<{ ok: boolean; name: string; enabled: boolean }>({
    body: { enabled },
    gatewayId,
    method: 'PUT',
    path: `/api/tools/toolsets/${encodeURIComponent(name)}`
  })
}

export function getToolsetConfig(name: string, gatewayId?: string): Promise<ToolsetConfig> {
  return window.hermesDesktop.api<ToolsetConfig>({
    gatewayId,
    path: `/api/tools/toolsets/${encodeURIComponent(name)}/config`
  })
}

export function selectToolsetProvider(
  name: string,
  provider: string,
  gatewayId?: string
): Promise<{ ok: boolean; name: string; provider: string }> {
  return window.hermesDesktop.api<{ ok: boolean; name: string; provider: string }>({
    body: { provider },
    gatewayId,
    method: 'PUT',
    path: `/api/tools/toolsets/${encodeURIComponent(name)}/provider`
  })
}

export function getMessagingPlatforms(): Promise<MessagingPlatformsResponse> {
  return window.hermesDesktop.api<MessagingPlatformsResponse>({
    path: '/api/messaging/platforms'
  })
}

export function updateMessagingPlatform(
  platformId: string,
  body: MessagingPlatformUpdate
): Promise<{ ok: boolean; platform: string }> {
  return window.hermesDesktop.api<{ ok: boolean; platform: string }>({
    path: `/api/messaging/platforms/${encodeURIComponent(platformId)}`,
    method: 'PUT',
    body
  })
}

export function testMessagingPlatform(platformId: string): Promise<MessagingPlatformTestResponse> {
  return window.hermesDesktop.api<MessagingPlatformTestResponse>({
    path: `/api/messaging/platforms/${encodeURIComponent(platformId)}/test`,
    method: 'POST'
  })
}

export function getCronJobs(): Promise<CronJob[]> {
  return window.hermesDesktop.api<CronJob[]>({
    path: '/api/cron/jobs'
  })
}

export function getCronJob(jobId: string): Promise<CronJob> {
  return window.hermesDesktop.api<CronJob>({
    path: `/api/cron/jobs/${encodeURIComponent(jobId)}`
  })
}

export function createCronJob(body: CronJobCreatePayload): Promise<CronJob> {
  return window.hermesDesktop.api<CronJob>({
    path: '/api/cron/jobs',
    method: 'POST',
    body
  })
}

export function updateCronJob(jobId: string, updates: CronJobUpdates): Promise<CronJob> {
  return window.hermesDesktop.api<CronJob>({
    path: `/api/cron/jobs/${encodeURIComponent(jobId)}`,
    method: 'PUT',
    body: { updates }
  })
}

export function pauseCronJob(jobId: string): Promise<CronJob> {
  return window.hermesDesktop.api<CronJob>({
    path: `/api/cron/jobs/${encodeURIComponent(jobId)}/pause`,
    method: 'POST'
  })
}

export function resumeCronJob(jobId: string): Promise<CronJob> {
  return window.hermesDesktop.api<CronJob>({
    path: `/api/cron/jobs/${encodeURIComponent(jobId)}/resume`,
    method: 'POST'
  })
}

export function triggerCronJob(jobId: string): Promise<CronJob> {
  return window.hermesDesktop.api<CronJob>({
    path: `/api/cron/jobs/${encodeURIComponent(jobId)}/trigger`,
    method: 'POST'
  })
}

export function deleteCronJob(jobId: string): Promise<{ ok: boolean }> {
  return window.hermesDesktop.api<{ ok: boolean }>({
    path: `/api/cron/jobs/${encodeURIComponent(jobId)}`,
    method: 'DELETE'
  })
}

export function getProfiles(): Promise<ProfilesResponse> {
  return window.hermesDesktop.api<ProfilesResponse>({
    path: '/api/profiles'
  })
}

export function createProfile(body: ProfileCreatePayload): Promise<{ name: string; ok: boolean; path: string }> {
  return window.hermesDesktop.api<{ name: string; ok: boolean; path: string }>({
    path: '/api/profiles',
    method: 'POST',
    body
  })
}

export function renameProfile(name: string, newName: string): Promise<{ name: string; ok: boolean; path: string }> {
  return window.hermesDesktop.api<{ name: string; ok: boolean; path: string }>({
    path: `/api/profiles/${encodeURIComponent(name)}`,
    method: 'PATCH',
    body: { new_name: newName }
  })
}

export function deleteProfile(name: string): Promise<{ ok: boolean; path: string }> {
  return window.hermesDesktop.api<{ ok: boolean; path: string }>({
    path: `/api/profiles/${encodeURIComponent(name)}`,
    method: 'DELETE'
  })
}

export function getProfileSoul(name: string): Promise<ProfileSoul> {
  return window.hermesDesktop.api<ProfileSoul>({
    path: `/api/profiles/${encodeURIComponent(name)}/soul`
  })
}

export function updateProfileSoul(name: string, content: string): Promise<{ ok: boolean }> {
  return window.hermesDesktop.api<{ ok: boolean }>({
    path: `/api/profiles/${encodeURIComponent(name)}/soul`,
    method: 'PUT',
    body: { content }
  })
}

export function getProfileSetupCommand(name: string): Promise<ProfileSetupCommand> {
  return window.hermesDesktop.api<ProfileSetupCommand>({
    path: `/api/profiles/${encodeURIComponent(name)}/setup-command`
  })
}

export function getUsageAnalytics(days = 30): Promise<AnalyticsResponse> {
  return window.hermesDesktop.api<AnalyticsResponse>({
    path: `/api/analytics/usage?days=${Math.max(1, Math.floor(days))}`
  })
}

export function getGlobalModelOptions(gatewayId?: string): Promise<ModelOptionsResponse> {
  return window.hermesDesktop.api<ModelOptionsResponse>({
    gatewayId,
    path: '/api/model/options'
  })
}

export interface RecommendedDefaultModel {
  provider: string
  model: string
  /** True/false for Nous (free vs paid tier); null for other providers. */
  free_tier: boolean | null
}

// Recommended default model for a freshly-authenticated provider. Mirrors the
// curation `hermes model` does — for Nous it honors the free/paid tier so a
// free user gets a free model instead of a paid default.
export function getRecommendedDefaultModel(provider: string): Promise<RecommendedDefaultModel> {
  return window.hermesDesktop.api<RecommendedDefaultModel>({
    path: `/api/model/recommended-default?provider=${encodeURIComponent(provider)}`
  })
}

export function setGlobalModel(
  provider: string,
  model: string
): Promise<{ ok: boolean; provider: string; model: string }> {
  return window.hermesDesktop.api<{ ok: boolean; provider: string; model: string }>({
    path: '/api/model/set',
    method: 'POST',
    body: {
      scope: 'main',
      provider,
      model
    }
  })
}

export function getAuxiliaryModels(gatewayId?: string): Promise<AuxiliaryModelsResponse> {
  return window.hermesDesktop.api<AuxiliaryModelsResponse>({
    gatewayId,
    path: '/api/model/auxiliary'
  })
}

export function setModelAssignment(body: ModelAssignmentRequest, gatewayId?: string): Promise<ModelAssignmentResponse> {
  return window.hermesDesktop.api<ModelAssignmentResponse>({
    body,
    gatewayId,
    method: 'POST',
    path: '/api/model/set'
  })
}

export function restartGateway(): Promise<ActionResponse> {
  return window.hermesDesktop.api<ActionResponse>({
    path: '/api/gateway/restart',
    method: 'POST'
  })
}

export function updateHermes(): Promise<ActionResponse> {
  return window.hermesDesktop.api<ActionResponse>({
    path: '/api/hermes/update',
    method: 'POST'
  })
}

export function getActionStatus(name: string, lines = 200): Promise<ActionStatusResponse> {
  return window.hermesDesktop.api<ActionStatusResponse>({
    path: `/api/actions/${encodeURIComponent(name)}/status?lines=${Math.max(1, lines)}`
  })
}

export function transcribeAudio(dataUrl: string, mimeType?: string): Promise<AudioTranscriptionResponse> {
  return window.hermesDesktop.api<AudioTranscriptionResponse>({
    path: '/api/audio/transcribe',
    method: 'POST',
    body: {
      data_url: dataUrl,
      mime_type: mimeType
    }
  })
}

export function speakText(text: string): Promise<AudioSpeakResponse> {
  return window.hermesDesktop.api<AudioSpeakResponse>({
    path: '/api/audio/speak',
    method: 'POST',
    body: { text }
  })
}

export function getElevenLabsVoices(): Promise<ElevenLabsVoicesResponse> {
  return window.hermesDesktop.api<ElevenLabsVoicesResponse>({
    path: '/api/audio/elevenlabs/voices'
  })
}
