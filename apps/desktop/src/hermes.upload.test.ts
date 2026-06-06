import { beforeEach, describe, expect, it, vi } from 'vitest'

import { uploadAttachment } from './hermes'

// Unit coverage for the REST half of the remote-desktop attachment fix. The
// full submit-path regression (syncImageAttachmentsForSubmit uploads bytes and
// never forwards a C:\ path to a remote backend) lives alongside
// use-prompt-actions.test.tsx; this file pins the upload primitive itself.
describe('uploadAttachment', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('POSTs the data URL to /api/attachments and returns the backend path', async () => {
    const api = vi.fn().mockResolvedValue({
      ok: true,
      path: '/home/justin/.hermes/cache/images/img_abc123.png',
      bytes: 70
    })
    ;(globalThis as unknown as { window: unknown }).window = { hermesDesktop: { api } }

    const out = await uploadAttachment('data:image/png;base64,AAAA', 'composer.png')

    expect(out).toBe('/home/justin/.hermes/cache/images/img_abc123.png')
    expect(api).toHaveBeenCalledTimes(1)

    const req = api.mock.calls[0][0]
    expect(req.path).toBe('/api/attachments')
    expect(req.method).toBe('POST')
    expect(req.body).toEqual({ data_url: 'data:image/png;base64,AAAA', filename: 'composer.png' })

    // The reference handed back is the backend path, never a client path.
    expect(out.startsWith('C:\\')).toBe(false)
  })

  it('throws when the backend returns no path', async () => {
    const api = vi.fn().mockResolvedValue({ ok: false, message: 'nope' })
    ;(globalThis as unknown as { window: unknown }).window = { hermesDesktop: { api } }

    await expect(uploadAttachment('data:image/png;base64,AAAA')).rejects.toThrow('nope')
  })
})
