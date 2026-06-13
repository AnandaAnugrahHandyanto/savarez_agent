import { beforeEach, describe, expect, it, vi } from 'vitest'
import { atom } from 'nanostores'

vi.mock('@/hermes', () => ({
  getProfiles: vi.fn(),
  setApiRequestProfile: vi.fn()
}))

vi.mock('@/lib/query-client', () => ({
  queryClient: { invalidateQueries: vi.fn() }
}))

vi.mock('@/lib/storage', () => ({
  arraysEqual: (a: unknown[], b: unknown[]) => a.length === b.length && a.every((value, index) => value === b[index]),
  persistBoolean: vi.fn(),
  persistStringArray: vi.fn(),
  persistStringRecord: vi.fn(),
  storedBoolean: vi.fn(() => false),
  storedStringArray: vi.fn(() => []),
  storedStringRecord: vi.fn(() => ({}))
}))

const ensureGatewayForProfile = vi.fn(async () => undefined)

vi.mock('@/store/gateway', () => ({
  $gateway: atom({}),
  ensureGatewayForProfile
}))

describe('profile sidebar scope', () => {
  beforeEach(async () => {
    ensureGatewayForProfile.mockClear()
    const profile = await import('./profile')
    profile.$profiles.set([
      { name: 'default', path: '', is_default: true } as never,
      { name: 'google_search_agent', path: '', is_default: false } as never,
      { name: 'investment_agent', path: '', is_default: false } as never
    ])
    profile.$profileOrder.set([])
    profile.$activeGatewayProfile.set('default')
    profile.$selectedProfileScope.set('default')
    profile.$showAllProfiles.set(false)
    profile.$newChatProfile.set(null)
  })

  it('shows the selected profile history immediately without waiting for gateway connection', async () => {
    const profile = await import('./profile')

    profile.selectProfile('google_search_agent')

    expect(profile.$profileScope.get()).toBe('google_search_agent')
    expect(profile.$newChatProfile.get()).toBe('google_search_agent')
    expect(ensureGatewayForProfile).toHaveBeenCalledWith('google_search_agent')
  })

  it('does not let live gateway changes overwrite the browsed sidebar profile', async () => {
    const profile = await import('./profile')

    profile.selectProfile('investment_agent')
    profile.$activeGatewayProfile.set('default')

    expect(profile.$profileScope.get()).toBe('investment_agent')
  })

  it('cycles from the selected sidebar profile, not the live gateway profile', async () => {
    const profile = await import('./profile')

    profile.$activeGatewayProfile.set('default')
    profile.$selectedProfileScope.set('google_search_agent')

    profile.cycleProfile(1)

    expect(profile.$profileScope.get()).toBe('investment_agent')
  })
})
