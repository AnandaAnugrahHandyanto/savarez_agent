import { describe, expect, it } from 'vitest'

import { isImeComposing } from './ime'

describe('isImeComposing', () => {
  it('treats explicit composition state as active', () => {
    expect(isImeComposing({}, true)).toBe(true)
    expect(isImeComposing({ isComposing: true })).toBe(true)
    expect(isImeComposing({ nativeEvent: { isComposing: true } })).toBe(true)
  })

  it('recognizes process-key events emitted while an IME owns Enter', () => {
    expect(isImeComposing({ keyCode: 229 })).toBe(true)
    expect(isImeComposing({ which: 229 })).toBe(true)
    expect(isImeComposing({ nativeEvent: { keyCode: 229 } })).toBe(true)
    expect(isImeComposing({ nativeEvent: { which: 229 } })).toBe(true)
  })

  it('leaves normal Enter key events alone', () => {
    expect(isImeComposing({ keyCode: 13, nativeEvent: { keyCode: 13, isComposing: false } })).toBe(false)
  })
})
