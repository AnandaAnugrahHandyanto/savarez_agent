'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const ELECTRON_DIR = __dirname

function readMainSource() {
  return fs.readFileSync(path.join(ELECTRON_DIR, 'main.cjs'), 'utf8').replace(/\r\n/g, '\n')
}

function extractFunction(source, name) {
  const marker = `function ${name}()`
  const start = source.indexOf(marker)
  assert.notEqual(start, -1, `missing function ${name}`)
  const nextFunction = source.indexOf('\nfunction ', start + marker.length)
  return source.slice(start, nextFunction === -1 ? source.length : nextFunction)
}

test('packaged renderer index prefers the real unpacked dist before app.asar', () => {
  const body = extractFunction(readMainSource(), 'resolveRendererIndex')

  const unpackedCandidate = "path.join(resolveWebDist(), 'index.html')"
  const asarCandidate = "path.join(APP_ROOT, 'dist', 'index.html')"
  const unpackedIndex = body.indexOf(unpackedCandidate)
  const asarIndex = body.indexOf(asarCandidate)

  assert.notEqual(unpackedIndex, -1, `missing renderer candidate: ${unpackedCandidate}`)
  assert.notEqual(asarIndex, -1, `missing renderer candidate: ${asarCandidate}`)
  assert.ok(
    unpackedIndex < asarIndex,
    'resolveRendererIndex must load app.asar.unpacked/dist first so newly hashed Vite assets are visible on the real filesystem'
  )
  assert.match(body, /stale header cannot see those files/)
})
