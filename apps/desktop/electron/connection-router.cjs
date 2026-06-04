const { migrateDesktopConnectionConfig } = require('./connection-registry.cjs')

function defaultDecryptDesktopSecret(secret) {
  if (!secret || typeof secret !== 'object') {
    return ''
  }

  return String(secret.value || '')
}

function resolveConnectionRoute(config, gatewayId, options = {}) {
  const registry = migrateDesktopConnectionConfig(config)
  const requestedGatewayId = String(gatewayId || '').trim()
  const connections = registry.connections
  const activeConnection = connections.find(connection => connection.id === registry.activeConnectionId) || connections[0]
  const connection = requestedGatewayId
    ? connections.find(candidate => candidate.id === requestedGatewayId)
    : activeConnection

  if (!connection) {
    throw new Error(requestedGatewayId ? `Unknown gateway connection: ${requestedGatewayId}` : 'No gateway connections are configured.')
  }

  if (connection.mode === 'remote') {
    const decryptDesktopSecret = options.decryptDesktopSecret || defaultDecryptDesktopSecret
    const normalizeRemoteBaseUrl = options.normalizeRemoteBaseUrl || (value => String(value || '').replace(/\/+$/, ''))
    const buildGatewayWsUrl = options.buildGatewayWsUrl
    const token = decryptDesktopSecret(connection.token)

    if (!token) {
      throw new Error(`Remote Hermes gateway ${connection.name || connection.id} has no saved session token.`)
    }

    const baseUrl = normalizeRemoteBaseUrl(connection.baseUrl)

    return {
      baseUrl,
      id: connection.id,
      mode: 'remote',
      name: connection.name,
      source: 'settings',
      token,
      wsUrl: typeof buildGatewayWsUrl === 'function' ? buildGatewayWsUrl(baseUrl, token) : undefined
    }
  }

  return {
    id: connection.id,
    mode: 'local',
    name: connection.name,
    source: 'settings'
  }
}

module.exports = {
  resolveConnectionRoute
}
