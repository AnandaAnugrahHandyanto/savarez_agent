const assert = require('node:assert/strict')
const test = require('node:test')

const { resolveConnectionRoute } = require('./connection-router.cjs')

const normalizeRemoteBaseUrl = value => String(value || '').replace(/\/+$/, '')
const buildGatewayWsUrl = (baseUrl, token) => `${baseUrl.replace(/^http/, 'ws')}/ws?token=${encodeURIComponent(token)}`
const decryptDesktopSecret = secret => (secret && typeof secret === 'object' ? String(secret.value || '').replace(/^enc:/, '') : '')

const config = {
  schemaVersion: 2,
  activeConnectionId: 'remote-1',
  connections: [
    {
      id: 'local',
      name: 'Local gateway',
      kind: 'hermes-dashboard',
      mode: 'local',
      baseUrl: '',
      token: null
    },
    {
      id: 'remote-1',
      name: 'Dolly gateway',
      kind: 'hermes-dashboard',
      mode: 'remote',
      baseUrl: 'https://dolly.example/hermes/',
      token: { encoding: 'test', value: 'enc:dolly-token' }
    }
  ]
}

const deps = { buildGatewayWsUrl, decryptDesktopSecret, normalizeRemoteBaseUrl }

test('resolves local gateway by id even when a remote gateway is active', () => {
  assert.deepEqual(resolveConnectionRoute(config, 'local', deps), {
    id: 'local',
    mode: 'local',
    name: 'Local gateway',
    source: 'settings'
  })
})

test('resolves remote gateway by id with decrypted token and websocket URL', () => {
  assert.deepEqual(resolveConnectionRoute(config, 'remote-1', deps), {
    baseUrl: 'https://dolly.example/hermes',
    id: 'remote-1',
    mode: 'remote',
    name: 'Dolly gateway',
    source: 'settings',
    token: 'dolly-token',
    wsUrl: 'wss://dolly.example/hermes/ws?token=dolly-token'
  })
})

test('resolves empty gateway id to the active connection without disabling local peers', () => {
  assert.equal(resolveConnectionRoute(config, '', deps).id, 'remote-1')
})

test('resolves missing connection config to the implicit local gateway', () => {
  assert.deepEqual(resolveConnectionRoute(undefined, '', deps), {
    id: 'local',
    mode: 'local',
    name: 'Local gateway',
    source: 'settings'
  })
})

test('throws a clear error for unknown gateway ids', () => {
  assert.throws(() => resolveConnectionRoute(config, 'missing', deps), /Unknown gateway connection: missing/)
})
