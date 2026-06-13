'use strict'

const assert = require('node:assert/strict')
const test = require('node:test')

const { hasUsableActiveInstall, isResolverCacheHit, writeResolverCacheHit } = require('./runtime-resolver.cjs')

function baseOpts(overrides = {}) {
  return {
    activeRoot: '/home/user/.hermes/hermes-agent',
    canImportHermesCli: () => true,
    fileExists: () => true,
    getVenvPython: venvRoot => `${venvRoot}/bin/python`,
    isHermesSourceRoot: () => true,
    rememberLog: () => {},
    venvRoot: '/home/user/.hermes/hermes-agent/venv',
    ...overrides
  }
}

test('hasUsableActiveInstall accepts a CLI-first source checkout with a working venv', () => {
  assert.equal(hasUsableActiveInstall(baseOpts()), true)
})

test('hasUsableActiveInstall rejects missing source roots and venvs', () => {
  assert.equal(hasUsableActiveInstall(baseOpts({ isHermesSourceRoot: () => false })), false)
  assert.equal(hasUsableActiveInstall(baseOpts({ fileExists: () => false })), false)
})

test('hasUsableActiveInstall rejects venvs that cannot import hermes_cli and logs why', () => {
  const lines = []
  const ok = hasUsableActiveInstall(
    baseOpts({
      canImportHermesCli: () => false,
      rememberLog: line => lines.push(line)
    })
  )

  assert.equal(ok, false)
  assert.match(lines.join('\n'), /hermes_cli is not importable/)
})

test('hasUsableActiveInstall skips the Python import probe when resolver cache matches', () => {
  let importProbeCount = 0
  const ok = hasUsableActiveInstall(
    baseOpts({
      appVersion: '1.2.3',
      canImportHermesCli: () => {
        importProbeCount += 1
        return false
      },
      readResolverCache: () => ({
        schemaVersion: 1,
        activeRoot: '/home/user/.hermes/hermes-agent',
        venvPython: '/home/user/.hermes/hermes-agent/venv/bin/python',
        appVersion: '1.2.3',
        canImportHermesCli: true
      })
    })
  )

  assert.equal(ok, true)
  assert.equal(importProbeCount, 0)
})

test('hasUsableActiveInstall invalidates resolver cache on app version change', () => {
  let importProbeCount = 0
  const ok = hasUsableActiveInstall(
    baseOpts({
      appVersion: '1.2.4',
      canImportHermesCli: () => {
        importProbeCount += 1
        return true
      },
      readResolverCache: () => ({
        schemaVersion: 1,
        activeRoot: '/home/user/.hermes/hermes-agent',
        venvPython: '/home/user/.hermes/hermes-agent/venv/bin/python',
        appVersion: '1.2.3',
        canImportHermesCli: true
      })
    })
  )

  assert.equal(ok, true)
  assert.equal(importProbeCount, 1)
})

test('hasUsableActiveInstall invalidates resolver cache for a different install path', () => {
  let importProbeCount = 0
  const ok = hasUsableActiveInstall(
    baseOpts({
      appVersion: '1.2.3',
      canImportHermesCli: () => {
        importProbeCount += 1
        return true
      },
      readResolverCache: () => ({
        schemaVersion: 1,
        activeRoot: '/tmp/other/hermes-agent',
        venvPython: '/tmp/other/hermes-agent/venv/bin/python',
        appVersion: '1.2.3',
        canImportHermesCli: true
      })
    })
  )

  assert.equal(ok, true)
  assert.equal(importProbeCount, 1)
})

test('hasUsableActiveInstall writes a positive resolver cache after a successful probe', () => {
  let written = null
  const ok = hasUsableActiveInstall(
    baseOpts({
      appVersion: '1.2.3',
      writeResolverCache: cache => {
        written = cache
      }
    })
  )

  assert.equal(ok, true)
  assert.equal(written.schemaVersion, 1)
  assert.equal(written.activeRoot, '/home/user/.hermes/hermes-agent')
  assert.equal(written.venvPython, '/home/user/.hermes/hermes-agent/venv/bin/python')
  assert.equal(written.appVersion, '1.2.3')
  assert.equal(written.canImportHermesCli, true)
})

test('resolver cache helpers tolerate missing callbacks and malformed cache data', () => {
  assert.equal(isResolverCacheHit({ activeRoot: 'a', appVersion: '1', venvPython: 'p' }), false)
  assert.equal(
    isResolverCacheHit({ activeRoot: 'a', appVersion: '1', venvPython: 'p', readResolverCache: () => null }),
    false
  )
  assert.doesNotThrow(() => writeResolverCacheHit({ activeRoot: 'a', appVersion: '1', venvPython: 'p' }))
})
