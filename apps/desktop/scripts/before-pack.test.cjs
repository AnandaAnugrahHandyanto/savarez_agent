'use strict'

const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const test = require('node:test')

const { stashAppOutDir } = require('../scripts/before-pack.cjs')

test('stashAppOutDir renames a populated unpacked directory to .backup', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-before-pack-'))
  try {
    const appOutDir = path.join(tempRoot, 'linux-unpacked')
    fs.mkdirSync(appOutDir, { recursive: true })
    // Reproduce the corrupted partial state: license + payload present,
    // electron binary missing — exactly what trips the ENOENT rename.
    fs.writeFileSync(path.join(appOutDir, 'LICENSE.electron.txt'), 'x', 'utf8')
    fs.writeFileSync(path.join(appOutDir, 'resources.pak'), 'x', 'utf8')
    fs.mkdirSync(path.join(appOutDir, 'resources'), { recursive: true })
    fs.writeFileSync(path.join(appOutDir, 'resources', 'app.asar'), 'x', 'utf8')

    const backupPath = stashAppOutDir(appOutDir)

    // The original dir should be gone (renamed to backup)
    assert.equal(fs.existsSync(appOutDir), false)
    // The backup should exist at the expected location
    assert.equal(fs.existsSync(backupPath), true)
    assert.ok(backupPath.endsWith('.backup'))
    // Contents should be preserved
    assert.equal(fs.existsSync(path.join(backupPath, 'LICENSE.electron.txt')), true)
    assert.equal(fs.existsSync(path.join(backupPath, 'resources', 'app.asar')), true)
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true })
  }
})

test('stashAppOutDir is a no-op when the directory is absent', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-before-pack-'))
  try {
    const missing = path.join(tempRoot, 'does-not-exist')
    assert.equal(stashAppOutDir(missing), false)
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true })
  }
})

test('stashAppOutDir ignores empty or invalid input', () => {
  assert.equal(stashAppOutDir(''), false)
  assert.equal(stashAppOutDir(undefined), false)
  assert.equal(stashAppOutDir(null), false)
  assert.equal(stashAppOutDir(42), false)
})

test('stashAppOutDir removes a stale backup before renaming', () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-before-pack-'))
  try {
    const appOutDir = path.join(tempRoot, 'win-unpacked')
    const backupDir = appOutDir + '.backup'

    // Create both a current dir and a stale backup from a prior interrupted run
    fs.mkdirSync(appOutDir, { recursive: true })
    fs.writeFileSync(path.join(appOutDir, 'Hermes.exe'), 'x', 'utf8')

    fs.mkdirSync(backupDir, { recursive: true })
    fs.writeFileSync(path.join(backupDir, 'old.exe'), 'x', 'utf8')

    const backupPath = stashAppOutDir(appOutDir)

    // Stale backup should have been removed before rename
    assert.equal(fs.existsSync(backupDir), true)  // recreated by the rename
    assert.equal(fs.existsSync(path.join(backupPath, 'Hermes.exe')), true)
    assert.equal(fs.existsSync(path.join(backupPath, 'old.exe')), false)  // stale content gone
    assert.equal(fs.existsSync(appOutDir), false)
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true })
  }
})

test('beforePack default export resolves even when stash fails', async () => {
  const { default: beforePack } = require('../scripts/before-pack.cjs')
  // Passing an empty string for appOutDir should be handled gracefully
  // (no-op, no error)
  await assert.doesNotReject(beforePack({ appOutDir: '', electronPlatformName: 'linux' }))
})
