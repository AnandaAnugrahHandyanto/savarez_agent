import { describe, expect, it } from 'vitest'

import { isImeComposing } from './keyboard'

describe('isImeComposing', () => {
  it('matches active IME composition events', () => {
    expect(isImeComposing({ isComposing: true, keyCode: 13 } as KeyboardEvent)).toBe(true)
  })

  it('matches the legacy Chromium process key fallback', () => {
    expect(isImeComposing({ isComposing: false, keyCode: 229 } as KeyboardEvent)).toBe(true)
  })

  it('does not match a plain Enter key press', () => {
    expect(isImeComposing({ isComposing: false, keyCode: 13 } as KeyboardEvent)).toBe(false)
  })
})
