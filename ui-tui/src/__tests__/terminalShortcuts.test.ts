import { describe, expect, it } from 'vitest'

import type { TerminalCapabilities } from '../lib/terminalCapabilities.js'
import { classifyKeyEvent } from '../lib/terminalShortcuts.js'

const caps = (pasteShortcutShapes: string[], copyShortcutShapes: string[] = ['ctrl+shift+c']): TerminalCapabilities => ({
  keyboard: { copyShortcutShapes, pasteShortcutShapes }
})

const macCaps = caps(['super+v', 'ctrl+shift+v'], ['super+c', 'super+shift+c', 'ctrl+shift+c'])
const linuxCaps = caps(['ctrl+shift+v', 'alt+v'])
const remoteCaps = caps(['super+v', 'ctrl+shift+v'], ['super+c', 'super+shift+c', 'ctrl+shift+c'])

describe('classifyKeyEvent', () => {
  it('keeps Option+C as text instead of copy/noop', () => {
    expect(
      classifyKeyEvent({
        input: 'c',
        raw: '\x1bc',
        key: { ctrl: false, meta: true, shift: false, super: false },
        caps: macCaps,
        state: { busy: false, hasSelection: false }
      })
    ).toEqual({ type: 'text', text: 'c' })
  })

  it('classifies forwarded Cmd+C over SSH as copy when a selection exists', () => {
    expect(
      classifyKeyEvent({
        input: 'c',
        raw: '\x1b[99;9u',
        key: { ctrl: false, meta: false, shift: false, super: true },
        caps: remoteCaps,
        state: { busy: false, hasSelection: true }
      })
    ).toEqual({ type: 'copy' })
  })

  it('classifies forwarded Cmd+V over SSH as paste', () => {
    expect(
      classifyKeyEvent({
        input: 'v',
        raw: '\x1b[118;9u',
        key: { ctrl: false, meta: false, shift: false, super: true },
        caps: remoteCaps,
        state: { busy: false, hasSelection: false }
      })
    ).toEqual({ type: 'paste', source: 'hotkey' })
  })

  it('classifies kitty-protocol Cmd+C as copy only when a selection exists', () => {
    expect(
      classifyKeyEvent({
        input: 'c',
        raw: '\x1b[99;9u',
        key: { ctrl: false, meta: false, shift: false, super: true },
        caps: macCaps,
        state: { busy: false, hasSelection: true }
      })
    ).toEqual({ type: 'copy' })

    expect(
      classifyKeyEvent({
        input: 'c',
        raw: '\x1b[99;9u',
        key: { ctrl: false, meta: false, shift: false, super: true },
        caps: macCaps,
        state: { busy: false, hasSelection: false }
      })
    ).toEqual({ type: 'noop' })
  })

  it('keeps plain Ctrl+C as interrupt', () => {
    expect(
      classifyKeyEvent({
        input: 'c',
        raw: '\x03',
        key: { ctrl: true, meta: false, shift: false, super: false },
        caps: linuxCaps,
        state: { busy: false, hasSelection: false }
      })
    ).toEqual({ type: 'interrupt' })
  })

  it('classifies Ctrl+Shift+C as copy on non-mac terminals', () => {
    expect(
      classifyKeyEvent({
        input: 'c',
        raw: '\x1b[99;6u',
        key: { ctrl: true, meta: false, shift: true, super: false },
        caps: linuxCaps,
        state: { busy: false, hasSelection: true }
      })
    ).toEqual({ type: 'copy' })
  })

  it('classifies bracketed paste before shortcut modifiers', () => {
    expect(
      classifyKeyEvent({
        input: 'v',
        raw: '\x1b[200~hello',
        key: { ctrl: true, meta: false, shift: true, super: false },
        caps: linuxCaps,
        state: { busy: false, hasSelection: false }
      })
    ).toEqual({ type: 'paste', source: 'bracketed' })
  })

  it('classifies paste hotkeys from terminal capabilities', () => {
    expect(
      classifyKeyEvent({
        input: 'v',
        raw: 'v',
        key: { ctrl: true, meta: false, shift: true, super: false },
        caps: linuxCaps,
        state: { busy: false, hasSelection: false }
      })
    ).toEqual({ type: 'paste', source: 'hotkey' })

    expect(
      classifyKeyEvent({
        input: 'v',
        raw: '\x1b[118;9u',
        key: { ctrl: false, meta: false, shift: false, super: true },
        caps: macCaps,
        state: { busy: false, hasSelection: false }
      })
    ).toEqual({ type: 'paste', source: 'hotkey' })
  })
})
