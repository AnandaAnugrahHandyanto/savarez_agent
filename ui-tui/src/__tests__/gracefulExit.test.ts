import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { startParentWatchdog } from '../lib/gracefulExit.js'

describe('startParentWatchdog', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('calls onOrphaned when ppid changes to 1', () => {
    const onOrphaned = vi.fn()
    let ppid = 1234
    const originalPpid = process.ppid

    // Mock process.ppid to simulate reparenting to init
    Object.defineProperty(process, 'ppid', { get: () => ppid, configurable: true })

    try {
      const stop = startParentWatchdog(onOrphaned, 1000)
      expect(onOrphaned).not.toHaveBeenCalled()

      // Simulate parent exit → reparented to PID 1
      ppid = 1
      vi.advanceTimersByTime(1000)

      expect(onOrphaned).toHaveBeenCalledTimes(1)
      expect(onOrphaned.mock.calls[0][0]).toContain('ppid changed from 1234 to 1')

      stop()
    } finally {
      Object.defineProperty(process, 'ppid', { get: () => originalPpid, configurable: true })
    }
  })

  it('calls onOrphaned when ppid changes to a different non-init PID', () => {
    const onOrphaned = vi.fn()
    let ppid = 1234
    const originalPpid = process.ppid

    Object.defineProperty(process, 'ppid', { get: () => ppid, configurable: true })

    try {
      const stop = startParentWatchdog(onOrphaned, 1000)

      // Simulate PID recycling — parent died, PID reused by unrelated process
      ppid = 5678
      vi.advanceTimersByTime(1000)

      expect(onOrphaned).toHaveBeenCalledTimes(1)
      expect(onOrphaned.mock.calls[0][0]).toContain('parent changed (ppid 1234 → 5678)')

      stop()
    } finally {
      Object.defineProperty(process, 'ppid', { get: () => originalPpid, configurable: true })
    }
  })

  it('does not call onOrphaned when ppid stays the same', () => {
    const onOrphaned = vi.fn()
    const originalPpid = process.ppid
    const fixedPpid = originalPpid > 1 ? originalPpid : 9999

    Object.defineProperty(process, 'ppid', { get: () => fixedPpid, configurable: true })

    try {
      const stop = startParentWatchdog(onOrphaned, 1000)

      // Advance several intervals — parent stays alive
      vi.advanceTimersByTime(5000)

      expect(onOrphaned).not.toHaveBeenCalled()

      stop()
    } finally {
      Object.defineProperty(process, 'ppid', { get: () => originalPpid, configurable: true })
    }
  })

  it('stops checking after orphaning is detected', () => {
    const onOrphaned = vi.fn()
    let ppid = 1234
    const originalPpid = process.ppid

    Object.defineProperty(process, 'ppid', { get: () => ppid, configurable: true })

    try {
      startParentWatchdog(onOrphaned, 1000)

      ppid = 1
      vi.advanceTimersByTime(1000)
      expect(onOrphaned).toHaveBeenCalledTimes(1)

      // Advance more — should not call again (interval was cleared)
      vi.advanceTimersByTime(5000)
      expect(onOrphaned).toHaveBeenCalledTimes(1)
    } finally {
      Object.defineProperty(process, 'ppid', { get: () => originalPpid, configurable: true })
    }
  })

  it('returns a no-op when already orphaned at startup (ppid <= 1)', () => {
    const onOrphaned = vi.fn()
    const originalPpid = process.ppid

    Object.defineProperty(process, 'ppid', { get: () => 1, configurable: true })

    try {
      const stop = startParentWatchdog(onOrphaned, 1000)

      // Should not fire even after time passes
      vi.advanceTimersByTime(10000)
      expect(onOrphaned).not.toHaveBeenCalled()

      // stop() should not throw
      expect(() => stop()).not.toThrow()
    } finally {
      Object.defineProperty(process, 'ppid', { get: () => originalPpid, configurable: true })
    }
  })

  it('stop() prevents further checks', () => {
    const onOrphaned = vi.fn()
    let ppid = 1234
    const originalPpid = process.ppid

    Object.defineProperty(process, 'ppid', { get: () => ppid, configurable: true })

    try {
      const stop = startParentWatchdog(onOrphaned, 1000)

      stop()

      ppid = 1
      vi.advanceTimersByTime(10000)

      expect(onOrphaned).not.toHaveBeenCalled()
    } finally {
      Object.defineProperty(process, 'ppid', { get: () => originalPpid, configurable: true })
    }
  })
})
