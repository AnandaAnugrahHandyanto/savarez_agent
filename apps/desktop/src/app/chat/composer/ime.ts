import type { KeyboardEvent as ReactKeyboardEvent } from 'react'

const CHROMIUM_IME_PROCESSING_KEY_CODE = 229

export function isImeComposingKeyEvent(event: ReactKeyboardEvent<HTMLElement>): boolean {
  // Chromium/Electron can report the IME confirmation key as keyCode 229
  // even when isComposing is already false by the time React handles keydown.
  // Treat it as composition so Enter confirms CJK preedit text instead of
  // submitting the composer.
  return event.nativeEvent.isComposing || event.nativeEvent.keyCode === CHROMIUM_IME_PROCESSING_KEY_CODE
}
