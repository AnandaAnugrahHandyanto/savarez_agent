import { describe, expect, it } from 'vitest'

import { stringWidth } from './stringWidth.js'

describe('stringWidth', () => {
  it('treats common text-presentation prompt symbols as one terminal cell', () => {
    expect(stringWidth('❯')).toBe(1)
    expect(stringWidth('⚠')).toBe(1)
  })

  it('keeps emoji-presentation dingbats wide', () => {
    expect(stringWidth('✅')).toBe(2)
    expect(stringWidth('⚠️')).toBe(2)
  })
})
