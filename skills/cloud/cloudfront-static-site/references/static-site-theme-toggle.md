# Static site dark/light theme toggle pattern

Use this when adding dark mode to a simple static HTML/CSS site without introducing a build step or framework.

## Durable implementation pattern

1. Keep it framework-free unless the site already has a frontend stack.
2. Convert hard-coded colors into CSS custom properties:
   - `:root` for the light theme
   - `[data-theme="dark"]` for the dark theme
   - include `color-scheme: light` / `color-scheme: dark`
3. Cover every visible surface, not just `body`:
   - page background/text/muted text
   - navbar and blurred/sticky nav backgrounds
   - cards and borders
   - primary/secondary buttons
   - badges/tags
   - terminal/code blocks
   - contact/footer sections
4. Add a real button in the nav, not a decorative icon-only div:
   - `type="button"`
   - stable `id`, e.g. `theme-toggle`
   - `aria-label` describing the next action
   - `aria-pressed` reflecting current state
   - visible icon + text such as `🌙 Dark` / `☀️ Light`
5. Initialize theme in JS before or near the main page script:
   - read `localStorage.getItem('theme')`
   - choose the default deliberately:
     - for developer/demo sites, system preference via `window.matchMedia('(prefers-color-scheme: dark)').matches` is fine
     - for client-facing/freelance portfolio sites, default new visitors to `'light'` unless the user explicitly asks for system preference
   - set `document.documentElement.dataset.theme`
   - update the button text/icon/aria values
   - update `<meta name="theme-color">` to match the active theme
6. On click, toggle `dark`/`light`, save the selected value to `localStorage`, and re-render the button state.

Minimal client-facing default pattern:
```js
const savedTheme = localStorage.getItem('theme');
setTheme(savedTheme || 'light'); // fresh visitors land in light mode
```

## Verification checklist

- Parse/check HTML after editing.
- Search for required strings: `id="theme-toggle"`, `data-theme`, `localStorage.getItem('theme')`, and the light/dark aria labels.
- Serve locally with `python3 -m http.server <port> --bind 127.0.0.1`.
- Browser-test both directions:
  - initial theme follows system preference or saved choice
  - click changes `document.documentElement.getAttribute('data-theme')`
  - click changes button label/icon
  - click changes `meta[name="theme-color"]`
- Visually inspect the dark theme; pay special attention to muted text contrast, cards, and contact/footer blocks.
- After deploy, verify live with a cache-busted URL like `https://domain/?v=<short-sha>` and run a DOM check for the active theme/toggle.

## Pitfalls

- A dark `body` with unchanged white cards/buttons looks unfinished. Convert the whole palette to variables.
- Contact sections that intentionally stay light in dark mode can work, but only if contrast and hierarchy still look deliberate.
- If the toggle defaults from system preference, live verification may show dark or light depending on the browser environment; validate behavior, not a single expected default.
- If the site should always welcome new visitors in light mode, remove/avoid the `prefers-color-scheme` fallback and verify with `localStorage.removeItem('theme'); location.reload();` that `data-theme` is `light`, button text says `Dark`, and `theme-color` is `#ffffff`.
- Remember to update browser/mobile chrome color via `theme-color`; otherwise the site can feel visually inconsistent on mobile.
