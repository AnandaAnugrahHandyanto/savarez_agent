import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ComposerControls } from './controls'
import type { ChatBarState } from './types'

const state: ChatBarState = {
  model: { canSwitch: true, model: 'mimo-v2.5-pro', provider: 'custom' },
  tools: { enabled: true, label: 'Tools' },
  voice: { active: false, enabled: true }
}

const conversation = () => ({
  active: false,
  level: 0,
  muted: false,
  onEnd: vi.fn(),
  onStart: vi.fn(),
  onStopTurn: vi.fn(),
  onToggleMute: vi.fn(),
  status: 'listening' as const
})

function renderControls(overrides: Partial<Parameters<typeof ComposerControls>[0]> = {}) {
  return render(
    <ComposerControls
      busy={false}
      busyAction="stop"
      canSubmit={false}
      conversation={conversation()}
      disabled={false}
      hasComposerPayload={false}
      onDictate={vi.fn()}
      state={state}
      voiceStatus="idle"
      {...overrides}
    />
  )
}

afterEach(() => {
  cleanup()
})

describe('ComposerControls', () => {
  it('shows voice conversation when the composer has no payload', () => {
    renderControls()

    expect(screen.getByRole('button', { name: 'Start voice conversation' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Send' })).toBeNull()
  })

  it('shows send when the composer has a payload', () => {
    renderControls({ canSubmit: true, hasComposerPayload: true })

    expect(screen.getByRole('button', { name: 'Send' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Start voice conversation' })).toBeNull()
  })
})
