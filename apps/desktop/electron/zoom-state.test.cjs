const test = require('node:test')
const assert = require('node:assert/strict')

const {
  clampZoomLevel,
  normalizeZoomState,
  serializeZoomState,
  shouldHandleZoomShortcut,
  zoomFactorToLevel,
  zoomLevelToFactor
} = require('./zoom-state.cjs')

test('clampZoomLevel accepts finite numbers and clamps Electron bounds', () => {
  assert.equal(clampZoomLevel(0.5), 0.5)
  assert.equal(clampZoomLevel(999), 9)
  assert.equal(clampZoomLevel(-999), -9)
  assert.equal(clampZoomLevel('nope'), 0)
})

test('zoom factor conversion round-trips practical UI scales', () => {
  const level = zoomFactorToLevel(1.5)
  assert.equal(Math.round(zoomLevelToFactor(level) * 100), 150)
})

test('normalizeZoomState reads current level schema', () => {
  assert.deepEqual(normalizeZoomState({ level: 0.5 }), serializeZoomState(0.5))
})

test('normalizeZoomState migrates old factor and percent schemas', () => {
  assert.equal(normalizeZoomState({ factor: 1.5 }).percent, 150)
  assert.equal(normalizeZoomState({ percent: 150 }).percent, 150)
})

test('normalizeZoomState tolerates localStorage string level fallback', () => {
  assert.deepEqual(normalizeZoomState('0.25'), serializeZoomState(0.25))
  assert.equal(normalizeZoomState('wat'), null)
})

test('shouldHandleZoomShortcut catches Cmd/Ctrl plus even when + requires Shift', () => {
  assert.equal(shouldHandleZoomShortcut({ meta: true, key: '=', shift: true }, true), 'in')
  assert.equal(shouldHandleZoomShortcut({ meta: true, key: '+', shift: true }, true), 'in')
  assert.equal(shouldHandleZoomShortcut({ control: true, key: '=' }, false), 'in')
})

test('shouldHandleZoomShortcut distinguishes reset/out and ignores alt/plain input', () => {
  assert.equal(shouldHandleZoomShortcut({ meta: true, key: '0' }, true), 'reset')
  assert.equal(shouldHandleZoomShortcut({ meta: true, key: '-' }, true), 'out')
  assert.equal(shouldHandleZoomShortcut({ meta: true, alt: true, key: '=' }, true), false)
  assert.equal(shouldHandleZoomShortcut({ key: '=' }, true), false)
})
