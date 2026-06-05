import { describe, expect, it } from 'vitest'

import {
  ambiguousModelDisplayNames,
  displayModelName,
  formatModelStatusLabel,
  modelDisplayParts,
  reasoningEffortLabel
} from './model-status-label'

describe('model-status-label', () => {
  it('formats display names consistently', () => {
    expect(displayModelName('anthropic/claude-opus-4.8-fast')).toBe('Opus 4.8')
    expect(displayModelName('openai/gpt-5.5')).toBe('GPT-5.5')
  })

  it('can preserve provider-prefixed model ids for ambiguous picker rows', () => {
    expect(modelDisplayParts('anthropic/claude-opus-4.8-fast', { preserveProviderPrefix: true })).toEqual({
      name: 'anthropic/claude-opus-4.8',
      tag: 'Fast'
    })
  })

  it('detects friendly display names that would collapse distinct model ids', () => {
    expect([...ambiguousModelDisplayNames(['anthropic/claude-sonnet-4.6', 'openrouter/claude-sonnet-4.6'])]).toEqual([
      'Sonnet 4.6'
    ])
  })

  it('maps reasoning effort to compact labels', () => {
    expect(reasoningEffortLabel('high')).toBe('High')
    expect(reasoningEffortLabel('xhigh')).toBe('Max')
    expect(reasoningEffortLabel('')).toBe('')
  })

  it('appends fast + effort session state to the status label', () => {
    expect(formatModelStatusLabel('openai/gpt-5.5', { fastMode: true, reasoningEffort: 'high' })).toBe(
      'GPT-5.5 · Fast High'
    )
  })

  it('always surfaces the effort (default medium) so the level is visible', () => {
    expect(formatModelStatusLabel('openai/gpt-5.5', { reasoningEffort: 'medium' })).toBe('GPT-5.5 · Med')
    expect(formatModelStatusLabel('openai/gpt-5.5')).toBe('GPT-5.5 · Med')
  })

  it('returns just the placeholder name when there is no model', () => {
    expect(formatModelStatusLabel('')).toBe('No model')
  })
})
