# Phonetic Captions Dashboard — UI Color Pitfalls

## Context

The plugin UI (`plugins/phonetic-captions/dashboard/src/index.tsx`) is an IIFE
injected into the Hermes dashboard (React + Tailwind). The dashboard host page
can be in light or dark mode. Tailwind's `dark:` variants work via a parent
`class="dark"` on a container element supplied by the dashboard host.

---

## The core problem: inherited text color + light hover background = invisible text

The Hermes dashboard sets a light default text color on the page (near-white in
dark mode). If a JSX element omits an explicit text color class, it inherits that
light color from the host page.

When a hover state applies a *light* background (e.g. `hover:bg-zinc-50`) without
also ensuring the text is *dark*, the text disappears on hover because you end up
with white text on a near-white background.

**Broken pattern:**
```tsx
// No text color → inherits light from host → invisible on hover:bg-zinc-50
<div className="font-medium text-sm truncate">{job.video_filename}</div>
```

**Fixed pattern:**
```tsx
// Explicit text color survives regardless of hover background
<div className="font-medium text-sm truncate text-zinc-900 dark:text-zinc-100">
  {job.video_filename}
</div>
```

---

## The secondary trap: fixing text color breaks the default (non-hover) state

Adding `text-zinc-900 dark:text-zinc-100` to the filename text fixes hover, but
`text-zinc-900` is dark. If the card itself has **no background** (transparent),
in dark mode the host page's dark background shows through and `text-zinc-900`
becomes invisible.

Relying on `dark:text-zinc-100` to fix that is fragile — if the class isn't in
the host's compiled Tailwind CSS (because the host's source never used it), it
silently has no effect.

**The reliable fix:** give every card/container an **explicit background** in
both modes, so text always has a known surface to sit against:

```tsx
// Card gets its own bg — no more guessing what the page background is
className="... bg-white dark:bg-zinc-900 hover:bg-zinc-50 dark:hover:bg-zinc-800 ..."
```

Then `text-zinc-900 dark:text-zinc-100` is always correct because you control
both the text AND the background.

---

## Rules to avoid this class of bug

1. **Give every card/panel an explicit `bg-*` AND `dark:bg-*`**, not just the
   hover state. A transparent card is one you don't control.

2. **Always set explicit text color on content inside a hoverable container.**
   Never rely on inheritance — the host page's base color is unpredictable.

3. **Every `hover:bg-*` needs a `dark:hover:bg-*`** — and vice-versa.

4. **Metadata / secondary text** (`text-zinc-500 dark:text-zinc-400`) is safe.
   Primary / headline text (no color class) is what gets forgotten.

5. **Interactive element text** (buttons, toggles) should carry both `text-*`
   and `dark:text-*`, especially when the background changes on hover.

---

## Specific fix applied (May 2026)

Job list card in `JobListView` — filename `<div>` was missing explicit color:

```diff
- <div className="font-medium text-sm truncate">
+ <div className="font-medium text-sm truncate text-zinc-900 dark:text-zinc-100">
```

---

Each `hover:bg-*` in the file accounted for:

| Element | Light hover bg | Dark hover bg | Text |
|---|---|---|---|
| Job card (L163) | `hover:bg-zinc-50` | `dark:hover:bg-zinc-800` | `text-zinc-900 dark:text-zinc-100` ✅ |
| ✂ split button (L263) | `hover:bg-orange-200` | `dark:hover:bg-orange-800/50` | `hover:text-orange-600` ✅ |
| Cancel button (L292) | `hover:bg-zinc-100` | `dark:hover:bg-zinc-800` | inherits host — light mode = dark text on light bg ✅, dark mode = white text on dark bg ✅ |
| Re-burn button (L499) | `hover:bg-zinc-700` | `dark:hover:bg-zinc-300` | `text-white` / `dark:text-zinc-900` ✅ |
| Download button (L506) | `hover:bg-zinc-50` | `dark:hover:bg-zinc-800` | inherits host — same safe pattern as Cancel ✅ |

Every `hover:bg-*` has a paired `dark:hover:bg-*`, which is the critical requirement. Cancel and Download inherit text from the host but that's safe here because the hover bg and the inherited text always contrast correctly (light bg + dark inherited text in light mode, dark bg + white inherited text in dark mode).
