interface ImeCompositionKeyEvent {
  nativeEvent?: {
    isComposing?: boolean
    keyCode?: number
  }
}

const IME_PROCESSING_KEY_CODE = 229

export function isImeCompositionKeyEvent(event: ImeCompositionKeyEvent) {
  return Boolean(event.nativeEvent?.isComposing || event.nativeEvent?.keyCode === IME_PROCESSING_KEY_CODE)
}
