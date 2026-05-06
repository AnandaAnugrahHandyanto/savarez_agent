import { writeSync } from 'fs'
import { Readable } from 'node:stream'

import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { renderSync } from '../root.js'
import { EXIT_ALT_SCREEN } from '../termio/dec.js'

import { AlternateScreen } from './AlternateScreen.js'
import Box from './Box.js'
import Text from './Text.js'

vi.mock('fs', async () => {
  const actual = await vi.importActual<typeof import('fs')>('fs')

  return {
    ...actual,
    writeSync: vi.fn(() => 0)
  }
})

class TestStdin extends Readable {
  isRaw = false
  isTTY = true

  _read() {}

  setRawMode(value: boolean) {
    this.isRaw = value

    return this
  }
}

const replaceStdoutProp = (key: 'columns' | 'isTTY' | 'rows', value: number | boolean) => {
  const descriptor = Object.getOwnPropertyDescriptor(process.stdout, key)

  Object.defineProperty(process.stdout, key, { configurable: true, value })

  return () => {
    if (descriptor) {
      Object.defineProperty(process.stdout, key, descriptor)
    } else {
      delete (process.stdout as unknown as Record<string, unknown>)[key]
    }
  }
}

describe('AlternateScreen shutdown', () => {
  const restoreStdoutProps: Array<() => void> = []
  let stdoutWrite: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    restoreStdoutProps.push(
      replaceStdoutProp('columns', 40),
      replaceStdoutProp('rows', 12),
      replaceStdoutProp('isTTY', true)
    )
    stdoutWrite = vi.spyOn(process.stdout, 'write').mockImplementation((() => true) as typeof process.stdout.write)
    vi.mocked(writeSync).mockClear()
  })

  afterEach(() => {
    stdoutWrite.mockRestore()

    while (restoreStdoutProps.length) {
      restoreStdoutProps.pop()?.()
    }
  })

  it('does not emit a second alt-screen exit while React cleanup runs', () => {
    const instance = renderSync(
      React.createElement(
        AlternateScreen,
        null,
        React.createElement(Box, null, React.createElement(Text, null, 'hi'))
      ),
      {
        exitOnCtrlC: false,
        patchConsole: false,
        stdin: new TestStdin() as NodeJS.ReadStream,
        stdout: process.stdout
      }
    )

    stdoutWrite.mockClear()
    vi.mocked(writeSync).mockClear()

    instance.unmount()

    const syncWrites = vi
      .mocked(writeSync)
      .mock.calls.map(([, chunk]) => String(chunk))
      .join('')

    const streamWrites = stdoutWrite.mock.calls.map(([chunk]) => String(chunk)).join('')

    expect(syncWrites.split(EXIT_ALT_SCREEN)).toHaveLength(2)
    expect(streamWrites).not.toContain(EXIT_ALT_SCREEN)
  })
})
