const queryTokens = (query: string): string[] => query.trim().toLowerCase().split(/\s+/).filter(Boolean)

function isSubsequence(haystack: string, needle: string): boolean {
  let pos = 0

  for (const ch of needle) {
    pos = haystack.indexOf(ch, pos)

    if (pos < 0) {
      return false
    }

    pos += 1
  }

  return true
}

function searchableFields<T>(item: T, keys: readonly string[]): string[] {
  const record = item as Record<string, unknown>

  return keys.map(key => String(record[key] ?? '').toLowerCase()).filter(Boolean)
}

export function queryMatchesText(text: string, query: string): boolean {
  const normalized = text.toLowerCase()
  const tokens = queryTokens(query)

  if (!tokens.length) {
    return true
  }

  return tokens.every(token => isSubsequence(normalized, token))
}

export function createFuzzyFilter<T>(items: T[], keys: readonly string[]) {
  return (query: string): T[] => {
    const tokens = queryTokens(query)

    if (!tokens.length) {
      return items
    }

    return items.filter(item => {
      const fields = searchableFields(item, keys)

      return tokens.every(token => fields.some(field => isSubsequence(field, token)))
    })
  }
}

export function fuzzyFilter<T>(items: T[], query: string, keys: readonly string[]): T[] {
  return createFuzzyFilter(items, keys)(query)
}
