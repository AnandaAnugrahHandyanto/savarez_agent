import { type Dispatch, type SetStateAction, useEffect, useMemo } from 'react'

import { createFuzzyFilter } from './fuzzy.js'

export interface IndexedEntry {
  index: number
}

interface InkKey {
  backspace?: boolean
  ctrl?: boolean
  delete?: boolean
  downArrow?: boolean
  escape?: boolean
  meta?: boolean
  return?: boolean
  upArrow?: boolean
}

interface SearchInputOptions {
  active: boolean
  onQueryChange?: () => void
  setActive: (active: boolean) => void
  setQuery: Dispatch<SetStateAction<string>>
}

const isClearQueryKey = (ch: string | undefined, key: InkKey): boolean =>
  ch === '\u0015' || (key.ctrl === true && ch?.toLowerCase() === 'u')

export function handleSearchInput(ch: string | undefined, key: InkKey, opts: SearchInputOptions): boolean {
  if (opts.active) {
    if (key.escape) {
      opts.setActive(false)

      return true
    }

    if (key.backspace || key.delete) {
      opts.setQuery(q => q.slice(0, -1))
      opts.onQueryChange?.()

      return true
    }

    if (isClearQueryKey(ch, key)) {
      opts.setQuery('')
      opts.onQueryChange?.()

      return true
    }

    if (ch && !key.ctrl && !key.meta && !key.return) {
      opts.setQuery(q => q + ch)
      opts.onQueryChange?.()

      return true
    }

    return false
  }

  if (ch === '/') {
    opts.setActive(true)

    return true
  }

  if (isClearQueryKey(ch, key)) {
    opts.setQuery('')
    opts.onQueryChange?.()

    return true
  }

  return false
}

export function reconcileIndexedSelection<T extends IndexedEntry>(filtered: T[], selectedIndex: number): number | null {
  if (!filtered.length || filtered.some(entry => entry.index === selectedIndex)) {
    return null
  }

  return filtered[0]!.index
}

export function useIndexedFuzzyList<T extends IndexedEntry>(
  entries: T[],
  query: string,
  keys: readonly string[],
  selectedIndex: number,
  setSelectedIndex: Dispatch<SetStateAction<number>>,
  enabled = true
) {
  const search = useMemo(() => createFuzzyFilter(entries, keys), [entries, keys])
  const filtered = useMemo(() => search(query), [query, search])
  const selectedPosition = Math.max(0, filtered.findIndex(entry => entry.index === selectedIndex))

  useEffect(() => {
    if (!enabled) {
      return
    }

    const nextIndex = reconcileIndexedSelection(filtered, selectedIndex)

    if (nextIndex !== null) {
      setSelectedIndex(nextIndex)
    }
  }, [enabled, filtered, selectedIndex, setSelectedIndex])

  return { filtered, selectedPosition }
}
