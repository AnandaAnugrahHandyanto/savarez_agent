import { afterEach, describe, expect, it } from 'vitest'

import { $activeModeId, $agentModes, cycleActiveMode, DEFAULT_AGENT_MODES, NO_MODE_ID } from '../app/modeStore.js'
import { applyModePrompt } from '../app/useSubmission.js'

describe('applyModePrompt', () => {
  afterEach(() => {
    $agentModes.set(DEFAULT_AGENT_MODES)
    $activeModeId.set(NO_MODE_ID)
  })

  it('does not inject instructions for hidden/no-mode entries', () => {
    $agentModes.set([
      {
        color: '#D7D7D7',
        description: 'No mode',
        hidden: true,
        id: NO_MODE_ID,
        label: 'No Mode',
        prompt: 'should not inject'
      }
    ])
    $activeModeId.set(NO_MODE_ID)

    expect(applyModePrompt('hello')).toBe('hello')
  })

  it('escapes mode names before inserting them into the wrapper attribute', () => {
    $agentModes.set([
      {
        color: '#111111',
        id: 'review',
        label: 'Review "<Mode>"',
        description: 'review mode',
        prompt: 'review carefully'
      }
    ])
    $activeModeId.set('review')

    expect(applyModePrompt('hello')).toBe(
      '<mode_instructions name="Review &quot;&lt;Mode&gt;&quot;">\nreview carefully\n</mode_instructions>\n\nhello'
    )
  })

  it('cycles through visible modes and no-mode, skipping hidden custom modes', () => {
    $agentModes.set([
      {
        color: '#D7D7D7',
        description: 'No mode',
        hidden: true,
        id: NO_MODE_ID,
        label: 'No Mode'
      },
      {
        color: '#111111',
        description: 'Hidden mode',
        hidden: true,
        id: 'hidden-review',
        label: 'Hidden Review'
      },
      {
        color: '#222222',
        description: 'Visible mode',
        id: 'review',
        label: 'Review'
      }
    ])
    $activeModeId.set(NO_MODE_ID)

    expect(cycleActiveMode().id).toBe('review')
    expect(cycleActiveMode().id).toBe(NO_MODE_ID)
  })
})
