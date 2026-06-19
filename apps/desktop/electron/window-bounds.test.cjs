/**
 * Tests for electron/window-bounds.cjs.
 *
 * Run with: node --test electron/window-bounds.test.cjs
 */

const test = require('node:test')
const assert = require('node:assert/strict')

const {
  DEFAULT_BOUNDS,
  MIN_WIDTH,
  MIN_HEIGHT,
  sanitizeBounds,
  isVisibleOnDisplays,
  resolveInitialBounds
} = require('./window-bounds.cjs')

const primaryDisplay = { workArea: { x: 0, y: 0, width: 1920, height: 1080 } }

test('sanitizeBounds returns null for missing/malformed payloads', () => {
  assert.equal(sanitizeBounds(null), null)
  assert.equal(sanitizeBounds(undefined), null)
  assert.equal(sanitizeBounds('1220x800'), null)
  assert.equal(sanitizeBounds({}), null)
  assert.equal(sanitizeBounds({ width: 1220 }), null) // height missing
  assert.equal(sanitizeBounds({ width: 'a', height: 'b' }), null)
  assert.equal(sanitizeBounds({ width: NaN, height: 800 }), null)
})

test('sanitizeBounds clamps width/height to the window minimums', () => {
  const out = sanitizeBounds({ width: 100, height: 100 })
  assert.equal(out.width, MIN_WIDTH)
  assert.equal(out.height, MIN_HEIGHT)
  assert.equal(out.isMaximized, false)
  assert.equal('x' in out, false)
})

test('sanitizeBounds rounds and preserves a valid position', () => {
  const out = sanitizeBounds({ x: 12.7, y: -4.2, width: 1300.6, height: 900.1, isMaximized: true })
  assert.deepEqual(out, { x: 13, y: -4, width: 1301, height: 900, isMaximized: true })
})

test('sanitizeBounds drops position when only one of x/y is finite', () => {
  const out = sanitizeBounds({ x: 100, width: 1220, height: 800 })
  assert.equal('x' in out, false)
  assert.equal('y' in out, false)
})

test('isVisibleOnDisplays treats position-less bounds as visible', () => {
  assert.equal(isVisibleOnDisplays({ width: 1220, height: 800 }, [primaryDisplay]), true)
})

test('isVisibleOnDisplays detects on-screen bounds', () => {
  const bounds = { x: 100, y: 100, width: 1220, height: 800 }
  assert.equal(isVisibleOnDisplays(bounds, [primaryDisplay]), true)
})

test('isVisibleOnDisplays rejects bounds on a removed monitor', () => {
  // Saved on a second monitor at x=2200 that is no longer attached.
  const bounds = { x: 2200, y: 200, width: 1220, height: 800 }
  assert.equal(isVisibleOnDisplays(bounds, [primaryDisplay]), false)
})

test('isVisibleOnDisplays rejects a tiny off-screen sliver', () => {
  // Only 10px of the window overlaps the right edge of the work area.
  const bounds = { x: 1910, y: 100, width: 1220, height: 800 }
  assert.equal(isVisibleOnDisplays(bounds, [primaryDisplay]), false)
})

test('isVisibleOnDisplays returns false with no displays and a stored position', () => {
  const bounds = { x: 100, y: 100, width: 1220, height: 800 }
  assert.equal(isVisibleOnDisplays(bounds, []), false)
})

test('resolveInitialBounds falls back to defaults on malformed payload', () => {
  assert.deepEqual(resolveInitialBounds(null, [primaryDisplay]), {
    width: DEFAULT_BOUNDS.width,
    height: DEFAULT_BOUNDS.height,
    isMaximized: false
  })
})

test('resolveInitialBounds restores valid on-screen bounds verbatim', () => {
  const raw = { x: 200, y: 150, width: 1400, height: 900, isMaximized: false }
  assert.deepEqual(resolveInitialBounds(raw, [primaryDisplay]), {
    x: 200,
    y: 150,
    width: 1400,
    height: 900,
    isMaximized: false
  })
})

test('resolveInitialBounds keeps size but drops an off-screen position', () => {
  const raw = { x: 5000, y: 5000, width: 1400, height: 900, isMaximized: false }
  const out = resolveInitialBounds(raw, [primaryDisplay])
  assert.deepEqual(out, { width: 1400, height: 900, isMaximized: false })
  assert.equal('x' in out, false)
})

test('resolveInitialBounds carries the maximized flag through', () => {
  const raw = { x: 0, y: 0, width: 1220, height: 800, isMaximized: true }
  const out = resolveInitialBounds(raw, [primaryDisplay])
  assert.equal(out.isMaximized, true)
})
