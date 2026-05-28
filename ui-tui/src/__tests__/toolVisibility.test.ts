import { describe, expect, it } from 'vitest'

import {
  parseToolTrailEntry,
  shouldToolEntryAutoOpen,
  summarizeDelegationControls
} from '../lib/toolVisibility.js'

describe('parseToolTrailEntry', () => {
  it('turns verbose completed tool lines into expandable sections', () => {
    const entry = parseToolTrailEntry(
      'Terminal("npm test") (1.3s) :: Args:\n{ "cmd": "npm test" }\nResult:\npassed ✓'
    )

    expect(entry).toEqual({
      call: 'Terminal("npm test")',
      detail: 'Args:\n{ "cmd": "npm test" }\nResult:\npassed',
      duration: ' (1.3s)',
      mark: '✓',
      sections: [
        { label: 'Args', text: '{ "cmd": "npm test" }' },
        { label: 'Result', text: 'passed' }
      ],
      status: 'done'
    })
  })

  it('auto-opens error rows but keeps successful rows collapsed by default', () => {
    const failed = parseToolTrailEntry('Terminal("npm test") (0.5s) :: Error:\nfailed ✗')
    const ok = parseToolTrailEntry('Read File("x") (0.1s) ✓')

    expect(shouldToolEntryAutoOpen(failed)).toBe(true)
    expect(shouldToolEntryAutoOpen(ok)).toBe(false)
  })
})

describe('summarizeDelegationControls', () => {
  it('shows pause/capacity controls for live delegation', () => {
    expect(
      summarizeDelegationControls({ maxConcurrentChildren: 3, maxSpawnDepth: 2, paused: false }, false)
    ).toEqual({
      capsLabel: 'caps d2/3',
      controlsHint: ' · x kill · X subtree · p pause',
      titleSuffix: ''
    })
  })

  it('locks destructive controls during replay while preserving capacity context', () => {
    expect(
      summarizeDelegationControls({ maxConcurrentChildren: 5, maxSpawnDepth: 1, paused: true }, true)
    ).toEqual({
      capsLabel: 'caps d1/5',
      controlsHint: ' · controls locked',
      titleSuffix: ' · ⏸ paused'
    })
  })
})
