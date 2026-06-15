import { describe, expect, it } from 'vitest'

import { FILE_PREVIEW_SHIKI_THEME } from './shiki-theme'

describe('file preview Shiki theme', () => {
  it('uses Catppuccin bundled themes for source previews', () => {
    expect(FILE_PREVIEW_SHIKI_THEME).toEqual({
      dark: 'catppuccin-mocha',
      light: 'catppuccin-latte'
    })
  })
})
