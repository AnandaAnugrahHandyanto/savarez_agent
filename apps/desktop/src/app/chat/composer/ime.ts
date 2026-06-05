interface ImeKeyboardEventLike {
  isComposing?: boolean
  keyCode?: number
  nativeEvent?: {
    isComposing?: boolean
    keyCode?: number
    which?: number
  }
  which?: number
}

const IME_PROCESSING_KEY_CODE = 229

export function isImeComposing(event: ImeKeyboardEventLike, composing = false) {
  if (composing) {
    return true
  }

  return (
    event.isComposing === true ||
    event.nativeEvent?.isComposing === true ||
    event.keyCode === IME_PROCESSING_KEY_CODE ||
    event.which === IME_PROCESSING_KEY_CODE ||
    event.nativeEvent?.keyCode === IME_PROCESSING_KEY_CODE ||
    event.nativeEvent?.which === IME_PROCESSING_KEY_CODE
  )
}
