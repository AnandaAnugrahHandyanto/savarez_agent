import { describe, expect, it } from 'vitest'

import {
  supportsKittyKeyboardForTerminal,
  supportsModifyOtherKeysForTerminal
} from './terminal.js'

describe('extended keyboard mode selection', () => {
  it('enables xterm modifyOtherKeys for plain xterm-compatible terminals', () => {
    expect(supportsModifyOtherKeysForTerminal({ term: 'xterm-256color', terminal: undefined })).toBe(true)
  })

  it('keeps kitty keyboard protocol on the conservative allowlist', () => {
    expect(supportsKittyKeyboardForTerminal({ term: 'xterm-256color', terminal: undefined })).toBe(false)
    expect(supportsKittyKeyboardForTerminal({ term: 'xterm-kitty', terminal: 'kitty' })).toBe(true)
  })
})
