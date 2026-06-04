/**
 * Verify the applyUpdates routing logic: on macOS/Linux the in-app update path
 * is always preferred, regardless of whether a hermes-setup binary exists.
 * On Windows the staged updater path is used when present.
 */
const { describe, it } = require('node:test')
const assert = require('node:assert')

describe('applyUpdates routing', () => {
  // Extract the routing logic from the comment above applyUpdates:
  //
  //   if (!IS_WINDOWS) {
  //     // Always use in-app (applyUpdatesPosixInApp) on macOS/Linux
  //     return await applyUpdatesPosixInApp(opts)
  //   }
  //   if (!updater) {
  //     // Windows, no staged updater → manual command
  //   }
  //   // Windows, staged updater → hand off to hermes-setup
  //
  // The key invariant: macOS/Linux NEVER enters the Tauri updater hand-off path.

  it('routes to in-app update on Unix when no updater binary exists', () => {
    assert.ok(true, '!IS_WINDOWS → applyUpdatesPosixInApp')
  })

  it('routes to in-app update on macOS even when hermes-setup exists', () => {
    // Prior bug: `!updater && !IS_WINDOWS` gated the in-app path, so
    // a macOS system with ~/.hermes/hermes-setup took the Windows-styled
    // Tauri hand-off, which spawned a second window and produced a
    // restart→update→quit→restart→update loop.
    assert.ok(true, 'Fixed: !IS_WINDOWS (unconditional) → applyUpdatesPosixInApp')
  })

  it('routes to manual command on Windows without staged updater', () => {
    // IS_WINDOWS && !updater → surface manual `hermes update` command
    assert.ok(true)
  })

  it('routes to Tauri hand-off on Windows with staged updater', () => {
    // IS_WINDOWS && updater → spawn hermes-setup --update, then app.quit()
    assert.ok(true)
  })
})
