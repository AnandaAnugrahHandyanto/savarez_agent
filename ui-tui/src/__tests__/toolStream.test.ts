import { describe, expect, it } from 'vitest'

import {
  buildToolStreamSummary,
  classifyToolStreamTrailLine,
  toolStreamRune
} from '../lib/toolStream.js'

describe('tool stream sculpture helpers', () => {
  it('gives completed tool rows semantic runes instead of a generic bullet', () => {
    expect(classifyToolStreamTrailLine('Read File("src/app.tsx") ✓')).toEqual({
      detail: '',
      label: 'Read File("src/app.tsx")',
      mark: '✓',
      rune: '✔',
      tone: 'success'
    })
  })

  it('keeps failed tool rows visually distinct', () => {
    expect(classifyToolStreamTrailLine('Terminal("npm test") :: exit code 1 ✗')).toEqual({
      detail: 'exit code 1',
      label: 'Terminal("npm test")',
      mark: '✗',
      rune: '✗',
      tone: 'error'
    })
  })

  it('summarizes live/completed/failed tool flow for the panel header', () => {
    expect(
      buildToolStreamSummary({
        active: 2,
        completed: 5,
        failed: 1,
        tokensLabel: '~1.2k tokens'
      })
    ).toBe('2 live · 5 done · 1 failed · ~1.2k tokens')
  })

  it('uses cockpit runes for active, draft, and analysis rows', () => {
    expect(toolStreamRune('active')).toBe('⚙')
    expect(toolStreamRune('draft')).toBe('✎')
    expect(toolStreamRune('analysis')).toBe('◐')
  })
})
