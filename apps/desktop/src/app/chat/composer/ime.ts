import type { KeyboardEvent as ReactKeyboardEvent } from 'react'

/**
 * Browser/Electron IME composition sends keydown events while the candidate
 * string is still being committed. Enter during that phase means "accept the
 * IME candidate", not "submit the chat message".
 */
export function isImeCompositionKey(event: ReactKeyboardEvent<HTMLElement>) {
  const syntheticEvent = event as ReactKeyboardEvent<HTMLElement> & { isComposing?: boolean }
  const nativeEvent = event.nativeEvent as KeyboardEvent & { isComposing?: boolean }

  return Boolean(syntheticEvent.isComposing || nativeEvent.isComposing || nativeEvent.keyCode === 229)
}
