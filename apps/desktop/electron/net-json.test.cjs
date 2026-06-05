/**
 * Tests for Electron/Node JSON request header helpers.
 *
 * Run with: node --test electron/net-json.test.cjs
 */

const test = require('node:test')
const assert = require('node:assert/strict')

const { jsonBodyBuffer, jsonRequestHeaders } = require('./net-json.cjs')

test('jsonBodyBuffer returns undefined when no body is provided', () => {
  assert.equal(jsonBodyBuffer(undefined), undefined)
})

test('jsonBodyBuffer serializes request bodies to byte buffers', () => {
  const body = jsonBodyBuffer({ config: { approvals: { mode: 'smart' } } })

  assert.ok(Buffer.isBuffer(body))
  assert.equal(body.toString('utf8'), '{"config":{"approvals":{"mode":"smart"}}}')
})

test('Node JSON request headers include session token and content length', () => {
  const body = jsonBodyBuffer({ config: { approvals: { mode: 'off' } } })

  assert.deepEqual(jsonRequestHeaders({ body, token: 'tok_123' }), {
    'Content-Type': 'application/json',
    'X-Hermes-Session-Token': 'tok_123',
    'Content-Length': String(body.length)
  })
})

test('Public JSON request headers omit the session token when none is provided', () => {
  const headers = jsonRequestHeaders()

  assert.deepEqual(headers, {
    'Content-Type': 'application/json'
  })
  assert.equal(Object.hasOwn(headers, 'X-Hermes-Session-Token'), false)
})

test('OAuth Electron JSON request headers omit manual content length for bodies', () => {
  const body = jsonBodyBuffer({ config: { approvals: { mode: 'manual' } } })
  const headers = jsonRequestHeaders({ body, includeContentLength: false })

  assert.deepEqual(headers, {
    'Content-Type': 'application/json'
  })
  assert.equal(Object.hasOwn(headers, 'Content-Length'), false)
})
