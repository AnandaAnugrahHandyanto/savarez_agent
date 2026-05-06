const truthy = (v?: string) => /^(?:1|true|yes|on)$/i.test((v ?? '').trim())
const falsy = (v?: string) => /^(?:0|false|no|off)$/i.test((v ?? '').trim())

export const STARTUP_RESUME_ID = (process.env.HERMES_TUI_RESUME ?? '').trim()
export const STARTUP_QUERY = (process.env.HERMES_TUI_QUERY ?? '').trim()
export const STARTUP_IMAGE = (process.env.HERMES_TUI_IMAGE ?? '').trim()
export const MOUSE_TRACKING = !truthy(process.env.HERMES_TUI_DISABLE_MOUSE)
export const NO_CONFIRM_DESTRUCTIVE = truthy(process.env.HERMES_TUI_NO_CONFIRM)

// Skip AlternateScreen — TUI renders into the primary buffer so the host
// terminal's native scrollback captures whatever scrolls off the top, and
// exit doesn't depend on the host honoring DECRC on `\x1b[?1049l` (which
// xterm.js-backed terminals — VS Code, Cursor, Windsurf — don't always
// do, leaving an ugly gap above the resume hint). Default ON for those
// hosts; opt-out via HERMES_TUI_INLINE=0.
const inlineEnv = process.env.HERMES_TUI_INLINE
const inlineHost = process.env.TERM_PROGRAM === 'vscode'
export const INLINE_MODE = truthy(inlineEnv) || (inlineHost && !falsy(inlineEnv))

// Live FPS counter overlay, fed by ink's onFrame (real render rate, not a
// synthetic timer).
export const SHOW_FPS = truthy(process.env.HERMES_TUI_FPS)
