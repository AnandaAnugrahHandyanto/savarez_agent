const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { EventEmitter } = require('node:events')
const test = require('node:test')

const { isRunnableWindowsUpdaterBinary, waitForUpdaterSpawn } = require('./updater-handoff.cjs')

function withTempDir(fn) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-updater-handoff-'))
  try {
    return fn(dir)
  } finally {
    fs.rmSync(dir, { recursive: true, force: true })
  }
}

test('isRunnableWindowsUpdaterBinary rejects missing paths and directories', () => {
  withTempDir(dir => {
    assert.equal(isRunnableWindowsUpdaterBinary(path.join(dir, 'missing')), false)
    assert.equal(isRunnableWindowsUpdaterBinary(dir), false)
  })
})

test('isRunnableWindowsUpdaterBinary accepts existing hermes-setup.exe files', () => {
  withTempDir(dir => {
    const file = path.join(dir, 'hermes-setup.exe')
    fs.writeFileSync(file, 'not actually used by this test', { mode: 0o644 })

    assert.equal(isRunnableWindowsUpdaterBinary(file), true)
  })
})

test('waitForUpdaterSpawn rejects asynchronous spawn errors', async () => {
  const child = new EventEmitter()
  child.off = child.removeListener.bind(child)
  const promise = waitForUpdaterSpawn(child, { timeoutMs: 100 })
  const error = new Error('ENOENT')

  child.emit('error', error)

  await assert.rejects(promise, /ENOENT/)
})

test('waitForUpdaterSpawn resolves after spawn event', async () => {
  const child = new EventEmitter()
  child.off = child.removeListener.bind(child)
  const promise = waitForUpdaterSpawn(child, { timeoutMs: 100 })

  child.emit('spawn')

  await promise
})
