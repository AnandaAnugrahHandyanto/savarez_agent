import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import { describe, expect, it } from 'vitest'

import { isImeComposingKeyEvent } from './ime'

function keyEvent({ isComposing = false, keyCode = 13 }: { isComposing?: boolean; keyCode?: number }) {
  return {
    nativeEvent: {
      isComposing,
      keyCode
    }
  } as ReactKeyboardEvent<HTMLElement>
}

describe('isImeComposingKeyEvent', () => {
  it('detects standard composing key events', () => {
    expect(isImeComposingKeyEvent(keyEvent({ isComposing: true }))).toBe(true)
  })

  it('detects Chromium IME processing keyCode 229 after isComposing flips false', () => {
    expect(isImeComposingKeyEvent(keyEvent({ isComposing: false, keyCode: 229 }))).toBe(true)
  })

  it('does not treat normal Enter as IME composition', () => {
    expect(isImeComposingKeyEvent(keyEvent({ isComposing: false, keyCode: 13 }))).toBe(false)
  })
})
