import { describe, expect, it, vi, beforeEach } from 'vitest'

// Mock localStorage before importing the module
const store: Record<string, string> = {}
const mockStorage = {
  getItem: vi.fn((key: string) => store[key] ?? null),
  setItem: vi.fn((key: string, value: string) => { store[key] = value }),
  removeItem: vi.fn((key: string) => { delete store[key] }),
  clear: vi.fn(() => { for (const k in store) delete store[k] }),
  get length() { return Object.keys(store).length },
  key: vi.fn((i: number) => Object.keys(store)[i] ?? null)
}

vi.stubGlobal('localStorage', mockStorage)
vi.stubGlobal('window', { localStorage: mockStorage })

// Dynamic import after mocking so module-level storedBoolean sees the mock
const { $sidebarHideToolSessions } = await import('./layout')

describe('$sidebarHideToolSessions', () => {
  beforeEach(() => {
    mockStorage.clear()
    mockStorage.getItem.mockClear()
    mockStorage.setItem.mockClear()
    $sidebarHideToolSessions.set(false)
  })

  it('defaults to false', () => {
    expect($sidebarHideToolSessions.get()).toBe(false)
  })

  it('toggles on set(true)', () => {
    $sidebarHideToolSessions.set(true)
    expect($sidebarHideToolSessions.get()).toBe(true)
  })

  it('toggles back to false', () => {
    $sidebarHideToolSessions.set(true)
    $sidebarHideToolSessions.set(false)
    expect($sidebarHideToolSessions.get()).toBe(false)
  })

  it('persists via localStorage on change', () => {
    $sidebarHideToolSessions.set(true)
    expect(mockStorage.setItem).toHaveBeenCalledWith('hermes.desktop.hideToolSessions', 'true')
  })
})
