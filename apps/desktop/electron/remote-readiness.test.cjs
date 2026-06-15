const assert = require('node:assert/strict')
const test = require('node:test')

const { checkRemoteHermesOnce, waitForRemoteHermes } = require('./remote-readiness.cjs')

test('remote readiness checks status and token websocket path', async () => {
  const calls = []

  await checkRemoteHermesOnce(
    { baseUrl: 'https://hermes.example', authMode: 'token', token: 'saved-token' },
    {
      fetchJson: async (url, token, options) => {
        calls.push(['status', url, token, options.timeoutMs])
        return { ok: true }
      },
      probeWebSocket: async (url, options) => {
        calls.push(['ws', url, typeof options.WebSocketImpl])
        return { ok: true }
      },
      WebSocketImpl: function MockWebSocket() {}
    }
  )

  assert.deepEqual(calls, [
    ['status', 'https://hermes.example/api/status', 'saved-token', 8000],
    ['ws', 'wss://hermes.example/api/ws?token=saved-token', 'function']
  ])
})

test('remote readiness mints an OAuth websocket ticket instead of using a static token', async () => {
  const calls = []

  await checkRemoteHermesOnce(
    { baseUrl: 'https://hermes.example/prefix', authMode: 'oauth', token: 'ignored-token' },
    {
      fetchJson: async (url, token) => {
        calls.push(['status', url, token])
        return { ok: true }
      },
      mintTicket: async baseUrl => {
        calls.push(['ticket', baseUrl])
        return calls.filter(call => call[0] === 'ticket').length === 1 ? 'probe ticket' : 'renderer ticket'
      },
      probeWebSocket: async url => {
        calls.push(['ws', url])
        return { ok: true }
      },
      WebSocketImpl: function MockWebSocket() {}
    }
  )

  assert.deepEqual(calls, [
    ['status', 'https://hermes.example/prefix/api/status', null],
    ['ticket', 'https://hermes.example/prefix'],
    ['ws', 'wss://hermes.example/prefix/api/ws?ticket=probe%20ticket'],
    ['ticket', 'https://hermes.example/prefix']
  ])
})

test('remote readiness rejects status-only success when the websocket fails', async () => {
  await assert.rejects(
    () =>
      checkRemoteHermesOnce(
        { baseUrl: 'https://hermes.example', authMode: 'token', token: 'stale-token' },
        {
          fetchJson: async () => ({ ok: true }),
          probeWebSocket: async () => ({ ok: false, reason: '401 Unauthorized' }),
          WebSocketImpl: function MockWebSocket() {}
        }
      ),
    /saved token could not open the live \/api\/ws chat connection.*Refresh the token or switch to Local/
  )
})

test('remote readiness surfaces OAuth sign-in guidance when ws ticket auth fails', async () => {
  await assert.rejects(
    () =>
      checkRemoteHermesOnce(
        { baseUrl: 'https://hermes.example', authMode: 'oauth' },
        {
          fetchJson: async () => ({ ok: true }),
          mintTicket: async () => 'ticket',
          probeWebSocket: async () => ({ ok: false, reason: '4401 session expired' }),
          WebSocketImpl: function MockWebSocket() {}
        }
      ),
    /live \/api\/ws chat connection failed.*Sign in again.*switch to Local/
  )
})

test('waitForRemoteHermes retries until status and websocket are both ready', async () => {
  let attempts = 0

  await waitForRemoteHermes(
    { baseUrl: 'https://hermes.example', authMode: 'token', token: 'saved-token' },
    {
      fetchJson: async () => ({ ok: true }),
      probeWebSocket: async () => {
        attempts += 1
        return attempts === 1 ? { ok: false, reason: 'booting' } : { ok: true }
      },
      WebSocketImpl: function MockWebSocket() {},
      readyTimeoutMs: 500,
      retryDelayMs: 1
    }
  )

  assert.equal(attempts, 2)
})
