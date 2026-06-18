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


test('desktop resolver honors Windows PATHEXT and delimiter semantics', () => {
  const found = findExecutableOnPath('hermes', {
    searchPath: 'C:\\Tools;C:\\Windows',
    currentEnv: { PATHEXT: '.COM;.EXE;.BAT;.CMD' },
    platform: 'win32',
    pathModule: path.win32,
    fileExists: candidate => candidate === 'C:\\Tools\\hermes.EXE'
  })

  assert.equal(found, 'C:\\Tools\\hermes.EXE')
})

test('desktop resolver rejects direct Windows binary paths under WSL', () => {
  const found = findExecutableOnPath('C:\\Windows\\System32\\git.exe', {
    currentEnv: {},
    platform: 'win32',
    pathModule: path.win32,
    fileExists: () => true,
    isWindowsBinaryPathInWsl: (_candidate, { isWsl }) => isWsl,
    isWsl: true
  })

  assert.equal(found, null)
})


test('desktop resolver PATH matches backend PATH policy for bootstrap discovery', () => {
  const resolverPath = buildDesktopResolverPath({
    hermesHome: '/Users/alice/.hermes',
    venvRoot: '/Users/alice/.hermes/hermes-agent/venv',
    currentEnv: { PATH: '/usr/bin:/bin' },
    platform: 'darwin',
    pathModule: path.posix
  })

  assert.deepEqual(resolverPath.split(':').slice(0, 4), [
    '/Users/alice/.hermes/node/bin',
    '/Users/alice/.hermes/hermes-agent/venv/bin',
    '/usr/bin',
    '/bin'
  ])
  assert.ok(resolverPath.split(':').includes('/opt/homebrew/bin'))
})
