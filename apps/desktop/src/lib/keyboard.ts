export function isImeComposing(event: KeyboardEvent): boolean {
  // Chromium/Electron sets isComposing for modern IMEs. keyCode 229 is the
  // legacy "Process" fallback still seen with some CJK composition flows.
  return event.isComposing || event.keyCode === 229
}
