import type { Themes } from 'react-shiki'

// Keep file previews in the Catppuccin family so highlighted source matches the
// adaptive Desktop palette: Latte in light mode and Mocha in dark mode. Shiki's
// bundled themes carry the canonical Catppuccin colors for both variants.
export const FILE_PREVIEW_SHIKI_THEME = {
  dark: 'catppuccin-mocha',
  light: 'catppuccin-latte'
} as const satisfies Themes
