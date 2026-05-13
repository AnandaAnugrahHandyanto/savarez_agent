import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { _resetPaplayMissing, ringBell } from '../lib/notify.js'

const spawnMock = vi.fn()

vi.mock('node:child_process', () => ({
  spawn: (...args: unknown[]) => spawnMock(...args)
}))

const makeFakeChild = () => {
  const child = {
    on: vi.fn(),
    unref: vi.fn()
  }
  return child
}

describe('ringBell', () => {
  beforeEach(() => {
    spawnMock.mockReset()
    _resetPaplayMissing()
    spawnMock.mockReturnValue(makeFakeChild())
  })

  afterEach(() => {
    _resetPaplayMissing()
  })

  it('writes ASCII BEL when stdout is a TTY', () => {
    const stdout = { isTTY: true, write: vi.fn() } as unknown as NodeJS.WriteStream

    ringBell({ stdout })

    expect(stdout.write).toHaveBeenCalledWith('\x07')
  })

  it('skips ASCII BEL when stdout is not a TTY', () => {
    const stdout = { isTTY: false, write: vi.fn() } as unknown as NodeJS.WriteStream

    ringBell({ stdout })

    expect(stdout.write).not.toHaveBeenCalled()
  })

  it('skips ASCII BEL when stdout is missing entirely', () => {
    expect(() => ringBell()).not.toThrow()
    expect(spawnMock).toHaveBeenCalledTimes(1)
  })

  it('spawns paplay detached with ignored stdio so the agent thread never blocks', () => {
    ringBell()

    expect(spawnMock).toHaveBeenCalledTimes(1)
    const [cmd, args, opts] = spawnMock.mock.calls[0]
    expect(cmd).toBe('paplay')
    expect(args).toEqual(['/usr/share/sounds/freedesktop/stereo/message-new-instant.oga'])
    expect(opts).toMatchObject({ detached: true, stdio: 'ignore' })
  })

  it('forwards a custom soundPath when supplied', () => {
    ringBell({ soundPath: '/tmp/custom.oga' })

    const [, args] = spawnMock.mock.calls[0]
    expect(args).toEqual(['/tmp/custom.oga'])
  })

  it('caches paplayMissing on ENOENT so we do not spawn again', () => {
    const child = makeFakeChild()
    spawnMock.mockReturnValueOnce(child)

    ringBell()

    // Find the 'error' listener and trigger ENOENT.
    const errorEntry = child.on.mock.calls.find(([event]) => event === 'error')
    expect(errorEntry).toBeTruthy()
    const enoent = Object.assign(new Error('not found'), { code: 'ENOENT' })
    errorEntry?.[1](enoent)

    spawnMock.mockClear()
    ringBell()
    ringBell()

    expect(spawnMock).not.toHaveBeenCalled()
  })

  it('keeps trying spawn after non-ENOENT errors', () => {
    const child = makeFakeChild()
    spawnMock.mockReturnValueOnce(child)

    ringBell()

    const errorEntry = child.on.mock.calls.find(([event]) => event === 'error')
    errorEntry?.[1](Object.assign(new Error('busy'), { code: 'EBUSY' }))

    spawnMock.mockClear()
    ringBell()

    expect(spawnMock).toHaveBeenCalledTimes(1)
  })

  it('swallows synchronous spawn() throws (sandboxed environments)', () => {
    spawnMock.mockImplementationOnce(() => {
      throw new Error('sandbox blocked')
    })

    expect(() => ringBell()).not.toThrow()
  })

  it('swallows stdout.write failures so a closed pipe never crashes the caller', () => {
    const stdout = {
      isTTY: true,
      write: vi.fn(() => {
        throw new Error('EPIPE')
      })
    } as unknown as NodeJS.WriteStream

    expect(() => ringBell({ stdout })).not.toThrow()
    expect(spawnMock).toHaveBeenCalledTimes(1)
  })
})
