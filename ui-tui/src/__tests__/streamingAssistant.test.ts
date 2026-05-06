import { describe, expect, it } from 'vitest'

import { submissionPlaceholderLabel } from '../components/streamingAssistant.js'

describe('submissionPlaceholderLabel', () => {
  it('shows a working label while the turn is busy but no live content exists yet', () => {
    expect(
      submissionPlaceholderLabel({
        busy: true,
        hasLiveContent: false,
        status: 'running…'
      })
    ).toBe('working…')
  })

  it('preserves more specific non-running statuses', () => {
    expect(
      submissionPlaceholderLabel({
        busy: true,
        hasLiveContent: false,
        status: 'queued for next turn'
      })
    ).toBe('queued for next turn')
  })

  it('hides the placeholder once real live content arrives', () => {
    expect(
      submissionPlaceholderLabel({
        busy: true,
        hasLiveContent: true,
        status: 'running…'
      })
    ).toBeNull()
  })

  it('hides the placeholder when the session is idle', () => {
    expect(
      submissionPlaceholderLabel({
        busy: false,
        hasLiveContent: false,
        status: 'ready'
      })
    ).toBeNull()
  })
})
