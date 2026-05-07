import { describe, expect, it } from 'vitest'

import { deriveTerminalCapabilities } from '../lib/terminalCapabilities.js'
import { collectTerminalSignals } from '../lib/terminalSignals.js'

const deriveFromEnv = (env: NodeJS.ProcessEnv, platform: NodeJS.Platform = 'linux') =>
  deriveTerminalCapabilities(
    collectTerminalSignals({
      env,
      platform,
      isStdinTty: true,
      isStdoutTty: true
    })
  )

describe('deriveTerminalCapabilities', () => {
  it('enables forwarded super clipboard shortcuts for SSH sessions', () => {
    const caps = deriveFromEnv({ SSH_CONNECTION: '1 2 3 4', TERM: 'xterm-256color' })

    expect(caps.keyboard.copyShortcutShapes).toContain('super+c')
    expect(caps.keyboard.pasteShortcutShapes).toContain('super+v')
  })

  it('does not treat local Linux Super+C/V as clipboard shortcuts', () => {
    const caps = deriveFromEnv({ TERM: 'xterm-256color' })

    expect(caps.keyboard.copyShortcutShapes).not.toContain('super+c')
    expect(caps.keyboard.pasteShortcutShapes).not.toContain('super+v')
  })
})
