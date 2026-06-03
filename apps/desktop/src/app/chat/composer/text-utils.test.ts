import { describe, expect, it } from 'vitest'

import { detectTrigger, extractClipboardImageBlobs } from './text-utils'

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

describe('extractClipboardImageBlobs', () => {
  it('does not duplicate a screenshot exposed through both items and files', () => {
    const image = new File(['png'], 'screenshot.png', { type: 'image/png' })
    const duplicateImage = new File(['png'], 'screenshot.png', { type: 'image/png' })
    const clipboard = {
      files: {
        item: (index: number) => (index === 0 ? duplicateImage : null),
        length: 1
      },
      getData: () => '',
      items: [
        {
          getAsFile: () => image,
          kind: 'file',
          type: 'image/png'
        }
      ]
    } as unknown as DataTransfer

    expect(extractClipboardImageBlobs(clipboard)).toHaveLength(1)
  })
})
