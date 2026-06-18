'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const ELECTRON_DIR = __dirname

function readElectronFile(name) {
  return fs.readFileSync(path.join(ELECTRON_DIR, name), 'utf8').replace(/\r\n/g, '\n')
}

function compactSourceWithMap(source) {
  let text = ''
  const map = []

  for (let index = 0; index < source.length; index += 1) {
    if (/\s/.test(source[index])) continue
    map[text.length] = index
    text += source[index]
  }

  return { text, map }
}

function sourceIndexOf(source, needle) {
  const direct = source.indexOf(needle)
  if (direct !== -1) return direct

  const compactNeedle = needle.replace(/\s+/g, '')
  const compact = compactSourceWithMap(source)
  const compactIndex = compact.text.indexOf(compactNeedle)

  return compactIndex === -1 ? -1 : compact.map[compactIndex]
}

function requireHiddenChildOptions(source, needle) {
  const index = sourceIndexOf(source, needle)
  assert.notEqual(index, -1, `missing call site: ${needle}`)
  const snippet = source.slice(index, index + 700)
  assert.match(
    snippet,
    /hiddenWindowsChildOptions\(/,
    `expected ${needle} to wrap child-process options with hiddenWindowsChildOptions`
  )
}

test('desktop background child processes opt into hidden Windows consoles', () => {
  const source = readElectronFile('main.cjs')

  assert.match(source, /function hiddenWindowsChildOptions\(options = \{\}\)/)

  requireHiddenChildOptions(source, "execFileSync(\n          'reg'")
  requireHiddenChildOptions(source, 'execFileSync(\n          pyExe')
  requireHiddenChildOptions(source, 'spawn(resolveGitBinary()')
  requireHiddenChildOptions(source, "execFileSync('taskkill'")
  requireHiddenChildOptions(source, "spawn('curl'")
  requireHiddenChildOptions(source, 'spawn(backend.command, backend.args')
  requireHiddenChildOptions(source, 'hermesProcess = spawn(backend.command, backend.args')
  requireHiddenChildOptions(source, "spawn(py, ['-m', 'hermes_cli.main', 'uninstall', '--gui-summary']")
})

test('intentional or interactive desktop child processes stay documented', () => {
  const source = readElectronFile('main.cjs')

  assert.match(source, /windowsHide: false/)
  assert.match(source, /handOffWindowsBootstrapRecovery/)
  assert.match(source, /'--repair', '--branch'/)
  assert.match(source, /'--update', '--branch'/)
  assert.match(source, /nodePty\.spawn\(command, args/)
  assert.match(source, /spawn\('cmd\.exe', \['\/c', 'start'/)
})

test('bootstrap PowerShell runner hides Windows console children', () => {
  const source = readElectronFile('bootstrap-runner.cjs')

  assert.match(source, /function hiddenWindowsChildOptions\(options = \{\}\)/)
  requireHiddenChildOptions(source, 'spawn(ps, fullArgs')
})
