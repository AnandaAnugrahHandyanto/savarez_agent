import { describe, expect, it } from 'vitest'

import { BUILTIN_THEME_LIST, BUILTIN_THEMES, DEFAULT_TYPOGRAPHY, EMOJI_FALLBACK } from './presets'

// #40364: none of the UI text/mono fonts carry emoji glyphs, so every font
// stack must end with a color-emoji fallback or emoji render as tofu on
// platforms whose default font lacks them (e.g. Linux).
describe('built-in Catppuccin Mocha theme', () => {
  it('ships a dark Mocha palette and terminal ANSI colors', () => {
    const theme = BUILTIN_THEMES['catppuccin-mocha']

    expect(theme).toBeDefined()
    expect(theme.label).toBe('Catppuccin Mocha')
    expect(theme.colors.background).toBe('#1E1E2E')
    expect(theme.colors.foreground).toBe('#CDD6F4')
    expect(theme.colors.primary).toBe('#CBA6F7')
    expect(theme.colors.ring).toBe('#89B4FA')
    expect(theme.colors.chatBackground).toBe('#1E1E2E')
    expect(theme.colors.chatBackdropOpacity).toBe('0')
    expect(theme.colors.fileIcon).toBe('#89B4FA')
    expect(theme.colors.folderIcon).toBe('#F9E2AF')
    expect(theme.colors.folderOpenIcon).toBe('#CBA6F7')
    expect(theme.colors.navNewSessionIcon).toBe('#A6E3A1')
    expect(theme.colors.navSkillsIcon).toBe('#FAB387')
    expect(theme.colors.navMessagingIcon).toBe('#74C7EC')
    expect(theme.colors.navArtifactsIcon).toBe('#F5C2E7')
    expect(theme.colors.searchIcon).toBe('#B4BEFE')
    expect(theme.darkColors).toEqual(theme.colors)
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
