import type { DashboardTheme, ThemeTypography, ThemeLayout } from "./types";

/**
 * Built-in dashboard themes.
 *
 * Each theme defines its own palette, typography, and layout so switching
 * themes produces visible changes beyond just color — fonts, density, and
 * corner-radius all shift to match the theme's personality.
 *
 * Theme names must stay in sync with the backend's
 * `_BUILTIN_DASHBOARD_THEMES` list in `hermes_cli/web_server.py`.
 */

// ---------------------------------------------------------------------------
// Shared typography / layout presets
// ---------------------------------------------------------------------------

/** Default system stack — neutral, safe fallback for every platform. */
const SYSTEM_SANS =
  'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
const SYSTEM_MONO =
  'ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace';

const DEFAULT_TYPOGRAPHY: ThemeTypography = {
  fontSans: SYSTEM_SANS,
  fontMono: SYSTEM_MONO,
  baseSize: "15px",
  lineHeight: "1.55",
  letterSpacing: "0",
};

const DEFAULT_LAYOUT: ThemeLayout = {
  radius: "0.5rem",
  density: "comfortable",
};

// ---------------------------------------------------------------------------
// Themes
// ---------------------------------------------------------------------------

export const defaultTheme: DashboardTheme = {
  name: "default",
  label: "Hermes Teal",
  description: "Classic dark teal — the canonical Hermes look",
  palette: {
    background: { hex: "#041c1c", alpha: 1 },
    midground: { hex: "#ffe6cb", alpha: 1 },
    foreground: { hex: "#ffffff", alpha: 0 },
    warmGlow: "rgba(255, 189, 56, 0.35)",
    noiseOpacity: 1,
  },
  typography: DEFAULT_TYPOGRAPHY,
  layout: DEFAULT_LAYOUT,
  terminalBackground: "#000000",
};

export const midnightTheme: DashboardTheme = {
  name: "midnight",
  label: "Midnight",
  description: "Deep blue-violet with cool accents",
  palette: {
    background: { hex: "#0a0a1f", alpha: 1 },
    midground: { hex: "#d4c8ff", alpha: 1 },
    foreground: { hex: "#ffffff", alpha: 0 },
    warmGlow: "rgba(167, 139, 250, 0.32)",
    noiseOpacity: 0.8,
  },
  typography: {
    ...DEFAULT_TYPOGRAPHY,
    fontSans: `"Inter", ${SYSTEM_SANS}`,
    fontMono: `"JetBrains Mono", ${SYSTEM_MONO}`,
    fontUrl:
      "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap",
    letterSpacing: "-0.005em",
  },
  layout: {
    ...DEFAULT_LAYOUT,
    radius: "0.75rem",
  },
};

export const emberTheme: DashboardTheme = {
  name: "ember",
  label: "Ember",
  description: "Warm crimson and bronze — forge vibes",
  palette: {
    background: { hex: "#1a0a06", alpha: 1 },
    midground: { hex: "#ffd8b0", alpha: 1 },
    foreground: { hex: "#ffffff", alpha: 0 },
    warmGlow: "rgba(249, 115, 22, 0.38)",
    noiseOpacity: 1,
  },
  typography: {
    ...DEFAULT_TYPOGRAPHY,
    fontSans: `"Spectral", Georgia, "Times New Roman", serif`,
    fontMono: `"IBM Plex Mono", ${SYSTEM_MONO}`,
    fontUrl:
      "https://fonts.googleapis.com/css2?family=Spectral:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;700&display=swap",
  },
  layout: {
    ...DEFAULT_LAYOUT,
    radius: "0.25rem",
  },
  colorOverrides: {
    destructive: "#c92d0f",
    warning: "#f97316",
  },
};

export const monoTheme: DashboardTheme = {
  name: "mono",
  label: "Mono",
  description: "Clean grayscale — minimal and focused",
  palette: {
    background: { hex: "#0e0e0e", alpha: 1 },
    midground: { hex: "#eaeaea", alpha: 1 },
    foreground: { hex: "#ffffff", alpha: 0 },
    warmGlow: "rgba(255, 255, 255, 0.1)",
    noiseOpacity: 0.6,
  },
  typography: {
    ...DEFAULT_TYPOGRAPHY,
    fontSans: `"IBM Plex Sans", ${SYSTEM_SANS}`,
    fontMono: `"IBM Plex Mono", ${SYSTEM_MONO}`,
    fontUrl:
      "https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap",
  },
  layout: {
    ...DEFAULT_LAYOUT,
    radius: "0",
  },
};

export const cyberpunkTheme: DashboardTheme = {
  name: "cyberpunk",
  label: "Cyberpunk",
  description: "Neon green on black — matrix terminal",
  palette: {
    background: { hex: "#040608", alpha: 1 },
    midground: { hex: "#9bffcf", alpha: 1 },
    foreground: { hex: "#ffffff", alpha: 0 },
    warmGlow: "rgba(0, 255, 136, 0.22)",
    noiseOpacity: 1.2,
  },
  typography: {
    ...DEFAULT_TYPOGRAPHY,
    fontSans: `"Share Tech Mono", "JetBrains Mono", ${SYSTEM_MONO}`,
    fontMono: `"Share Tech Mono", "JetBrains Mono", ${SYSTEM_MONO}`,
    fontUrl:
      "https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=JetBrains+Mono:wght@400;700&display=swap",
  },
  layout: {
    ...DEFAULT_LAYOUT,
    radius: "0",
  },
  colorOverrides: {
    success: "#00ff88",
    warning: "#ffd700",
    destructive: "#ff0055",
  },
};

export const roseTheme: DashboardTheme = {
  name: "rose",
  label: "Rosé",
  description: "Soft pink and warm ivory — easy on the eyes",
  palette: {
    background: { hex: "#1a0f15", alpha: 1 },
    midground: { hex: "#ffd4e1", alpha: 1 },
    foreground: { hex: "#ffffff", alpha: 0 },
    warmGlow: "rgba(249, 168, 212, 0.3)",
    noiseOpacity: 0.9,
  },
  typography: {
    ...DEFAULT_TYPOGRAPHY,
    fontSans: `"Fraunces", Georgia, serif`,
    fontMono: `"DM Mono", ${SYSTEM_MONO}`,
    fontUrl:
      "https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=DM+Mono:wght@400;500&display=swap",
  },
  layout: {
    ...DEFAULT_LAYOUT,
    radius: "1rem",
  },
};

/**
 * Nous Blue — the inverted "light mode" Hermes look, ported from the
 * LENS_5I overlay preset in `@nous-research/ui`.
 *
 * Unlike the other built-ins (which paint dark color directly on the
 * canvas), this theme relies on `<Backdrop />`'s foreground inversion
 * layer: an opaque white sheet at z-200 with `mix-blend-mode: difference`
 * that flips the entire stack below it. Authoring colors stay dark
 * (`#170d02` brown background, `#FFAC02` orange midground), and the
 * inversion converts them to their visual complements at paint time —
 * the orange midground reads as #0053FD Nous-blue on screen, against a
 * cream `#E8F2FD` canvas.
 *
 * Note on bg blend mode: the DS Lens uses `multiply` for LENS_5I because
 * nousnet-web's <body> is white; hermes-agent's App root is `bg-black`,
 * so we leave the bg layer's blend mode at the `difference` default —
 * `difference(#170d02, #000)` passes the bg through unchanged, and the
 * subsequent FG-difference layer then inverts it to cream. Using
 * `multiply` here would collapse the bg to pure black against the
 * `bg-black` root and produce a plain-white canvas instead of the
 * intended cream-blue.
 *
 * Source of truth for the palette: `design-language/src/ui/components/
 * overlays/lens.ts` (LENS_5I export).
 */
export const nousBlueTheme: DashboardTheme = {
  name: "nous-blue",
  label: "Nous Blue",
  description: "Light mode — vivid Nous-blue accents on cream canvas",
  palette: {
    background: { hex: "#170d02", alpha: 1 },
    midground: { hex: "#FFAC02", alpha: 1 },
    foreground: { hex: "#FFFFFF", alpha: 1 },
    // Same warm-amber as nousnet-web's overlay glow; after the FG
    // inversion it reads as a cool ultraviolet vignette in the top-left.
    warmGlow: "rgba(255, 172, 2, 0.18)",
    // Noise sits above the FG inversion and is NOT flipped, so a softer
    // multiplier keeps it from speckling over the bright post-inversion
    // canvas.
    noiseOpacity: 0.4,
  },
  typography: DEFAULT_TYPOGRAPHY,
  layout: DEFAULT_LAYOUT,
  // Inverted page: the embedded terminal is below the FG layer too, so
  // a `#000000` source paints as visual white — i.e. a proper light-mode
  // terminal pane. xterm picks lighter palette colors against the "black"
  // canvas, which then read as dark text on screen post-inversion.
  terminalBackground: "#000000",
  componentStyles: {
    backdrop: {
      // Lower than LENS_5I.Lens.fillerOpacity (0.06). The filler texture
      // gets amplified post-inversion: small variations against the deep
      // `#170d02` source bg are barely visible, but those same variations
      // against the bright `#E8F2FD` post-inversion canvas read as a
      // heavy cloud/marble pattern — especially on near-empty pages
      // (loading spinners, blank states). 0.02 keeps subtle grain
      // without overwhelming the canvas.
      fillerOpacity: "0.02",
    },
  },
  // Pre-invert absolute-hex tokens so they read as their familiar colors
  // through the FG difference layer. e.g. source #04D3C9 (cyan) is what
  // gets painted, and `255 - channel` flips it to #FB2C36 (red) on screen.
  // Without these, the default destructive/success/warning tokens would
  // appear as their unintuitive complements.
  colorOverrides: {
    destructive: "#04d3c9",
    destructiveForeground: "#000000",
    success: "#b5217f",
    warning: "#0042c7",
  },
  // Pre-inverted data-series accents for the Analytics/Models token
  // charts. The defaults (#ffe6cb cream + #34d399 emerald) would render
  // through the FG difference layer as dark navy + hot-coral on the
  // bright Nous-blue canvas — the coral is the "red" users see for
  // Output values without these overrides. Source → on-screen:
  //   Input:  #ffe6cb → #001934 (dark navy)        ← unchanged
  //   Output: #ffac02 → #0053fd (vivid Nous-blue)  ← brand accent
  // Input keeps the cream source so it stays a neutral, low-contrast
  // dark-blue against the cream canvas; output paints as the brand
  // Nous-blue so the "primary" series in token-flow charts reads as
  // the highlight color, matching the rest of the inverted UI chrome.
  seriesColors: {
    inputTokenAccent: "#ffe6cb",
    outputTokenAccent: "#ffac02",
  },
  // Explicit picker swatch — the raw palette hex (`#170d02`, `#FFAC02`,
  // amber rgba) doesn't reflect what users see after the FG inversion,
  // so we paint the post-inversion visual triplet directly:
  //   white → vivid Nous-blue → cream/light-blue
  // matching the actual on-screen rendering of the theme.
  swatchColors: ["#FFFFFF", "#0053FD", "#E8F2FD"],
};

/**
 * Same look as ``defaultTheme`` but with a larger root font size, looser
 * line-height, and ``spacious`` density so every rem-based size in the
 * dashboard scales up. For users who find the default 15px UI too dense.
 */
export const defaultLargeTheme: DashboardTheme = {
  name: "default-large",
  label: "Hermes Teal (Large)",
  description: "Hermes Teal with bigger fonts and roomier spacing",
  palette: defaultTheme.palette,
  typography: {
    ...DEFAULT_TYPOGRAPHY,
    baseSize: "18px",
    lineHeight: "1.65",
  },
  layout: {
    ...DEFAULT_LAYOUT,
    density: "spacious",
  },
};

export const catppuccinMochaTheme: DashboardTheme = {
  name: "catppuccin-mocha",
  label: "Catppuccin Mocha",
  description: "Soft pastel dark dashboard inspired by Catppuccin Mocha",
  palette: {
    background: { hex: "#1E1E2E", alpha: 1 },
    midground: { hex: "#CDD6F4", alpha: 1 },
    foreground: { hex: "#FFFFFF", alpha: 0 },
    warmGlow: "rgba(203, 166, 247, 0.22)",
    noiseOpacity: 0.18,
  },
  typography: {
    ...DEFAULT_TYPOGRAPHY,
    fontSans: `"Inter", ${SYSTEM_SANS}`,
    fontMono: `"JetBrains Mono", ${SYSTEM_MONO}`,
    fontDisplay: `"Inter", ${SYSTEM_SANS}`,
    fontUrl:
      "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap",
    lineHeight: "1.58",
    letterSpacing: "0.005em",
  },
  layout: {
    ...DEFAULT_LAYOUT,
    radius: "0.85rem",
  },
  assets: {
    bg: "radial-gradient(circle at 15% 10%, rgba(203, 166, 247, 0.22), transparent 31%), radial-gradient(circle at 82% 4%, rgba(137, 180, 250, 0.17), transparent 30%), radial-gradient(circle at 88% 86%, rgba(245, 194, 231, 0.13), transparent 36%), linear-gradient(135deg, #1E1E2E 0%, #181825 48%, #11111B 100%)",
  },
  colorOverrides: {
    card: "#242437",
    cardForeground: "#CDD6F4",
    popover: "#181825",
    popoverForeground: "#CDD6F4",
    primary: "#CBA6F7",
    primaryForeground: "#11111B",
    secondary: "#313244",
    secondaryForeground: "#CDD6F4",
    muted: "#313244",
    mutedForeground: "#BAC2DE",
    accent: "#45475A",
    accentForeground: "#F5C2E7",
    destructive: "#F38BA8",
    destructiveForeground: "#11111B",
    success: "#A6E3A1",
    warning: "#F9E2AF",
    border: "rgba(180, 190, 254, 0.24)",
    input: "rgba(180, 190, 254, 0.28)",
    ring: "#B4BEFE",
  },
  componentStyles: {
    backdrop: {
      backgroundPosition: "center",
      backgroundSize: "cover",
      bgBlendMode: "normal",
      fillerBlendMode: "normal",
      fillerOpacity: "1",
    },
    header: {
      background:
        "linear-gradient(90deg, rgba(17, 17, 27, 0.92), rgba(30, 30, 46, 0.82))",
      borderImage:
        "linear-gradient(180deg, rgba(180, 190, 254, 0.36), rgba(203, 166, 247, 0.08)) 1",
    },
    sidebar: {
      background:
        "linear-gradient(180deg, rgba(24, 24, 37, 0.96), rgba(17, 17, 27, 0.96))",
      borderImage:
        "linear-gradient(180deg, rgba(203, 166, 247, 0.42), rgba(137, 180, 250, 0.16), rgba(245, 194, 231, 0.22)) 1",
    },
    tab: {
      clipPath: "inset(0 round 0.75rem)",
    },
  },
  customCSS: `
    :root {
      color-scheme: dark;
      --cat-mocha-rosewater: #f5e0dc;
      --cat-mocha-pink: #f5c2e7;
      --cat-mocha-mauve: #cba6f7;
      --cat-mocha-red: #f38ba8;
      --cat-mocha-peach: #fab387;
      --cat-mocha-yellow: #f9e2af;
      --cat-mocha-green: #a6e3a1;
      --cat-mocha-teal: #94e2d5;
      --cat-mocha-sky: #89dceb;
      --cat-mocha-blue: #89b4fa;
      --cat-mocha-lavender: #b4befe;
      --cat-mocha-text: #cdd6f4;
      --cat-mocha-surface0: #313244;
      --cat-mocha-base: #1e1e2e;
      --cat-mocha-mantle: #181825;
      --cat-mocha-crust: #11111b;
      --color-text-primary: #CDD6F4;
      --color-text-secondary: #BAC2DE;
      --color-text-tertiary: #A6ADC8;
      --color-text-on-accent: #11111B;
      --series-input-token: #F9E2AF;
      --series-output-token: #A6E3A1;
    }

    html, body, #root {
      background: #1E1E2E;
    }

    [data-layout-variant] {
      background: linear-gradient(135deg, #1E1E2E 0%, #181825 52%, #11111B 100%);
    }

    aside {
      box-shadow: 20px 0 60px rgba(17, 17, 27, 0.42), inset -1px 0 0 rgba(180, 190, 254, 0.18);
    }

    aside nav a,
    aside button,
    [role="tab"],
    [role="option"] {
      border-radius: 0.75rem;
    }

    aside nav a:hover,
    aside button:hover,
    [role="tab"]:hover,
    [role="option"]:hover {
      background: rgba(69, 71, 90, 0.42);
      box-shadow: inset 0 0 0 1px rgba(180, 190, 254, 0.16);
    }

    aside nav a[aria-current="page"] {
      color: #CBA6F7 !important;
      background: linear-gradient(90deg, rgba(203, 166, 247, 0.18), rgba(137, 180, 250, 0.08));
      box-shadow: inset 0 0 0 1px rgba(203, 166, 247, 0.26), 0 10px 28px rgba(203, 166, 247, 0.12);
    }

    aside nav a[aria-current="page"] svg {
      color: #F5C2E7;
      filter: drop-shadow(0 0 8px rgba(245, 194, 231, 0.38));
    }

    .bg-card,
    [class*="bg-card"] {
      box-shadow: 0 18px 48px rgba(17, 17, 27, 0.28), inset 0 1px 0 rgba(205, 214, 244, 0.06);
    }

    input,
    textarea,
    select {
      background-color: rgba(24, 24, 37, 0.74) !important;
      border-color: rgba(180, 190, 254, 0.26) !important;
      color: #CDD6F4 !important;
    }

    input:focus,
    textarea:focus,
    select:focus {
      outline-color: #B4BEFE;
      box-shadow: 0 0 0 3px rgba(180, 190, 254, 0.18);
    }

    ::selection {
      background: rgba(203, 166, 247, 0.36);
      color: #F5E0DC;
    }
  `,
  seriesColors: {
    inputTokenAccent: "#F9E2AF",
    outputTokenAccent: "#A6E3A1",
  },
  swatchColors: ["#1E1E2E", "#CDD6F4", "#CBA6F7"],
  terminalBackground: "#11111B",
};

export const BUILTIN_THEMES: Record<string, DashboardTheme> = {
  default: defaultTheme,
  "default-large": defaultLargeTheme,
  "nous-blue": nousBlueTheme,
  "catppuccin-mocha": catppuccinMochaTheme,
  midnight: midnightTheme,
  ember: emberTheme,
  mono: monoTheme,
  cyberpunk: cyberpunkTheme,
  rose: roseTheme,
};
