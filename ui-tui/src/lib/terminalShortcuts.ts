import type { TerminalCapabilities } from './terminalCapabilities.js'

export type ShortcutKey = {
  ctrl: boolean
  shift?: boolean
  meta: boolean
  super?: boolean
}

export type ShortcutState = {
  busy: boolean
  hasSelection: boolean
}

export type ClassifyInput = {
  input: string
  raw: string
  key: ShortcutKey
  caps: TerminalCapabilities
  state: ShortcutState
}

export type TerminalAction =
  | { type: 'copy' }
  | { source: 'bracketed' | 'hotkey'; type: 'paste' }
  | { type: 'interrupt' }
  | { type: 'noop' }
  | { text: string; type: 'text' }

function supportsShortcut(caps: TerminalCapabilities, shortcut: string): boolean {
  return caps.keyboard.copyShortcutShapes.includes(shortcut) || caps.keyboard.pasteShortcutShapes.includes(shortcut)
}

function isPasteHotkey(i: ClassifyInput): boolean {
  const ch = i.input.toLowerCase()

  if (ch !== 'v') {
    return false
  }

  if (i.key.ctrl && i.key.shift && supportsShortcut(i.caps, 'ctrl+shift+v')) {
    return true
  }

  if (i.key.super === true && !i.key.shift && supportsShortcut(i.caps, 'super+v')) {
    return true
  }

  if (!i.key.ctrl && !i.key.super && i.key.meta && supportsShortcut(i.caps, 'alt+v')) {
    return true
  }

  if (i.key.ctrl && !i.key.shift && !i.key.meta && i.key.super !== true && supportsShortcut(i.caps, 'ctrl+v')) {
    return true
  }

  return false
}

function classifyCopyChord(i: ClassifyInput): TerminalAction | undefined {
  const ch = i.input.toLowerCase()

  if (ch !== 'c') {
    return undefined
  }

  const isSuperC = i.key.super === true && !i.key.shift && supportsShortcut(i.caps, 'super+c')
  const isSuperShiftC = i.key.super === true && i.key.shift && supportsShortcut(i.caps, 'super+shift+c')

  if (isSuperC || isSuperShiftC) {
    return i.state.hasSelection ? { type: 'copy' } : { type: 'noop' }
  }

  if (i.key.ctrl && i.key.shift && !i.key.meta && i.key.super !== true && supportsShortcut(i.caps, 'ctrl+shift+c')) {
    return i.state.hasSelection ? { type: 'copy' } : { type: 'noop' }
  }

  if (i.key.ctrl && !i.key.shift && !i.key.meta && i.key.super !== true) {
    return { type: 'interrupt' }
  }

  return undefined
}

export function classifyKeyEvent(i: ClassifyInput): TerminalAction {
  if (i.raw.startsWith('\x1b[200~')) {
    return { type: 'paste', source: 'bracketed' }
  }

  if (isPasteHotkey(i)) {
    return { type: 'paste', source: 'hotkey' }
  }

  const copy = classifyCopyChord(i)

  if (copy) {
    return copy
  }

  if (i.raw === '\x03' && i.key.ctrl && !i.key.shift && !i.key.meta && i.key.super !== true) {
    return { type: 'interrupt' }
  }

  return i.input ? { type: 'text', text: i.input } : { type: 'noop' }
}

export const classifyTerminalInput = classifyKeyEvent
