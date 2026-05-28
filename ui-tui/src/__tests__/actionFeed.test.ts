import { describe, expect, it } from 'vitest'

import { actionStatusGlyph, foldActionDetail, parseActionCall, selectVisibleActionFeedItems } from '../lib/actionFeed.js'

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

  it('limits visible actions to important and recent items', () => {
    const actions = [
      { label: 'Read File("a")', status: 'success' as const },
      { label: 'Search Files("b")', status: 'success' as const },
      { label: 'Read File("c")', status: 'success' as const },
      { label: 'Patch("src/app.ts")', status: 'success' as const },
      { label: 'Search Files("d")', status: 'success' as const },
      { label: 'Todo', status: 'success' as const },
      { label: 'Read File("e")', status: 'success' as const },
      { label: 'Terminal("npm test")', status: 'running' as const }
    ]

    const selected = selectVisibleActionFeedItems(actions)

    expect(selected.hidden).toBe(3)
    expect(selected.items.map(item => item.label)).toEqual([
      'Patch("src/app.ts")',
      'Search Files("d")',
      'Todo',
      'Read File("e")',
      'Terminal("npm test")'
    ])
  })
})
