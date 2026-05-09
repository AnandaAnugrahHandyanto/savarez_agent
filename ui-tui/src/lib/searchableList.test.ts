import { describe, expect, it } from 'vitest'

import { handleSearchInput, reconcileIndexedSelection } from './searchableList.js'

describe('handleSearchInput', () => {
  it('activates search on slash', () => {
    let active = false
    let query = ''

    const consumed = handleSearchInput('/', {}, {
      active,
      setActive: v => {
        active = v
      },
      setQuery: v => {
        query = typeof v === 'function' ? v(query) : v
      }
    })

    expect(consumed).toBe(true)
    expect(active).toBe(true)
    expect(query).toBe('')
  })

  it('edits an active query and reports query changes', () => {
    let active = true
    let changes = 0
    let query = 'cl'

    const setQuery = (v: string | ((prev: string) => string)) => {
      query = typeof v === 'function' ? v(query) : v
    }

    expect(handleSearchInput('a', {}, {
      active,
      onQueryChange: () => {
        changes += 1
      },
      setActive: v => {
        active = v
      },
      setQuery
    })).toBe(true)
    expect(query).toBe('cla')

    expect(handleSearchInput(undefined, { backspace: true }, {
      active,
      onQueryChange: () => {
        changes += 1
      },
      setActive: v => {
        active = v
      },
      setQuery
    })).toBe(true)
    expect(query).toBe('cl')
    expect(changes).toBe(2)
  })

  it('clears the query on Ctrl+U in Ink key shape', () => {
    let active = true
    let changes = 0
    let query = 'opus'

    const consumed = handleSearchInput('u', { ctrl: true }, {
      active,
      onQueryChange: () => {
        changes += 1
      },
      setActive: v => {
        active = v
      },
      setQuery: v => {
        query = typeof v === 'function' ? v(query) : v
      }
    })

    expect(consumed).toBe(true)
    expect(active).toBe(true)
    expect(query).toBe('')
    expect(changes).toBe(1)
  })

  it('exits active search on escape without clearing the query', () => {
    let active = true
    let query = 'opus'

    const consumed = handleSearchInput(undefined, { escape: true }, {
      active,
      setActive: v => {
        active = v
      },
      setQuery: v => {
        query = typeof v === 'function' ? v(query) : v
      }
    })

    expect(consumed).toBe(true)
    expect(active).toBe(false)
    expect(query).toBe('opus')
  })

  it('lets navigation and selection keys pass through while search is active', () => {
    let active = true
    let query = 'opus'

    const opts = {
      active,
      setActive: (v: boolean) => {
        active = v
      },
      setQuery: (v: string | ((prev: string) => string)) => {
        query = typeof v === 'function' ? v(query) : v
      }
    }

    expect(handleSearchInput(undefined, { downArrow: true }, opts)).toBe(false)
    expect(handleSearchInput(undefined, { return: true }, opts)).toBe(false)
    expect(active).toBe(true)
    expect(query).toBe('opus')
  })

  it('reports the first visible item when indexed selection is filtered out', () => {
    const filtered = [{ index: 2 }, { index: 4 }]

    expect(reconcileIndexedSelection(filtered, 4)).toBeNull()
    expect(reconcileIndexedSelection(filtered, 0)).toBe(2)
    expect(reconcileIndexedSelection([], 0)).toBeNull()
  })
})
