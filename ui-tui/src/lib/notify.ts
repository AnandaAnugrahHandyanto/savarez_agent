import { spawn } from 'node:child_process'

// freedesktop sound theme path used by ringBell().  The
// `sound-theme-freedesktop` package is part of the default install
// on every major desktop Linux distro using PulseAudio / PipeWire
// (Ubuntu, Fedora, Arch, Debian, openSUSE), so we lean on it as a
// safe always-present fallback.
const BELL_SOUND_PATH = '/usr/share/sounds/freedesktop/stereo/message-new-instant.oga'

const PAPLAY_BIN = process.env.HERMES_PAPLAY_BIN || 'paplay'

let paplayMissing = false

interface RingBellOptions {
  /** Optional stdout stream — when provided and a TTY, we also fire ASCII BEL. */
  stdout?: NodeJS.WriteStream
  /** Override for the sound asset (mostly for tests). */
  soundPath?: string
}

/** Fire-and-forget audible notification for the user.
 *
 * Two-pronged best-effort strategy that mirrors the Python side
 * (`cli._ring_bell`) so CLI and TUI users get the same behaviour:
 *
 *  1. Write `\x07` (ASCII BEL) to stdout when it's a TTY — keeps
 *     legacy / SSH / classic iTerm2 paths working and propagates
 *     through tmux passthrough.
 *  2. `spawn('paplay', [...])` with the freedesktop
 *     "message-new-instant" sound — covers Wayland-native terminals
 *     (Foot, Kitty, ghostty) where the BEL is silently swallowed
 *     or only flashes the screen.
 *
 * Both legs are wrapped so a missing `paplay` binary, headless
 * environment, locked audio device, or closed stdout never throws
 * — the audible cue is a UX nicety, not a load-bearing dependency.
 *
 * After the first ENOENT we remember the binary is missing and skip
 * future spawn attempts so we don't pay the fork cost once per
 * notification on a system that simply doesn't have paplay.
 */
export function ringBell(options: RingBellOptions = {}): void {
  const { stdout, soundPath = BELL_SOUND_PATH } = options

  if (stdout?.isTTY) {
    try {
      stdout.write('\x07')
    } catch {
      // Closed/broken stdout — nothing reasonable to do here.
    }
  }

  if (paplayMissing) {
    return
  }

  try {
    const child = spawn(PAPLAY_BIN, [soundPath], {
      detached: true,
      stdio: 'ignore'
    })

    child.on('error', err => {
      if ((err as NodeJS.ErrnoException).code === 'ENOENT') {
        paplayMissing = true
      }
    })

    child.unref()
  } catch {
    // Some sandboxes throw synchronously on spawn — same swallow.
  }
}

/** Reset the cached "paplay is missing" flag.  Test-only helper. */
export function _resetPaplayMissing(): void {
  paplayMissing = false
}
