import { describe, expect, it } from 'vitest'

import { composerUsesStackedLayout, draftRequestsStackedComposer } from './layout'

describe('composer layout mode', () => {
  it('does not switch to stacked layout for a long single-line prompt', () => {
    const longSingleLine = 'explain this without moving the prompt box under my cursor '.repeat(12)

    expect(draftRequestsStackedComposer(longSingleLine)).toBe(false)
    expect(composerUsesStackedLayout({ draft: longSingleLine, narrow: false, tight: false })).toBe(false)
  })

  it('uses stacked layout for explicit multiline prompts and constrained widths', () => {
    expect(composerUsesStackedLayout({ draft: 'line one\nline two', narrow: false, tight: false })).toBe(true)
    expect(composerUsesStackedLayout({ draft: 'short', narrow: true, tight: false })).toBe(true)
    expect(composerUsesStackedLayout({ draft: 'short', narrow: false, tight: true })).toBe(true)
  })
})
