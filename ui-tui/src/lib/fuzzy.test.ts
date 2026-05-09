import { describe, expect, it } from 'vitest'

import { createFuzzyFilter, fuzzyFilter, queryMatchesText } from './fuzzy.js'

interface Item {
  label: string
  slug: string
}

const items: Item[] = [
  { label: 'Anthropic', slug: 'anthropic' },
  { label: 'Google Gemini', slug: 'gemini' },
  { label: 'OpenAI Codex', slug: 'openai-codex' }
]

describe('fuzzyFilter', () => {
  it('returns the original list for blank queries', () => {
    expect(fuzzyFilter(items, '', ['label'])).toBe(items)
    expect(fuzzyFilter(items, '   ', ['label'])).toBe(items)
  })

  it('filters using the same tokenized subsequence contract as the Python picker', () => {
    expect(fuzzyFilter(items, 'gem', ['label']).map(item => item.slug)).toEqual(['gemini'])
  })

  it('searches across the configured keys', () => {
    expect(fuzzyFilter(items, 'codex', ['label', 'slug']).map(item => item.slug)).toEqual(['openai-codex'])
  })

  it('matches model abbreviations users type in model pickers', () => {
    const models = [
      { label: 'claude-opus-4-7' },
      { label: 'claude-sonnet-4-6' },
      { label: 'claude-haiku-4-5' },
      { label: 'gpt-5-codex' }
    ]

    expect(fuzzyFilter(models, 'co47', ['label']).map(item => item.label)).toEqual(['claude-opus-4-7'])
    expect(fuzzyFilter(models, 'co 47', ['label']).map(item => item.label)).toEqual(['claude-opus-4-7'])
    expect(fuzzyFilter(models, 'cl 4', ['label']).map(item => item.label)).toEqual([
      'claude-opus-4-7',
      'claude-sonnet-4-6',
      'claude-haiku-4-5'
    ])
  })

  it('can reuse a prepared matcher across queries', () => {
    const search = createFuzzyFilter(items, ['label', 'slug'])

    expect(search('gem').map(item => item.slug)).toEqual(['gemini'])
    expect(search('codex').map(item => item.slug)).toEqual(['openai-codex'])
  })

  it('requires every query token to match as a subsequence', () => {
    expect(queryMatchesText('OpenAI Codex', 'open cod')).toBe(true)
    expect(queryMatchesText('OpenAI Chat Completions', 'open cod')).toBe(false)
  })

  it('does not assemble a single query token across separate fields', () => {
    const providers = [
      { name: 'Nous Portal', slug: 'nous' },
      { name: 'OpenRouter', slug: 'openrouter', status: 'needs setup' },
      { name: 'LM Studio', slug: 'lm-studio', status: 'needs setup' }
    ]

    expect(fuzzyFilter(providers, 'nous', ['name', 'slug', 'status']).map(item => item.name)).toEqual([
      'Nous Portal'
    ])
  })
})
