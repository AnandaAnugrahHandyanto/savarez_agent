export type TerminalSignalInput = {
  env: NodeJS.ProcessEnv
  platform: NodeJS.Platform
  isStdinTty?: boolean
  isStdoutTty?: boolean
}

export type TerminalSignals = {
  platform: NodeJS.Platform
  isStdinTty: boolean
  isStdoutTty: boolean
  ssh: {
    hasSshConnection: boolean
    hasSshClient: boolean
    hasSshTty: boolean
  }
  multiplexer: {
    tmux: boolean
    screen: boolean
    zellij: boolean
    cy: boolean
  }
  env: {
    TERM?: string
    TERM_PROGRAM?: string
    TERM_PROGRAM_VERSION?: string
    KITTY_WINDOW_ID?: string
    WEZTERM_PANE?: string
    GHOSTTY_RESOURCES_DIR?: string
    ITERM_SESSION_ID?: string
    LC_TERMINAL?: string
    TERM_SESSION_ID?: string
  }
}

const terminalEnvKeys = [
  'TERM',
  'TERM_PROGRAM',
  'TERM_PROGRAM_VERSION',
  'KITTY_WINDOW_ID',
  'WEZTERM_PANE',
  'GHOSTTY_RESOURCES_DIR',
  'ITERM_SESSION_ID',
  'LC_TERMINAL',
  'TERM_SESSION_ID'
] as const

type TerminalEnvKey = (typeof terminalEnvKeys)[number]

const pick = (env: NodeJS.ProcessEnv, key: string): string | undefined => {
  const value = env[key]

  return typeof value === 'string' && value.length > 0 ? value : undefined
}

const collectEnvSignals = (env: NodeJS.ProcessEnv): TerminalSignals['env'] => {
  const signals: Partial<Record<TerminalEnvKey, string>> = {}

  for (const key of terminalEnvKeys) {
    const value = pick(env, key)

    if (value !== undefined) {
      signals[key] = value
    }
  }

  return signals as TerminalSignals['env']
}

export function collectTerminalSignals(input: TerminalSignalInput): TerminalSignals {
  const env = input.env

  return {
    platform: input.platform,
    isStdinTty: input.isStdinTty === true,
    isStdoutTty: input.isStdoutTty === true,
    ssh: {
      hasSshConnection: pick(env, 'SSH_CONNECTION') !== undefined,
      hasSshClient: pick(env, 'SSH_CLIENT') !== undefined,
      hasSshTty: pick(env, 'SSH_TTY') !== undefined
    },
    multiplexer: {
      tmux: pick(env, 'TMUX') !== undefined,
      screen: pick(env, 'STY') !== undefined,
      zellij: pick(env, 'ZELLIJ') !== undefined,
      cy: pick(env, 'CY') !== undefined
    },
    env: collectEnvSignals(env)
  }
}
