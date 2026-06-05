const assert = require('node:assert/strict')
const crypto = require('node:crypto')
const http = require('node:http')
const test = require('node:test')

const {
  DEFAULT_GATEWAY_WS_PROBE_TIMEOUT_MS,
  DEFAULT_GATEWAY_WS_STABLE_MS,
  probeGatewayWebSocket
} = require('./gateway-ws-probe.cjs')

async function listen(server) {
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      server.off('error', reject)
      resolve()
    })
  })

  return server.address().port
}

function closeServer(server) {
  return new Promise(resolve => server.close(() => resolve()))
}

function acceptWebSocket(req, socket) {
  const key = req.headers['sec-websocket-key']
  const accept = crypto
    .createHash('sha1')
    .update(`${key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11`, 'utf8')
    .digest('base64')

  socket.write(
    [
      'HTTP/1.1 101 Switching Protocols',
      'Upgrade: websocket',
      'Connection: Upgrade',
      `Sec-WebSocket-Accept: ${accept}`,
      '',
      ''
    ].join('\r\n')
  )
}

test('probeGatewayWebSocket resolves once the socket stays open briefly', async t => {
  const server = http.createServer()
  t.after(async () => closeServer(server))

  server.on('upgrade', (req, socket) => {
    acceptWebSocket(req, socket)
    socket.on('data', () => socket.end())
    socket.on('end', () => socket.destroy())
  })

  const port = await listen(server)
  await assert.doesNotReject(
    probeGatewayWebSocket(`ws://127.0.0.1:${port}/api/ws?token=test`, {
      timeoutMs: 1_000,
      stableMs: 50
    })
  )
})

test('probeGatewayWebSocket rejects when the endpoint is not a websocket route', async t => {
  const server = http.createServer((_req, res) => {
    res.writeHead(404)
    res.end('no ws here')
  })
  t.after(async () => closeServer(server))

  const port = await listen(server)

  await assert.rejects(
    probeGatewayWebSocket(`ws://127.0.0.1:${port}/api/ws?token=test`, {
      timeoutMs: 1_000,
      stableMs: 50
    }),
    error => error instanceof Error
  )
})

test('probeGatewayWebSocket rejects when the socket closes immediately after upgrade', async t => {
  const server = http.createServer()
  t.after(async () => closeServer(server))

  server.on('upgrade', (req, socket) => {
    acceptWebSocket(req, socket)
    socket.end()
  })

  const port = await listen(server)

  await assert.rejects(
    probeGatewayWebSocket(`ws://127.0.0.1:${port}/api/ws?token=test`, {
      timeoutMs: 1_000,
      stableMs: 150
    }),
    error => error instanceof Error
  )
})

test('probe defaults stay positive', () => {
  assert.equal(DEFAULT_GATEWAY_WS_PROBE_TIMEOUT_MS > 0, true)
  assert.equal(DEFAULT_GATEWAY_WS_STABLE_MS > 0, true)
})
