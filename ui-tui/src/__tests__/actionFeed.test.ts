import { describe, expect, it } from 'vitest'

import { actionStatusGlyph, foldActionDetail, parseActionCall } from '../lib/actionFeed.js'

describe('actionFeed formatter', () => {
  it.each([
    ['Read File("/tmp/project/src/app.ts")', 'Read …/src/app.ts'],
    ['Search Files("statusbar")', 'Searched "statusbar"'],
    ['Terminal("pytest tests/foo.py -q")', 'Ran "pytest tests/foo.py -q"'],
    ['Patch("ui-tui/src/components/appChrome.tsx")', 'Edited …/components/appChrome.tsx'],
    ['Write File("docs/plan.md")', 'Wrote docs/plan.md'],
    ['Todo', 'Updated todos'],
    ['Delegate Task("review implementation")', 'Delegated "review implementation"']
  ])('formats %s as %s', (input, expected) => {
    expect(parseActionCall(input).title).toBe(expected)
  })

  it('ignores duration suffixes when parsing the action subject', () => {
    expect(parseActionCall('Terminal("npm test") (1.2s)').title).toBe('Ran "npm test"')
  })

  it('folds long multiline detail bodies', () => {
    const folded = foldActionDetail(['Result:', 'line 1', 'line 2', 'line 3', 'line 4', 'line 5'].join('\n'), 3)

    expect(folded.preview).toBe(['Result:', 'line 1', 'line 2'].join('\n'))
    expect(folded.hiddenLines).toBe(3)
  })

  it('returns stable status glyphs', () => {
    expect(actionStatusGlyph('running')).toBe('●')
    expect(actionStatusGlyph('success')).toBe('✓')
    expect(actionStatusGlyph('error')).toBe('✗')
  })
})
