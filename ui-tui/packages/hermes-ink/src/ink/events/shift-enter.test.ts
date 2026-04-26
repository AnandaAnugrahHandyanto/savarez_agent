import { describe, expect, it } from 'vitest'

import { parseMultipleKeypresses } from '../parse-keypress.js'

import { InputEvent } from './input-event.js'

function eventFor(sequence: string) {
  const [keys] = parseMultipleKeypresses({ incomplete: '', mode: 'NORMAL' }, sequence)
  expect(keys).toHaveLength(1)
  const parsed = keys[0]
  expect(parsed?.kind).toBe('key')

  return new InputEvent(parsed as Extract<typeof parsed, { kind: 'key' }>)
}

describe('InputEvent Shift+Enter', () => {
  it('recognizes Kitty CSI-u Shift+Enter as a shifted return', () => {
    const event = eventFor('\x1b[13;2u')

    expect(event.key.return).toBe(true)
    expect(event.key.shift).toBe(true)
    expect(event.input).toBe('')
  })

  it('recognizes xterm modifyOtherKeys Shift+Enter as a shifted return', () => {
    const event = eventFor('\x1b[27;2;13~')

    expect(event.key.return).toBe(true)
    expect(event.key.shift).toBe(true)
    expect(event.input).toBe('')
  })
})
