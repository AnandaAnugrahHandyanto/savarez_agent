const CONNECTION_REGISTRY_SCHEMA_VERSION = 2
const DEFAULT_CONNECTION_KIND = 'hermes-dashboard'

function normalizeRemoteBaseUrl(rawUrl) {
  const value = String(rawUrl || '').trim()

  if (!value) {
    throw new Error('Remote gateway URL is required.')
  }

  let parsed
  try {
    parsed = new URL(value)
  } catch (error) {
    throw new Error(`Remote gateway URL is not valid: ${error.message}`)
  }

  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error(`Remote gateway URL must be http:// or https://, got ${parsed.protocol}`)
  }

  parsed.hash = ''
  parsed.search = ''
  parsed.pathname = parsed.pathname.replace(/\/+$/, '')

  return parsed.toString().replace(/\/+$/, '')
}

function tokenPreview(value) {
  const raw = String(value || '')

  if (!raw) {
    return null
  }

  return raw.length <= 8 ? 'set' : `...${raw.slice(-6)}`
}

function isPlainObject(value) {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function stableConnectionId(mode, index = 1) {
  return mode === 'remote' ? `remote-${index}` : 'local'
}

function normalizeConnection(candidate, fallbackIndex = 1) {
  if (!isPlainObject(candidate)) return null

  const mode = candidate.mode === 'remote' ? 'remote' : 'local'
  const id = String(candidate.id || stableConnectionId(mode, fallbackIndex)).trim() || stableConnectionId(mode, fallbackIndex)
  const baseUrl = mode === 'remote' ? String(candidate.baseUrl ?? candidate.url ?? '').trim() : ''

  return {
    id,
    name: String(candidate.name || (mode === 'remote' ? 'Remote gateway' : 'Local gateway')).trim(),
    kind: candidate.kind === DEFAULT_CONNECTION_KIND ? DEFAULT_CONNECTION_KIND : DEFAULT_CONNECTION_KIND,
    mode,
    baseUrl,
    token: candidate.token && typeof candidate.token === 'object' ? candidate.token : null
  }
}

function registryFromConnections(connections, activeConnectionId) {
  const safeConnections = connections.map((connection, index) => normalizeConnection(connection, index + 1)).filter(Boolean)
  const fallback = normalizeConnection({ mode: 'local' })
  const allConnections = safeConnections.length ? safeConnections : [fallback]
  const requestedActiveId = String(activeConnectionId || '').trim()
  const active = allConnections.find(connection => connection.id === requestedActiveId) || allConnections[0]

  return {
    schemaVersion: CONNECTION_REGISTRY_SCHEMA_VERSION,
    activeConnectionId: active.id,
    connections: allConnections
  }
}

function registryFromConnection(connection) {
  const normalized = normalizeConnection(connection) || normalizeConnection({ mode: 'local' })

  return registryFromConnections([normalized], normalized.id)
}

function migrateDesktopConnectionConfig(rawConfig = {}) {
  if (isPlainObject(rawConfig) && rawConfig.schemaVersion === CONNECTION_REGISTRY_SCHEMA_VERSION) {
    const connections = Array.isArray(rawConfig.connections)
      ? rawConfig.connections.map((connection, index) => normalizeConnection(connection, index + 1)).filter(Boolean)
      : []
    const fallback = normalizeConnection({ mode: rawConfig.mode === 'remote' ? 'remote' : 'local' })
    const safeConnections = connections.length ? connections : [fallback]
    const requestedActiveId = String(rawConfig.activeConnectionId || '').trim()
    const active = safeConnections.find(connection => connection.id === requestedActiveId) || safeConnections[0]

    return {
      schemaVersion: CONNECTION_REGISTRY_SCHEMA_VERSION,
      activeConnectionId: active.id,
      connections: safeConnections
    }
  }

  const legacyMode = rawConfig?.mode === 'remote' ? 'remote' : 'local'
  const legacyRemote = isPlainObject(rawConfig?.remote) ? rawConfig.remote : {}

  if (legacyMode === 'remote') {
    return registryFromConnection({
      id: 'remote-1',
      name: 'Remote gateway',
      kind: DEFAULT_CONNECTION_KIND,
      mode: 'remote',
      baseUrl: String(legacyRemote.url || '').trim(),
      token: legacyRemote.token && typeof legacyRemote.token === 'object' ? legacyRemote.token : null
    })
  }

  return registryFromConnection({
    id: 'local',
    name: 'Local gateway',
    kind: DEFAULT_CONNECTION_KIND,
    mode: 'local',
    baseUrl: String(legacyRemote.url || '').trim(),
    token: legacyRemote.token && typeof legacyRemote.token === 'object' ? legacyRemote.token : null
  })
}

function getActiveConnection(config) {
  const registry = migrateDesktopConnectionConfig(config)
  return registry.connections.find(connection => connection.id === registry.activeConnectionId) || registry.connections[0]
}

function sanitizeConnection(connection, decryptDesktopSecret) {
  const token = decryptDesktopSecret(connection.token)

  return {
    id: connection.id,
    name: connection.name,
    kind: DEFAULT_CONNECTION_KIND,
    mode: connection.mode,
    baseUrl: connection.baseUrl || '',
    tokenPreview: tokenPreview(token),
    tokenSet: Boolean(token)
  }
}

function sanitizeDesktopConnectionConfig(config, options = {}) {
  const decryptDesktopSecret = options.decryptDesktopSecret || (() => '')
  const registry = migrateDesktopConnectionConfig(config)
  const active = getActiveConnection(registry)
  const activeToken = decryptDesktopSecret(active.token)
  const remoteConnection =
    active.mode === 'remote' ? active : registry.connections.find(connection => connection.mode === 'remote')
  const remoteToken = remoteConnection ? decryptDesktopSecret(remoteConnection.token) : ''

  return {
    schemaVersion: CONNECTION_REGISTRY_SCHEMA_VERSION,
    activeConnectionId: active.id,
    connections: registry.connections.map(connection => sanitizeConnection(connection, decryptDesktopSecret)),
    mode: active.mode === 'remote' ? 'remote' : 'local',
    remoteUrl: String(remoteConnection?.baseUrl || ''),
    remoteTokenPreview: tokenPreview(remoteConnection ? remoteToken : activeToken),
    remoteTokenSet: Boolean(remoteConnection ? remoteToken : activeToken),
    envOverride: Boolean(options.envOverride)
  }
}

function coerceDesktopConnectionConfig(input = {}, existing = {}, options = {}) {
  const encryptDesktopSecret = options.encryptDesktopSecret || (() => null)
  const decryptDesktopSecret = options.decryptDesktopSecret || (() => '')
  const persistToken = options.persistToken !== false
  const registry = migrateDesktopConnectionConfig(existing)
  const mode = input.mode === 'remote' ? 'remote' : 'local'
  const active = getActiveConnection(registry)
  const existingRemote =
    active.mode === 'remote' ? active : registry.connections.find(connection => connection.mode === 'remote')
  const remoteUrl = String(input.remoteUrl ?? existingRemote?.baseUrl ?? '').trim()
  const incomingToken = typeof input.remoteToken === 'string' ? input.remoteToken.trim() : ''
  const existingToken = existingRemote?.token || null
  const remoteToken = incomingToken
    ? persistToken
      ? encryptDesktopSecret(incomingToken)
      : { encoding: 'plain', value: incomingToken }
    : existingToken

  const localConnection = registry.connections.find(connection => connection.mode === 'local') || {
    id: 'local',
    name: 'Local gateway',
    kind: DEFAULT_CONNECTION_KIND,
    mode: 'local',
    baseUrl: '',
    token: null
  }
  const connections = registry.connections.filter(connection => connection.mode !== 'local' && connection.mode !== 'remote')

  if (mode === 'remote') {
    const baseUrl = normalizeRemoteBaseUrl(remoteUrl)
    if (!decryptDesktopSecret(remoteToken)) {
      throw new Error('Remote gateway session token is required.')
    }
    const remoteConnection = {
      id: existingRemote?.id || 'remote-1',
      name: existingRemote?.name || 'Remote gateway',
      kind: DEFAULT_CONNECTION_KIND,
      mode: 'remote',
      baseUrl,
      token: remoteToken
    }

    return registryFromConnections([remoteConnection, ...connections], remoteConnection.id)
  }

  const remoteConnection = existingRemote
    ? {
        ...existingRemote,
        baseUrl: remoteUrl ? normalizeRemoteBaseUrl(remoteUrl) : String(existingRemote.baseUrl || ''),
        token: remoteToken
      }
    : null
  const nextConnections = [localConnection, ...(remoteConnection ? [remoteConnection] : []), ...connections]

  return registryFromConnections(nextConnections, localConnection.id)
}

module.exports = {
  CONNECTION_REGISTRY_SCHEMA_VERSION,
  DEFAULT_CONNECTION_KIND,
  coerceDesktopConnectionConfig,
  getActiveConnection,
  migrateDesktopConnectionConfig,
  normalizeRemoteBaseUrl,
  sanitizeDesktopConnectionConfig,
  tokenPreview
}
