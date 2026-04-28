import { describe, expect, it } from 'vitest'

import { completionReplacementOnSubmit } from '../app/useSubmission.js'

describe('completionReplacementOnSubmit', () => {
  it('does not consume Enter for an exact slash command completion with trailing space', () => {
    expect(completionReplacementOnSubmit('/clear', 'clear ', 1)).toBeNull()
  })

  it('still completes partial slash commands', () => {
    expect(completionReplacementOnSubmit('/cl', 'clear ', 1)).toBe('/clear ')
  })

  it('does not swallow Enter for slash commands with arguments', () => {
    expect(completionReplacementOnSubmit('/clear extra', 'clear ', 1)).toBe('/clear ')
  })

  it('does not rewrite exact slash completions even without trailing space', () => {
    expect(completionReplacementOnSubmit('/clear', 'clear', 1)).toBeNull()
  })

  it('still completes non-slash path-like completions', () => {
    expect(completionReplacementOnSubmit('@fo', '@foo.md', 0)).toBe('@foo.md')
  })
})
