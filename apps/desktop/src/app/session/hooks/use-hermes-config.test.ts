import { describe, expect, it } from 'vitest'

import { isFileBrowserHoverRevealEnabled } from './use-hermes-config'

describe('isFileBrowserHoverRevealEnabled', () => {
  it('defaults to enabled for existing configs', () => {
    expect(isFileBrowserHoverRevealEnabled({})).toBe(true)
    expect(isFileBrowserHoverRevealEnabled({ display: {} })).toBe(true)
  })

  it('honors an explicit false value', () => {
    expect(isFileBrowserHoverRevealEnabled({ display: { hover_reveal_file_browser: false } })).toBe(false)
  })

  it('keeps hover reveal enabled when explicitly true', () => {
    expect(isFileBrowserHoverRevealEnabled({ display: { hover_reveal_file_browser: true } })).toBe(true)
  })
})
