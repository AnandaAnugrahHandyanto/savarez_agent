import { beforeEach, describe, expect, it } from 'vitest'

import { assignSkinToProfile, resolveSkinForProfile } from './context'
import { DEFAULT_SKIN_NAME } from './presets'

describe('per-profile theme resolution', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('falls back to the built-in default when nothing is assigned', () => {
    expect(resolveSkinForProfile('default')).toBe(DEFAULT_SKIN_NAME)
    expect(resolveSkinForProfile('work')).toBe(DEFAULT_SKIN_NAME)
  })

  it('keeps each profile on its own assigned skin', () => {
    assignSkinToProfile('work', 'ember')
    assignSkinToProfile('default', 'midnight')

    expect(resolveSkinForProfile('work')).toBe('ember')
    expect(resolveSkinForProfile('default')).toBe('midnight')
  })

  it('lets an unassigned profile inherit the default profile as the global fallback', () => {
    // Setting the default profile also seeds the legacy global skin, so any
    // profile without its own assignment inherits it rather than the built-in.
    assignSkinToProfile('default', 'mono')

    expect(resolveSkinForProfile('never-themed')).toBe('mono')
  })

  it('normalizes an unknown stored skin back to the default', () => {
    assignSkinToProfile('work', 'not-a-real-skin')

    expect(resolveSkinForProfile('work')).toBe(DEFAULT_SKIN_NAME)
  })
})
