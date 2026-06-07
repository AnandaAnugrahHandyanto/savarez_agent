import { describe, expect, it } from 'vitest'
import { parseSlash } from './slashExec'

describe('parseSlash', () => {
  it('should parse simple command without arguments', () => {
    const result = parseSlash('/help')
    expect(result).toEqual({ name: 'help', arg: '' })
  })

  it('should parse command with single-line argument', () => {
    const result = parseSlash('/goal Write a Python script')
    expect(result).toEqual({ name: 'goal', arg: 'Write a Python script' })
  })

  it('should parse command with multi-line argument (with newline)', () => {
    const result = parseSlash('/goal Write a Python\nthat prints Hello')
    expect(result).toEqual({ name: 'goal', arg: 'Write a Python\nthat prints Hello' })
  })

  it('should handle multiple newlines in argument', () => {
    const result = parseSlash('/goal Line 1\nLine 2\nLine 3')
    expect(result).toEqual({ name: 'goal', arg: 'Line 1\nLine 2\nLine 3' })
  })

  it('should handle command with leading slashes', () => {
    const result = parseSlash('//goal Write something')
    expect(result).toEqual({ name: 'goal', arg: 'Write something' })
  })

  it('should handle command with trailing whitespace in argument', () => {
    const result = parseSlash('/goal Some text  ')
    expect(result).toEqual({ name: 'goal', arg: 'Some text' })
  })

  it('should return empty name and arg for invalid commands', () => {
    const result = parseSlash('not a command')
    expect(result).toEqual({ name: '', arg: '' })
  })

  it('should handle tabs and newlines mixed in argument', () => {
    const result = parseSlash('/goal\tWrite something\nand more')
    expect(result).toEqual({ name: 'goal', arg: 'Write something\nand more' })
  })

  it('should parse /goal with comprehensive multiline example', () => {
    const input = `/goal Create a comprehensive testing framework
that supports unit tests
and integration tests
with clear documentation`
    const result = parseSlash(input)
    expect(result.name).toBe('goal')
    expect(result.arg).toContain('Create a comprehensive testing framework')
    expect(result.arg).toContain('unit tests')
    expect(result.arg).toContain('integration tests')
    expect(result.arg).toContain('clear documentation')
  })
})
