import { describe, expect, it } from 'vitest'

import { arrayBufferToBase64, imageUploadPayloadFromFile, imageUploadPayloadFromPath } from './image-upload'

describe('image upload helpers', () => {
  it('encodes binary data as base64 without leaking file paths', async () => {
    const file = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], 'C:\\Users\\alice\\Screenshot 2026.png', {
      type: 'image/png'
    })

    const payload = await imageUploadPayloadFromFile(file)

    expect(payload).toEqual({
      data_base64: 'iVBORw==',
      filename: 'Screenshot 2026.png',
      mime_type: 'image/png'
    })
    expect(Object.values(payload).join(' ')).not.toContain('Users')
  })

  it('extracts base64 payloads from data URLs read from local paths', () => {
    const payload = imageUploadPayloadFromPath('/Users/alice/Desktop/private.png', 'data:image/png;base64,iVBORw==')

    expect(payload).toEqual({
      data_base64: 'iVBORw==',
      filename: 'private.png',
      mime_type: 'image/png'
    })
    expect(Object.values(payload).join(' ')).not.toContain('/Users/alice')
  })

  it('encodes array buffers in chunks', () => {
    expect(arrayBufferToBase64(new Uint8Array([0, 1, 2, 253, 254, 255]).buffer)).toBe('AAEC/f7/')
  })
})
