import { describe, expect, it } from 'vitest'

import { thinkingHeaderLabel } from '../components/thinking.js'

describe('thinkingHeaderLabel', () => {
  it('distinguishes live thinking from completed reasoning', () => {
    expect(thinkingHeaderLabel(true)).toBe('Thinking')
    expect(thinkingHeaderLabel(false)).toBe('Reasoning')
  })
})
