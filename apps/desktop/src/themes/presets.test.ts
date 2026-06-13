import { describe, expect, it } from 'vitest'

import { BUILTIN_THEME_LIST, BUILTIN_THEMES, DEFAULT_TYPOGRAPHY, EMOJI_FALLBACK } from './presets'

// #40364: none of the UI text/mono fonts carry emoji glyphs, so every font
// stack must end with a color-emoji fallback or emoji render as tofu on
// platforms whose default font lacks them (e.g. Linux).
describe('built-in Catppuccin theme', () => {
  it('ships one adaptive skin with Latte light colors and Mocha dark colors', () => {
    const theme = BUILTIN_THEMES.catppuccin

    expect(theme).toBeDefined()
    expect(BUILTIN_THEMES['catppuccin-mocha']).toBeUndefined()
    expect(theme.label).toBe('Catppuccin')
    expect(theme.description).toBe('Catppuccin Latte in light mode and Mocha in dark mode')

    expect(theme.colors.background).toBe('#EFF1F5')
    expect(theme.colors.foreground).toBe('#4C4F69')
    expect(theme.colors.primary).toBe('#8839EF')
    expect(theme.colors.ring).toBe('#1E66F5')
    expect(theme.colors.chatBackground).toBe('#EFF1F5')
    expect(theme.colors.chatBackdropOpacity).toBe('0')
    expect(theme.colors.fileIcon).toBe('#1E66F5')
    expect(theme.colors.folderIcon).toBe('#DF8E1D')
    expect(theme.colors.folderOpenIcon).toBe('#8839EF')
    expect(theme.colors.navNewSessionIcon).toBe('#40A02B')
    expect(theme.colors.navSkillsIcon).toBe('#FE640B')
    expect(theme.colors.navMessagingIcon).toBe('#209FB5')
    expect(theme.colors.navArtifactsIcon).toBe('#EA76CB')
    expect(theme.colors.searchIcon).toBe('#7287FD')

    expect(theme.darkColors?.background).toBe('#1E1E2E')
    expect(theme.darkColors?.foreground).toBe('#CDD6F4')
    expect(theme.darkColors?.primary).toBe('#CBA6F7')
    expect(theme.darkColors?.ring).toBe('#89B4FA')
    expect(theme.darkColors?.chatBackground).toBe('#1E1E2E')
    expect(theme.darkColors?.chatBackdropOpacity).toBe('0')

    expect(theme.terminal?.foreground).toBe('#4C4F69')
    expect(theme.terminal?.magenta).toBe('#8839EF')
    expect(theme.darkTerminal?.foreground).toBe('#CDD6F4')
    expect(theme.darkTerminal?.magenta).toBe('#CBA6F7')
  })
})

describe('theme typography emoji fallback (#40364)', () => {
  const stacks: Array<[string, string]> = [
    ['DEFAULT_TYPOGRAPHY.fontSans', DEFAULT_TYPOGRAPHY.fontSans],
    ['DEFAULT_TYPOGRAPHY.fontMono', DEFAULT_TYPOGRAPHY.fontMono],
    // A theme may override only fontMono (fontSans then falls back to the
    // default, which already carries the emoji stack), so skip undefined.
    ...BUILTIN_THEME_LIST.flatMap(theme =>
      (
        [
          [`${theme.name}.fontSans`, theme.typography?.fontSans],
          [`${theme.name}.fontMono`, theme.typography?.fontMono]
        ] as Array<[string, string | undefined]>
      ).filter((entry): entry is [string, string] => typeof entry[1] === 'string')
    )
  ]

  it.each(stacks)('%s includes a color-emoji font', (_label, stack) => {
    expect(stack).toMatch(/Apple Color Emoji|Segoe UI Emoji|Noto Color Emoji|(^|,\s*)emoji\b/)
  })

  it('EMOJI_FALLBACK lists the major platform emoji fonts', () => {
    expect(EMOJI_FALLBACK).toContain('Apple Color Emoji')
    expect(EMOJI_FALLBACK).toContain('Segoe UI Emoji')
    expect(EMOJI_FALLBACK).toContain('Noto Color Emoji')
  })
})
