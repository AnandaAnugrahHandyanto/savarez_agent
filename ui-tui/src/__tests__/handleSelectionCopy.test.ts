import { describe, expect, it, vi } from 'vitest'

import {
  CLIPBOARD_COPY_TOAST_LABEL,
  CLIPBOARD_COPY_TOAST_MSG,
  handleSelectionCopy,
} from '../app/useMainApp.js'

describe('handleSelectionCopy', () => {
  it('pushes a success toast when copy returns text', async () => {
    const pushToast = vi.fn()
    const selection = { copySelectionNoClear: () => Promise.resolve('some selected text') }

    const result = await handleSelectionCopy(selection, pushToast)

    expect(result).toBe('some selected text')
    expect(pushToast).toHaveBeenCalledTimes(1)
    expect(pushToast).toHaveBeenCalledWith(
      CLIPBOARD_COPY_TOAST_LABEL,
      CLIPBOARD_COPY_TOAST_MSG,
      'success',
    )
  })

  it('does NOT push a toast when copy returns empty string', async () => {
    const pushToast = vi.fn()
    const selection = { copySelectionNoClear: () => Promise.resolve('') }

    const result = await handleSelectionCopy(selection, pushToast)

    expect(result).toBe('')
    expect(pushToast).not.toHaveBeenCalled()
  })


  it('handles promise rejection gracefully (copySelectionNoClear never rejects)', async () => {
    const pushToast = vi.fn()
    const selection = { copySelectionNoClear: () => Promise.reject(new Error('unexpected')) }

    await expect(handleSelectionCopy(selection, pushToast)).rejects.toThrow('unexpected')
    expect(pushToast).not.toHaveBeenCalled()
  })
})
