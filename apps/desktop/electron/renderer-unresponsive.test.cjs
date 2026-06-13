const assert = require('node:assert/strict')
const test = require('node:test')

const { createRendererUnresponsiveHandler } = require('./renderer-unresponsive.cjs')

test('renderer unresponsive handler logs once and prevents the native Electron popup path', () => {
  const logs = []
  let prevented = 0
  const handler = createRendererUnresponsiveHandler({
    now: () => 1_000,
    log: message => logs.push(message)
  })

  handler({ preventDefault: () => { prevented += 1 } })

  assert.equal(prevented, 1)
  assert.deepEqual(logs, ['[renderer] webContents became unresponsive; native popup suppressed'])
})

test('renderer unresponsive handler dedupes repeated freeze logs inside debounce window', () => {
  const logs = []
  let currentTime = 1_000
  const handler = createRendererUnresponsiveHandler({
    now: () => currentTime,
    log: message => logs.push(message),
    debounceMs: 10_000
  })

  handler({ preventDefault() {} })
  currentTime += 1_000
  handler({ preventDefault() {} })
  currentTime += 10_000
  handler({ preventDefault() {} })

  assert.deepEqual(logs, [
    '[renderer] webContents became unresponsive; native popup suppressed',
    '[renderer] webContents became unresponsive; native popup suppressed'
  ])
})
