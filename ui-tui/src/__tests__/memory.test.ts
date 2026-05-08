import { mkdtempSync, readdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { performHeapDump } from '../lib/memory.js'

const ENV_KEYS = ['HERMES_AUTO_HEAPDUMP', 'HERMES_HEAPDUMP_DIR'] as const

describe('performHeapDump auto opt-in', () => {
  let saved: Record<string, string | undefined>
  let dir: string

  beforeEach(() => {
    saved = {}

    for (const k of ENV_KEYS) {
      saved[k] = process.env[k]
      delete process.env[k]
    }

    dir = mkdtempSync(join(tmpdir(), 'hermes-heapdump-test-'))
    process.env.HERMES_HEAPDUMP_DIR = dir
  })

  afterEach(() => {
    for (const k of ENV_KEYS) {
      if (saved[k] === undefined) {
        delete process.env[k]
      } else {
        process.env[k] = saved[k]
      }
    }

    rmSync(dir, { force: true, recursive: true })
  })

  it('writes only diagnostics for auto-high without HERMES_AUTO_HEAPDUMP', async () => {
    const result = await performHeapDump('auto-high')

    expect(result.success).toBe(true)
    expect(result.diagPath).toBeDefined()
    expect(result.heapPath).toBeUndefined()

    const files = readdirSync(dir)
    expect(files.some(f => f.endsWith('.diagnostics.json'))).toBe(true)
    expect(files.some(f => f.endsWith('.heapsnapshot'))).toBe(false)
  })

  it('writes only diagnostics for auto-critical without HERMES_AUTO_HEAPDUMP', async () => {
    const result = await performHeapDump('auto-critical')

    expect(result.success).toBe(true)
    expect(result.heapPath).toBeUndefined()

    const files = readdirSync(dir)
    expect(files.some(f => f.endsWith('.heapsnapshot'))).toBe(false)
  })

  it('writes both diagnostics and heap snapshot for auto-high when HERMES_AUTO_HEAPDUMP=1', async () => {
    process.env.HERMES_AUTO_HEAPDUMP = '1'

    const result = await performHeapDump('auto-high')

    expect(result.success).toBe(true)
    expect(result.diagPath).toBeDefined()
    expect(result.heapPath).toBeDefined()

    const files = readdirSync(dir)
    expect(files.some(f => f.endsWith('.heapsnapshot'))).toBe(true)
  })

  it('writes both for manual triggers regardless of HERMES_AUTO_HEAPDUMP', async () => {
    const result = await performHeapDump('manual')

    expect(result.success).toBe(true)
    expect(result.heapPath).toBeDefined()

    const files = readdirSync(dir)
    expect(files.some(f => f.endsWith('.heapsnapshot'))).toBe(true)
  })

  it('treats values other than "1" as opt-out for auto triggers', async () => {
    process.env.HERMES_AUTO_HEAPDUMP = 'true'

    const result = await performHeapDump('auto-high')

    expect(result.success).toBe(true)
    expect(result.heapPath).toBeUndefined()
  })
})
