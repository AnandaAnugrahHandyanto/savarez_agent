import { describe, expect, it } from 'vitest'

import { isImeCompositionKeyEvent } from './ime'

describe('isImeCompositionKeyEvent', () => {
  it('treats Enter keydown during IME composition as composing so it does not submit', () => {
    const event = {
      key: 'Enter',
      nativeEvent: { isComposing: true }
    }

    expect(isImeCompositionKeyEvent(event)).toBe(true)
  })

  it('treats macOS IME composition Enter with keyCode 229 as composing', () => {
    const event = {
      key: 'Enter',
      nativeEvent: { isComposing: false, keyCode: 229 }
    }

    expect(isImeCompositionKeyEvent(event)).toBe(true)
  })

  it('does not treat normal Enter as composing', () => {
    const event = {
      key: 'Enter',
      nativeEvent: { isComposing: false, keyCode: 13 }
    }

    expect(isImeCompositionKeyEvent(event)).toBe(false)
  })
})
