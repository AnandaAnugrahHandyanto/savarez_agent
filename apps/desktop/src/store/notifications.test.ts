import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { $notifications, clearNotifications, notify } from './notifications'

describe('notification native delivery', () => {
  let nativeNotify: ReturnType<typeof vi.fn>

  beforeEach(() => {
    nativeNotify = vi.fn().mockResolvedValue(true)
    Object.defineProperty(window, 'hermesDesktop', {
      configurable: true,
      value: { notify: nativeNotify }
    })
  })

  afterEach(() => {
    clearNotifications()
    $notifications.set([])
    vi.restoreAllMocks()
    Reflect.deleteProperty(window, 'hermesDesktop')
  })

  it('mirrors warning and error to native notifications so they are visible outside the toast stack', () => {
    notify({ kind: 'warning', title: 'Voice recording failed', message: 'No microphone signal was detected.' })

    expect(nativeNotify).toHaveBeenCalledWith({
      title: 'Voice recording failed',
      body: 'No microphone signal was detected.',
      silent: true
    })
  })

  it('keeps visible success notifications in-app only', () => {
    notify({ kind: 'success', title: 'Saved', message: 'Done.' })

    expect(nativeNotify).not.toHaveBeenCalled()
  })
})
