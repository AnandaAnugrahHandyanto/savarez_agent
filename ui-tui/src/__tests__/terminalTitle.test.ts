import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { buildTerminalTitle } from '../domain/terminalTitle.js'

describe('buildTerminalTitle', () => {
  const origHome = process.env.HOME

  beforeEach(() => {
    process.env.HOME = '/Users/bb'
  })

  afterEach(() => {
    process.env.HOME = origHome
  })

  it('prefers the session title before model and cwd', () => {
    expect(
      buildTerminalTitle({
        cwd: '/Users/bb/projects/hermes-agent',
        marker: '✓',
        model: 'openrouter/deepseek-v4-pro',
        sessionTitle: 'Quarterly planning'
      })
    ).toBe('✓ Quarterly planning · deepseek-v4-pro · ~/projects/hermes-agent')
  })

  it('preserves the previous model and cwd title when there is no session title', () => {
    expect(
      buildTerminalTitle({
        cwd: '/Users/bb/projects/hermes-agent',
        marker: '⏳',
        model: 'anthropic/claude-sonnet-4'
      })
    ).toBe('⏳ claude-sonnet-4 · ~/projects/hermes-agent')
  })

  it('sanitizes blank and control-character titles', () => {
    expect(
      buildTerminalTitle({
        marker: '✓',
        model: 'openai/gpt-5.5',
        sessionTitle: '  Release\nplanning\u001b[31m  '
      })
    ).toBe('✓ Release planning · gpt-5.5')
  })
})
