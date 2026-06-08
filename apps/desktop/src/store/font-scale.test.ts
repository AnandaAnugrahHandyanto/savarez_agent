import { beforeEach, describe, expect, it, vi } from 'vitest'

// Mock document.documentElement before importing the module
const mockSetProperty = vi.fn()
const mockGetItem = vi.fn()
const mockSetItem = vi.fn()

Object.defineProperty(globalThis, 'document', {
  value: { documentElement: { style: { setProperty: mockSetProperty } } },
  writable: true
})

Object.defineProperty(globalThis, 'window', {
  value: { localStorage: { getItem: mockGetItem, setItem: mockSetItem } },
  writable: true
})

describe('font-scale store', () => {
  beforeEach(() => {
    vi.resetModules()
    mockSetProperty.mockClear()
    mockGetItem.mockReset()
    mockSetItem.mockClear()
  })

  it('defaults to 1 when no stored value', async () => {
    mockGetItem.mockReturnValue(null)
    const { $fontScale } = await import('./font-scale')
    expect($fontScale.get()).toBe(1)
  })

  it('loads stored value within range', async () => {
    mockGetItem.mockReturnValue('1.25')
    const { $fontScale } = await import('./font-scale')
    expect($fontScale.get()).toBe(1.25)
  })

  it('falls back to 1 for out-of-range values', async () => {
    mockGetItem.mockReturnValue('5')
    const { $fontScale } = await import('./font-scale')
    expect($fontScale.get()).toBe(1)
  })

  it('falls back to 1 for non-numeric values', async () => {
    mockGetItem.mockReturnValue('abc')
    const { $fontScale } = await import('./font-scale')
    expect($fontScale.get()).toBe(1)
  })

  it('setFontScale clamps to valid range', async () => {
    mockGetItem.mockReturnValue('1')
    const { $fontScale, setFontScale } = await import('./font-scale')

    setFontScale(0.5) // below min 0.8
    expect($fontScale.get()).toBe(0.8)

    setFontScale(3) // above max 2
    expect($fontScale.get()).toBe(2)

    setFontScale(1.15)
    expect($fontScale.get()).toBe(1.15)
  })

  it('persists to localStorage on change', async () => {
    mockGetItem.mockReturnValue('1')
    const { setFontScale } = await import('./font-scale')

    setFontScale(1.25)
    expect(mockSetItem).toHaveBeenCalledWith('hermes.desktop.fontScale', '1.25')
  })

  it('sets CSS variable on change', async () => {
    mockGetItem.mockReturnValue('1')
    const { setFontScale } = await import('./font-scale')

    setFontScale(1.5)
    expect(mockSetProperty).toHaveBeenCalledWith('--dt-font-scale', '1.5')
  })

  it('applyFontScaleBoot sets CSS variable for non-default scale', async () => {
    mockGetItem.mockReturnValue('1.2')
    const { applyFontScaleBoot } = await import('./font-scale')

    applyFontScaleBoot()
    expect(mockSetProperty).toHaveBeenCalledWith('--dt-font-scale', '1.2')
  })

  it('applyFontScaleBoot skips CSS variable for default scale', async () => {
    mockGetItem.mockReturnValue('1')
    const { applyFontScaleBoot } = await import('./font-scale')

    mockSetProperty.mockClear() // Clear initial subscribe call
    applyFontScaleBoot()
    expect(mockSetProperty).not.toHaveBeenCalled()
  })
})
