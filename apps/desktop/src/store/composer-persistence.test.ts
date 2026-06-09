import { describe, expect, it } from 'vitest'

import { $composerDraft } from './composer'

describe('$composerDraft cross-navigation persistence', () => {
  it('stores and retrieves a non-empty draft', () => {
    $composerDraft.set('hello world')
    expect($composerDraft.get()).toBe('hello world')
    $composerDraft.set('')
  })

  it('returns empty string by default', () => {
    expect($composerDraft.get()).toBe('')
  })

  it('round-trips multiline text', () => {
    const text = 'line one\n\nline two'
    $composerDraft.set(text)
    expect($composerDraft.get()).toBe(text)
    $composerDraft.set('')
  })
})
