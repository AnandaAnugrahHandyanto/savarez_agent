# Hermes Desktop — Internationalization (i18n) RFC

Status: **Spike / proposal**
Owner: Desktop team
Scope: `apps/desktop` (Electron renderer + main process). Backend/server-side language handling out of scope.

---

## 1. Why this is a spike, not a PR

"Add a language switcher" looks like a settings toggle but in practice it touches:

- ~hundreds of hardcoded English UI strings spread across `app/`, `components/`, `lib/`
- runtime locale detection in Electron main (`session.setSpellCheckerLanguages`, OS dialogs, menu)
- LLM prompts the agent receives (separate concern from UI strings — these are content that should stay in whatever language the user is conversing in, NOT in the user's chrome locale)
- input-method (IME) interaction in the composer's contentEditable
- right-to-left (RTL) bidi layout for Arabic / Hebrew
- CJK (Chinese / Japanese / Korean) text shaping, line-breaking, font fallback
- date/number formatting via `Intl.*`
- pluralization (English-only `1 result / 2 results` patterns are everywhere)

Each of these is independently substantial. This document scopes what we'd be signing up for so the team can decide whether to do it now, defer, or pick a subset (e.g. just RTL + CJK shaping, no string translation).

---

## 2. Survey of where strings live today

Rough buckets, all in `apps/desktop/src`:

| Location | Examples | Approx. string count |
|---|---|---|
| `app/chat/composer/` | placeholder, button labels, error toasts | ~30 |
| `app/chat/sidebar/` | "Sessions", "Pinned", "Load more", time labels | ~25 |
| `app/settings/` | every section heading, helper text, button label | ~150 |
| `app/cron/`, `app/messaging/`, `app/artifacts/` | empty states, table headers, error toasts | ~120 |
| `components/ui/` (dialog, button, etc.) | very few — primitives are stringless | ~5 |
| `components/assistant-ui/thread.tsx` | "Stop", "Edit message", "Copy", tool labels | ~40 |
| `lib/icons` + Tabler descriptions | aria-labels only | ~10 |
| Notifications via `store/notifications` | `notify({ title, message })` call sites | ~60 |

Total: **roughly 400–500 distinct strings** to translate per language. Plurals (`1 X / N X`) are extra: ~25 plural forms.

---

## 3. Framework comparison

Three serious candidates for a Vite/React renderer:

### a) `react-intl` (FormatJS)

- ICU MessageFormat (rich plural / gender / select syntax)
- React-native APIs (`<FormattedMessage>`, `useIntl()`)
- ~50 KB gzip
- AST extraction via `formatjs extract` — works with Vite via babel plugin
- Best ergonomics for translators; battle-tested

### b) `i18next` + `react-i18next`

- Most popular in the React ecosystem
- Plain string interpolation by default; `{count, plural, ...}` via ICU plugin
- Many backends (json files, HTTP, async-load)
- ~30 KB gzip
- Looser typing than FormatJS

### c) `@lingui/core` + `@lingui/react`

- Compile-time message extraction with macros (zero runtime overhead for keys)
- ICU MessageFormat
- ~10 KB gzip
- Smaller community, but used by Pleroma, Polkadot apps; lean

**Recommendation:** Start with **`react-intl`**. Reasons:

1. We already have devs familiar with ICU MessageFormat from web work.
2. Best translator tooling (Crowdin / Lokalise / phrase.com all import FormatJS catalogs natively).
3. The bundle-size hit is acceptable for a desktop app — we're not on a cold-start budget.
4. AST extraction is non-negotiable; we don't want to babysit a `t('hello')` registry manually.

---

## 4. Wiring plan (informational only — no code in this RFC)

1. **Add provider at the root.** `src/main.tsx` wraps `<App />` in `<IntlProvider>` with `locale` from a new `$locale` nanostore (default `navigator.language`, persisted to localStorage).
2. **Wire Electron main.** On `app.whenReady`, read the persisted locale via IPC and call `session.setSpellCheckerLanguages([locale])`. Already done in batch 3 — that landed `configureSpellChecker()` with a chosen language; the language-switcher would push to it on change.
3. **Catalog format.** `apps/desktop/src/i18n/en.json` is the source of truth; other locales (e.g. `zh-CN.json`, `ja.json`) populated by translators.
4. **String extraction.** Add an `npm run extract` step (`formatjs extract 'src/**/*.{ts,tsx}' --out-file src/i18n/en.json`) that runs in CI and fails the PR if any translation key is missing from `en.json`.
5. **Component changes.** Replace bare strings with `<FormattedMessage id="..." defaultMessage="..."/>` or `intl.formatMessage(...)`. Use a codemod for the first pass (`jscodeshift`) so we don't write 400 manual edits.
6. **Language switcher UI.** Add a row in `app/settings/about-settings.tsx` with a `<Select>` listing available locales. On change: persist to localStorage + push to Electron main via IPC.

Estimated effort: **3–4 engineer-weeks** for the initial English + one other locale (CJK or RTL pick).

---

## 5. IME audit: composer's contentEditable

`app/chat/composer/index.tsx` uses a contentEditable `<div>`. Key concerns:

- **`compositionstart` / `compositionend` events.** During CJK / Korean composition, the IME inserts intermediate characters that we currently DO NOT specifically handle. `handleEditorInput` runs on every `input` event, which fires during composition with composition text in place. Need to gate trigger-detection on `!isComposing` to avoid `/file` palette opening mid-syllable.
- **`navigator.language`.** Already used elsewhere; can drive default spellcheck and keyboard mode.
- **Paste behavior.** Pasted CJK text comes in via `clipboardData.getData('text/plain')` and works fine — verified during the spellcheck batch.
- **Enter to send vs Enter to confirm IME.** Today, plain `Enter` submits the form. CJK IMEs commit composition on Enter — Chromium suppresses the `keydown` for the committing Enter, so we're safe on that specific case, but it's worth a manual smoke test with the macOS Pinyin IME and the Windows Japanese IME.

**Action items for the i18n PR:**

```ts
const isComposingRef = useRef(false)
// onCompositionStart: isComposingRef.current = true
// onCompositionEnd:   isComposingRef.current = false; refreshTrigger()
// In handleEditorKeyDown / handleEditorInput: bail when isComposingRef.current
```

---

## 6. RTL audit

Arabic / Hebrew / Persian users would need `dir="rtl"` on the document root. Tailwind already supports logical properties (`ps-2` / `pe-2`, `start-0` / `end-0`) but we use a mix:

- Padding & margin: ~70% logical (`pl-3` / `pr-3` used as-is, NOT logical)
- Position: very few uses of `left-` / `right-` — most are `left-0` for the sidebar (which IS visually-left even in RTL)
- Animations: a couple of `translate-x-` slide transitions that would feel backwards in RTL

**Action item:** Sweep `pl-`, `pr-`, `ml-`, `mr-`, `left-`, `right-` and convert to `ps-`, `pe-`, `ms-`, `me-`, `start-`, `end-` where appropriate. Tailwind v4 has `ltr:` / `rtl:` variants for the cases where logical doesn't suffice.

---

## 7. CJK audit

Chat bubbles (`thread.tsx UserMessage`, assistant messages) use `whitespace-pre-line` and `wrap-anywhere`. In CJK text:

- `wrap-anywhere` breaks between any two characters, which is correct for CJK because there are no inter-word spaces.
- Font fallback: we currently rely on system stack. For Windows we need to make sure `Noto Sans CJK` or `Microsoft YaHei` is available (the WSL fonts shim already handles WSL → Windows fonts in `main.cjs`).
- Vertical metrics: CJK glyphs have a different x-height — the composer's `min-h-(--composer-input-min-height)` may feel cramped. Consider increasing line-height in the composer when `:lang(zh)` / `:lang(ja)` / `:lang(ko)` is set.

**Action item:** Add `:lang(zh), :lang(ja), :lang(ko) { line-height: 1.7; }` to a CJK-tuned override block in `src/styles.css`.

---

## 8. Strings the agent emits (NOT in scope)

There's a separate question: when the agent talks to the user, what language should it use? Today the agent responds in whatever language the user types in (the LLM auto-detects). The user's chrome locale and the agent's reply language are intentionally separate concerns:

- The chrome (sidebar, settings, error toasts) reflects the user's OS / preference.
- The conversation reflects what the user is asking, which can switch mid-session.

The LLM-side system prompt should NOT include `"respond in {locale}"` based on the chrome locale — that would override what the user actually typed in. Out of scope for this RFC.

---

## 9. Recommendation

1. **Land this RFC + tracking issue.**
2. **Pick ONE locale to translate first** as a forcing function. Suggested: `zh-CN` (largest user base after English per Sentry/analytics) OR `ja` (translator availability internally).
3. **Carve up implementation into 4 PRs:**
   1. `react-intl` provider + extraction tooling + locale picker UI (zero string changes — English only)
   2. Codemod sweep of `app/` components → `<FormattedMessage>`
   3. Codemod sweep of `components/assistant-ui/` and `lib/`
   4. RTL + CJK styling adjustments + IME composition gating in composer
4. **Defer:** server-side / agent-side language handling until product confirms whether the chrome locale should influence agent behavior at all.

---

## 10. Open questions

- Do we want a build-time check that all locales have all keys (FormatJS supports this) — or accept missing-key fallback to English?
- Should the locale follow the OS or be a user setting? Today there's no setting; macOS apps usually follow `System Settings > Language & Region`. We could match that and skip the picker.
- Storybook / Playwright coverage — do we want screenshot diffs against the top 3 locales?
