import { describe, expect, it } from 'vitest'

import { effortLabel, modelLabel } from '../components/appChrome.js'

describe('status bar model label', () => {
  it('keeps medium reasoning visible as @med', () => {
    expect(modelLabel('gpt-5.5', 'medium')).toBe('gpt 5.5@med')
  })

  it('shortens minimal reasoning and keeps explicit efforts adjacent to the model', () => {
    expect(modelLabel('openai/gpt-5.5', 'minimal')).toBe('gpt 5.5@min')
    expect(modelLabel('openai/gpt-5.5', 'xhigh')).toBe('gpt 5.5@xhigh')
  })

  it('omits only neutral/default effort labels', () => {
    expect(effortLabel('default')).toBe('')
    expect(effortLabel('normal')).toBe('')
    expect(modelLabel('gpt-5.5')).toBe('gpt 5.5')
  })

  it('keeps fast as a separate suffix after the effort', () => {
    expect(modelLabel('gpt-5.5', 'medium', true)).toBe('gpt 5.5@med fast')
  })
})
