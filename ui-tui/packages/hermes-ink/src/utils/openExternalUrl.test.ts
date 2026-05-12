import { describe, expect, it } from 'vitest'

import { commandForExternalUrl } from './openExternalUrl.js'

describe('commandForExternalUrl', () => {
  it('opens safe external URLs with the platform opener', () => {
    expect(commandForExternalUrl('https://example.com', 'darwin')).toEqual({
      command: 'open',
      args: ['https://example.com']
    })
    expect(commandForExternalUrl('mailto:test@example.com', 'linux')).toEqual({
      command: 'xdg-open',
      args: ['mailto:test@example.com']
    })
  })

  it('rejects malformed and unsafe URLs', () => {
    expect(commandForExternalUrl('not a url', 'darwin')).toBeUndefined()
    expect(commandForExternalUrl('javascript:alert(1)', 'darwin')).toBeUndefined()
    expect(commandForExternalUrl('file:///etc/passwd', 'darwin')).toBeUndefined()
  })
})
