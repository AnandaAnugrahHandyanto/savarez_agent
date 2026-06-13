import type { Themes } from 'react-shiki'

// Keep file previews in the Catppuccin family so highlighted source matches the
// Catppuccin Mocha desktop palette. Shiki's bundled Mocha theme carries the
// canonical Base/Text/Mauve colors (#1E1E2E/#CDD6F4/#CBA6F7); Latte keeps the
// existing dual-theme behavior readable if the desktop app is switched to light.
export const FILE_PREVIEW_SHIKI_THEME = {
  dark: 'catppuccin-mocha',
  light: 'catppuccin-latte'
} as const satisfies Themes
