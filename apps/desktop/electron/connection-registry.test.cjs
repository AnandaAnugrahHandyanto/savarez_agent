const assert = require('node:assert/strict')
const test = require('node:test')

const {
  CONNECTION_REGISTRY_SCHEMA_VERSION,
  coerceDesktopConnectionConfig,
  migrateDesktopConnectionConfig,
  sanitizeDesktopConnectionConfig
} = require('./connection-registry.cjs')

const encrypt = value => (value ? { encoding: 'test', value: `enc:${value}` } : null)
const decrypt = secret => {
  if (!secret || typeof secret !== 'object') return ''
  return String(secret.value || '').replace(/^enc:/, '')
}

test('migrates legacy remote connection config into single active registry connection', () => {
  const legacy = {
    mode: 'remote',
    remote: {
      url: 'http://127.0.0.1:9120',
      token: { encoding: 'test', value: 'enc:super-secret-token' }
    }
  }

  const config = migrateDesktopConnectionConfig(legacy)

  assert.equal(config.schemaVersion, CONNECTION_REGISTRY_SCHEMA_VERSION)
  assert.equal(config.activeConnectionId, 'remote-1')
  assert.equal(config.connections.length, 1)
  assert.deepEqual(config.connections[0], {
    id: 'remote-1',
    name: 'Remote gateway',
    kind: 'hermes-dashboard',
    mode: 'remote',
    baseUrl: 'http://127.0.0.1:9120',
    token: legacy.remote.token
  })
})

test('sanitized connection config exposes registry metadata and preview only, never raw token', () => {
  const config = migrateDesktopConnectionConfig({
    mode: 'remote',
    remote: {
      url: 'http://127.0.0.1:9120',
      token: { encoding: 'test', value: 'enc:super-secret-token' }
    }
  })

  const sanitized = sanitizeDesktopConnectionConfig(config, {
    decryptDesktopSecret: decrypt,
    envOverride: false
  })

  assert.equal(sanitized.schemaVersion, CONNECTION_REGISTRY_SCHEMA_VERSION)
  assert.equal(sanitized.activeConnectionId, 'remote-1')
  assert.equal(sanitized.mode, 'remote')
  assert.equal(sanitized.remoteUrl, 'http://127.0.0.1:9120')
  assert.equal(sanitized.remoteTokenSet, true)
  assert.equal(sanitized.remoteTokenPreview, '...-token')
  assert.equal(JSON.stringify(sanitized).includes('super-secret-token'), false)
  assert.deepEqual(sanitized.connections, [
    {
      id: 'remote-1',
      name: 'Remote gateway',
      kind: 'hermes-dashboard',
      mode: 'remote',
      baseUrl: 'http://127.0.0.1:9120',
      tokenPreview: '...-token',
      tokenSet: true
    }
  ])
})

test('coerces current settings payload into registry while preserving existing saved token', () => {
  const existing = migrateDesktopConnectionConfig({
    mode: 'remote',
    remote: {
      url: 'http://old.example.test',
      token: { encoding: 'test', value: 'enc:old-token' }
    }
  })

  const next = coerceDesktopConnectionConfig(
    { mode: 'remote', remoteUrl: 'https://new.example.test/hermes' },
    existing,
    { decryptDesktopSecret: decrypt, encryptDesktopSecret: encrypt }
  )

  assert.equal(next.schemaVersion, CONNECTION_REGISTRY_SCHEMA_VERSION)
  assert.equal(next.activeConnectionId, 'remote-1')
  assert.equal(next.connections[0].baseUrl, 'https://new.example.test/hermes')
  assert.deepEqual(next.connections[0].token, existing.connections[0].token)
})

test('switching to local keeps the saved remote connection inactive for later reuse', () => {
  const existing = migrateDesktopConnectionConfig({
    mode: 'remote',
    remote: {
      url: 'https://gateway.example.test/hermes',
      token: { encoding: 'test', value: 'enc:saved-token' }
    }
  })

  const next = coerceDesktopConnectionConfig(
    { mode: 'local', remoteUrl: 'https://gateway.example.test/hermes' },
    existing,
    { decryptDesktopSecret: decrypt, encryptDesktopSecret: encrypt }
  )

  assert.equal(next.activeConnectionId, 'local')
  assert.equal(next.connections.length, 2)
  assert.equal(next.connections[0].mode, 'local')
  assert.equal(next.connections[1].mode, 'remote')
  assert.equal(next.connections[1].baseUrl, 'https://gateway.example.test/hermes')
  assert.deepEqual(next.connections[1].token, existing.connections[0].token)
})
