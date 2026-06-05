const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const {
  buildPinArgs,
  buildPosixPinArgs,
  runBootstrap,
  shouldPinBootstrapCommit
} = require('./bootstrap-runner.cjs')

test('runBootstrap bails immediately when the signal is already aborted', async () => {
  const controller = new AbortController()
  controller.abort()

  const events = []
  const result = await runBootstrap({
    installStamp: null,
    activeRoot: '/tmp/hermes-runner-test',
    sourceRepoRoot: null,
    hermesHome: '/tmp/hermes-runner-test',
    logRoot: '/tmp/hermes-runner-test',
    onEvent: ev => events.push(ev),
    abortSignal: controller.signal
  })

  // Cancelled before any install script is spawned.
  assert.deepEqual(result, { ok: false, cancelled: true })
  assert.ok(
    events.some(ev => ev.type === 'failed' && /cancelled/i.test(ev.error)),
    'should emit a cancelled failure event'
  )
})

test('bootstrap keeps commit pins for fresh desktop installs', () => {
  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-runner-fresh-'))
  const activeRoot = path.join(tmpRoot, 'hermes-agent')
  const stamp = { commit: 'abcdef1234567890abcdef1234567890abcdef12', branch: 'main' }

  assert.equal(shouldPinBootstrapCommit({ installStamp: stamp, activeRoot }), true)
  assert.deepEqual(buildPinArgs({ installStamp: stamp, activeRoot }), [
    '-Commit',
    stamp.commit,
    '-Branch',
    'main'
  ])
  assert.deepEqual(buildPosixPinArgs({ installStamp: stamp, activeRoot, hermesHome: '/tmp/hermes-home' }), [
    '--dir',
    activeRoot,
    '--hermes-home',
    '/tmp/hermes-home',
    '--branch',
    'main',
    '--commit',
    stamp.commit
  ])
})

test('bootstrap skips commit pins when repairing an existing git checkout', () => {
  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-runner-existing-'))
  const activeRoot = path.join(tmpRoot, 'hermes-agent')
  fs.mkdirSync(path.join(activeRoot, '.git'), { recursive: true })
  const stamp = { commit: 'abcdef1234567890abcdef1234567890abcdef12', branch: 'main' }

  assert.equal(shouldPinBootstrapCommit({ installStamp: stamp, activeRoot }), false)
  assert.deepEqual(buildPinArgs({ installStamp: stamp, activeRoot }), ['-Branch', 'main'])
  assert.deepEqual(buildPosixPinArgs({ installStamp: stamp, activeRoot, hermesHome: '/tmp/hermes-home' }), [
    '--dir',
    activeRoot,
    '--hermes-home',
    '/tmp/hermes-home',
    '--branch',
    'main'
  ])
})
