import { atom } from 'nanostores'

import { deriveTerminalCapabilities, type TerminalCapabilities } from '../lib/terminalCapabilities.js'
import { collectTerminalSignals, type TerminalSignals } from '../lib/terminalSignals.js'

export type TerminalEnvironment = {
  capabilities: TerminalCapabilities
  signals: TerminalSignals
}

export const createTerminalEnvironment = (env: NodeJS.ProcessEnv = process.env): TerminalEnvironment => {
  const signals = collectTerminalSignals({
    env,
    platform: process.platform,
    isStdinTty: process.stdin.isTTY ?? false,
    isStdoutTty: process.stdout.isTTY ?? false
  })

  return { signals, capabilities: deriveTerminalCapabilities(signals) }
}

export const $terminalEnvironment = atom<TerminalEnvironment>(createTerminalEnvironment())
