const test = require('node:test')
const assert = require('node:assert/strict')

const { revalidatePrimaryConnection } = require('./connection-revalidate.cjs')

test('revalidatePrimaryConnection clears a rejected cached remote boot promise', async () => {
  let resetCount = 0

  const result = await revalidatePrimaryConnection(Promise.reject(new Error('session expired')), {
    resetConnection: () => {
      resetCount += 1
    },
    probeStatus: async () => {
      throw new Error('should not probe after rejected boot')
    }
  })

  assert.deepEqual(result, { ok: true, rebuilt: true })
  assert.equal(resetCount, 1)
})

test('revalidatePrimaryConnection leaves healthy remote connections cached', async () => {
  let resetCount = 0
  const probed = []

  const result = await revalidatePrimaryConnection(Promise.resolve({ mode: 'remote', baseUrl: 'https://box.example/' }), {
    resetConnection: () => {
      resetCount += 1
    },
    probeStatus: async url => {
      probed.push(url)
    }
  })

  assert.deepEqual(result, { ok: true, rebuilt: false })
  assert.equal(resetCount, 0)
  assert.deepEqual(probed, ['https://box.example/api/status'])
})

test('revalidatePrimaryConnection drops unreachable remote connection descriptors', async () => {
  let resetCount = 0
  const logs = []

  const result = await revalidatePrimaryConnection(Promise.resolve({ mode: 'remote', baseUrl: 'http://box:9119' }), {
    resetConnection: () => {
      resetCount += 1
    },
    rememberLog: message => logs.push(message),
    probeStatus: async () => {
      throw new Error('offline')
    }
  })

  assert.deepEqual(result, { ok: true, rebuilt: true })
  assert.equal(resetCount, 1)
  assert.match(logs.join('\n'), /failed liveness probe/i)
})

test('revalidatePrimaryConnection ignores local connection descriptors', async () => {
  let resetCount = 0

  const result = await revalidatePrimaryConnection(Promise.resolve({ mode: 'local', baseUrl: 'http://127.0.0.1:1234' }), {
    resetConnection: () => {
      resetCount += 1
    },
    probeStatus: async () => {
      throw new Error('local should not be probed here')
    }
  })

  assert.deepEqual(result, { ok: true, rebuilt: false })
  assert.equal(resetCount, 0)
})
