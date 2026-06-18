'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')

const { createMessageSendRestartGuard, safeDecodeChunk } = require('./runtime-guards.cjs')

test('safeDecodeChunk replaces malformed byte sequences instead of throwing', () => {
  assert.equal(safeDecodeChunk(Buffer.from([0x61, 0x80, 0x62])), 'a�b')
  assert.equal(safeDecodeChunk(null), '')
  assert.equal(safeDecodeChunk('plain'), 'plain')
})

test('message send restart guard blocks during active sends and recent failures only', () => {
  let now = 1_000
  const guard = createMessageSendRestartGuard({ graceMs: 500, now: () => now })

  assert.equal(guard.restartBlockReason(), null)
  assert.deepEqual(guard.record({ state: 'begin' }), { activeCount: 1, blockingRestart: true, lastFailureAt: null })
  assert.equal(guard.restartBlockReason(), 'message-send-active:1')

  assert.deepEqual(guard.record({ state: 'success' }), { activeCount: 0, blockingRestart: false, lastFailureAt: null })
  assert.equal(guard.restartBlockReason(), null)

  assert.deepEqual(guard.record({ state: 'begin' }), { activeCount: 1, blockingRestart: true, lastFailureAt: null })
  assert.deepEqual(guard.record({ state: 'failure' }), { activeCount: 0, blockingRestart: true, lastFailureAt: 1_000 })
  assert.equal(guard.restartBlockReason(), 'message-send-recent-failure')

  now = 1_501
  assert.deepEqual(guard.snapshot(), { activeCount: 0, blockingRestart: false, lastFailureAt: 1_000 })
  assert.equal(guard.restartBlockReason(), null)
})
