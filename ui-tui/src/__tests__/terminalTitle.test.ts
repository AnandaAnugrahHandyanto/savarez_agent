import { describe, expect, it } from 'vitest'

import { buildTerminalTitle } from '../app/terminalTitle.js'

describe('buildTerminalTitle', () => {
  it('prefers the session topic over the model name', () => {
    expect(
      buildTerminalTitle({
        busy: false,
        fallbackLabel: 'Hermes',
        model: 'anthropic/claude-sonnet-4',
        status: 'ready',
        title: 'Fix terminal tab titles'
      })
    ).toBe('Fix terminal tab titles — Hermes')
  })

  it('appends current activity while busy', () => {
    expect(
      buildTerminalTitle({
        busy: true,
        fallbackLabel: 'Hermes',
        model: 'anthropic/claude-sonnet-4',
        status: 'searching files',
        title: 'Fix terminal tab titles'
      })
    ).toBe('Fix terminal tab titles · searching files — Hermes')
  })

  it('falls back to the model and activity when no session topic exists yet', () => {
    expect(
      buildTerminalTitle({
        busy: true,
        fallbackLabel: 'Hermes',
        model: 'anthropic/claude-sonnet-4',
        status: 'running pytest',
        title: ''
      })
    ).toBe('⏳ claude-sonnet-4 · running pytest — Hermes')
  })

  it('falls back to the model when no topic or specific activity exists yet', () => {
    expect(
      buildTerminalTitle({
        busy: false,
        fallbackLabel: 'Hermes',
        model: 'openai/gpt-5.4',
        status: 'ready',
        title: ''
      })
    ).toBe('✓ gpt-5.4 — Hermes')
  })
})
