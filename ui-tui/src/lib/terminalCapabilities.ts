import type { TerminalSignals } from './terminalSignals.js'

export type TerminalCapabilities = {
  keyboard: {
    copyShortcutShapes: string[]
    pasteShortcutShapes: string[]
  }
}

const MAC_PASTE_SHORTCUTS = ['super+v', 'ctrl+shift+v'] as const
const DEFAULT_PASTE_SHORTCUTS = ['ctrl+shift+v', 'alt+v'] as const
const SUPER_COPY_SHORTCUTS = ['super+c', 'super+shift+c', 'ctrl+shift+c'] as const
const DEFAULT_COPY_SHORTCUTS = ['ctrl+shift+c'] as const

const hasMacTerminalHint = (signals: TerminalSignals): boolean =>
  signals.platform === 'darwin' ||
  signals.env.LC_TERMINAL === 'iTerm2' ||
  signals.env.TERM_PROGRAM === 'iTerm.app' ||
  signals.env.TERM_PROGRAM === 'Apple_Terminal' ||
  signals.env.ITERM_SESSION_ID !== undefined ||
  signals.env.TERM_SESSION_ID !== undefined

const hasRemoteShell = (signals: TerminalSignals): boolean =>
  signals.ssh.hasSshConnection || signals.ssh.hasSshClient || signals.ssh.hasSshTty

export function deriveTerminalCapabilities(signals: TerminalSignals): TerminalCapabilities {
  const supportsSuperClipboard = hasMacTerminalHint(signals) || hasRemoteShell(signals)

  return {
    keyboard: {
      copyShortcutShapes: [...(supportsSuperClipboard ? SUPER_COPY_SHORTCUTS : DEFAULT_COPY_SHORTCUTS)],
      pasteShortcutShapes: [...(supportsSuperClipboard ? MAC_PASTE_SHORTCUTS : DEFAULT_PASTE_SHORTCUTS)]
    }
  }
}
