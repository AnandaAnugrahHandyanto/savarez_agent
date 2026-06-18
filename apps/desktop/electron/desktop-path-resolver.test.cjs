const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')

const { buildDesktopResolverPath, findExecutableOnPath } = require('./desktop-path-resolver.cjs')

test('desktop resolver PATH includes Homebrew before resolving GUI-launched binaries', () => {
  const resolverPath = buildDesktopResolverPath({
    hermesHome: '/Users/alice/.hermes',
    venvRoot: '/Users/alice/.hermes/hermes-agent/venv',
    currentEnv: { PATH: '/usr/bin:/bin:/usr/sbin:/sbin' },
    platform: 'darwin',
    pathModule: path.posix
  })

  const found = findExecutableOnPath('hermes', {
    searchPath: resolverPath,
    currentEnv: { PATH: '/usr/bin:/bin:/usr/sbin:/sbin' },
    platform: 'darwin',
    pathModule: path.posix,
    fileExists: candidate => candidate === '/opt/homebrew/bin/hermes'
  })

  assert.equal(found, '/opt/homebrew/bin/hermes')
})
