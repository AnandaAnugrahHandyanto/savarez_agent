import { describe, expect, it } from 'vitest'

import { extractClipboardImageBlobs } from './text-utils'

function fileList(files: File[]): FileList {
  return {
    length: files.length,
    item: (index: number) => files[index] ?? null,
    ...Object.fromEntries(files.map((file, index) => [index, file]))
  } as unknown as FileList
}

function clipboard(overrides: Partial<DataTransfer>): DataTransfer {
  return {
    files: fileList([]),
    getData: () => '',
    items: [] as unknown as DataTransferItemList,
    ...overrides
  } as DataTransfer
}

describe('extractClipboardImageBlobs', () => {
  it('dedupes the same pasted image exposed through items and files', () => {
    const itemImage = new File(['same-image'], 'clipboard.png', { type: 'image/png' })
    const fileImage = new File(['same-image'], 'screenshot.png', { type: 'image/png' })

    const data = clipboard({
      files: fileList([fileImage]),
      items: [
        {
          getAsFile: () => itemImage,
          kind: 'file',
          type: 'image/png'
        }
      ] as unknown as DataTransferItemList
    })

    expect(extractClipboardImageBlobs(data)).toEqual([itemImage])
  })

  it('keeps image files that were not already exposed as clipboard items', () => {
    const itemImage = new File(['first'], 'first.png', { type: 'image/png' })
    const secondImage = new File(['second-image'], 'second.png', { type: 'image/png' })

    const data = clipboard({
      files: fileList([secondImage]),
      items: [
        {
          getAsFile: () => itemImage,
          kind: 'file',
          type: 'image/png'
        }
      ] as unknown as DataTransferItemList
    })

    expect(extractClipboardImageBlobs(data)).toEqual([itemImage, secondImage])
  })
})
