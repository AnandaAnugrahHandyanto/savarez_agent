import { describe, expect, it } from 'vitest'

import { detectTrigger, isComposingKeyboardEvent } from './text-utils'

describe('detectTrigger', () => {
  it('detects a bare slash trigger with an empty query', () => {
    expect(detectTrigger('/')).toEqual({ kind: '/', query: '', tokenLength: 1 })
  })

  it('detects a slash command query', () => {
    expect(detectTrigger('/skill')).toEqual({ kind: '/', query: 'skill', tokenLength: 6 })
  })

  it('detects a bare at-mention trigger with an empty query', () => {
    expect(detectTrigger('@')).toEqual({ kind: '@', query: '', tokenLength: 1 })
  })

  it('detects an at-mention query', () => {
    expect(detectTrigger('@file')).toEqual({ kind: '@', query: 'file', tokenLength: 5 })
  })

  it('returns null for plain text', () => {
    expect(detectTrigger('hello there')).toBeNull()
  })
})

describe('isComposingKeyboardEvent', () => {
  it('recognizes browser IME composition flags so Enter can confirm conversion', () => {
    expect(isComposingKeyboardEvent({ isComposing: true, key: 'Enter', nativeEvent: {} })).toBe(true)
    expect(isComposingKeyboardEvent({ key: 'Enter', nativeEvent: { isComposing: true } })).toBe(true)
  })

  it('recognizes keyCode 229 IME process events from Electron/browser quirks', () => {
    expect(isComposingKeyboardEvent({ key: 'Enter', keyCode: 229, nativeEvent: {} })).toBe(true)
    expect(isComposingKeyboardEvent({ key: 'Enter', nativeEvent: { keyCode: 229 } })).toBe(true)
    expect(isComposingKeyboardEvent({ key: 'Process', nativeEvent: {} })).toBe(true)
  })

  it('does not treat normal Enter as composition', () => {
    expect(isComposingKeyboardEvent({ key: 'Enter', keyCode: 13, nativeEvent: { isComposing: false } })).toBe(false)
  })
})
