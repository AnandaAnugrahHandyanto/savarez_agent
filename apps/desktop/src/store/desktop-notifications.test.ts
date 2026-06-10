import { afterEach, describe, expect, it, vi } from 'vitest'

const mockStore = new Map<string, string>()

vi.mock('@/lib/storage', () => ({
  storedBoolean: (key: string, fallback: boolean) => {
    const val = mockStore.get(key)
    return val === undefined ? fallback : val === 'true'
  },
  persistBoolean: (key: string, value: boolean) => {
    mockStore.set(key, String(value))
  }
}))

describe('desktop-notifications store', () => {
  afterEach(async () => {
    mockStore.clear()
    vi.resetModules()
  })

  it('defaults to true (notifications enabled)', async () => {
    const mod = await import('./desktop-notifications')
    expect(mod.$desktopNotificationsEnabled.get()).toBe(true)
  })

  it('setDesktopNotificationsEnabled updates the atom', async () => {
    const mod = await import('./desktop-notifications')
    mod.setDesktopNotificationsEnabled(false)
    expect(mod.$desktopNotificationsEnabled.get()).toBe(false)

    mod.setDesktopNotificationsEnabled(true)
    expect(mod.$desktopNotificationsEnabled.get()).toBe(true)
  })

  it('toggleDesktopNotificationsEnabled flips the value', async () => {
    const mod = await import('./desktop-notifications')
    mod.$desktopNotificationsEnabled.set(true)
    mod.toggleDesktopNotificationsEnabled()
    expect(mod.$desktopNotificationsEnabled.get()).toBe(false)

    mod.toggleDesktopNotificationsEnabled()
    expect(mod.$desktopNotificationsEnabled.get()).toBe(true)
  })

  it('persists value changes to localStorage', async () => {
    const mod = await import('./desktop-notifications')
    mod.setDesktopNotificationsEnabled(false)
    expect(mockStore.get('hermes.desktop.notifications.enabled')).toBe('false')

    mod.setDesktopNotificationsEnabled(true)
    expect(mockStore.get('hermes.desktop.notifications.enabled')).toBe('true')
  })

  it('restores persisted value from localStorage', async () => {
    mockStore.set('hermes.desktop.notifications.enabled', 'false')
    const mod = await import('./desktop-notifications')
    expect(mod.$desktopNotificationsEnabled.get()).toBe(false)
  })
})
