interface SetupOptions {
  cleanups?: (() => Promise<void> | void)[]
  failsafeMs?: number
  onError?: (scope: 'uncaughtException' | 'unhandledRejection', err: unknown) => void
  onSignal?: (signal: NodeJS.Signals) => void
}

const SIGNAL_EXIT_CODE: Record<'SIGHUP' | 'SIGINT' | 'SIGTERM', number> = {
  SIGHUP: 129,
  SIGINT: 130,
  SIGTERM: 143
}

let wired = false

export function setupGracefulExit({ cleanups = [], failsafeMs = 4000, onError, onSignal }: SetupOptions = {}) {
  if (wired) {
    return
  }

  wired = true

  let shuttingDown = false

  const exit = (code: number, signal?: NodeJS.Signals) => {
    if (shuttingDown) {
      return
    }

    shuttingDown = true

    if (signal) {
      onSignal?.(signal)
    }

    setTimeout(() => process.exit(code), failsafeMs).unref?.()

    void Promise.allSettled(cleanups.map(fn => Promise.resolve().then(fn))).finally(() => process.exit(code))
  }

  for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP'] as const) {
    process.on(sig, () => exit(SIGNAL_EXIT_CODE[sig], sig))
  }

  process.on('uncaughtException', err => onError?.('uncaughtException', err))
  process.on('unhandledRejection', reason => onError?.('unhandledRejection', reason))
}

/**
 * Start a watchdog that detects when this process has been orphaned
 * (parent PID changed to 1 / launchd, or the original parent exited).
 *
 * When a terminal window is closed or the desktop app quits, the TUI
 * process may survive as an orphan.  Without this watchdog the Ink
 * render loop can enter a tight busy-loop at ~100 % CPU because stdin
 * is gone but the event loop keeps running.
 *
 * The check runs every `intervalMs` (default 10 s) and is `.unref()`'d
 * so it does not keep the process alive on its own.
 *
 * @param onOrphaned  Called when orphaning is detected.  Receives a
 *                    human-readable reason string for logging.
 * @param intervalMs  How often to check (default: 10 000).
 * @returns           A stop function that clears the interval.
 */
export function startParentWatchdog(
  onOrphaned: (reason: string) => void,
  intervalMs = 10_000
): () => void {
  // Not supported on Windows (ppid is unreliable there).
  if (process.platform === 'win32') {
    return () => {}
  }

  // Record the original parent PID at startup.  If it later changes
  // (the parent exited and we were reparented to init/launchd) or
  // becomes unresolvable, we know we are orphaned.
  const originalPpid = process.ppid

  // PID ≤ 1 means init / launchd — reparenting to it means the real
  // parent is gone.  On macOS orphaned processes go to PID 1 (launchd),
  // on Linux to PID 1 (init / systemd).
  if (originalPpid <= 1) {
    // Already orphaned at startup (unusual but possible if launched from
    // a short-lived wrapper).  Don't arm the watchdog — we'd fire immediately.
    return () => {}
  }

  const timer = setInterval(() => {
    try {
      const currentPpid = process.ppid

      // Reparented to init/launchd → parent exited.
      if (currentPpid <= 1) {
        onOrphaned(`parent exited (ppid changed from ${originalPpid} to ${currentPpid})`)
        clearInterval(timer)
        return
      }

      // The ppid changed to a different non-init PID — unusual but
      // means the original parent is gone (e.g. inside a container
      // with a reaper).  Treat as orphaned.
      if (currentPpid !== originalPpid) {
        onOrphaned(`parent changed (ppid ${originalPpid} → ${currentPpid})`)
        clearInterval(timer)
        return
      }

      // Original parent still alive — also verify with signal 0.
      // This catches the edge case where the PID was recycled by an
      // unrelated process.  Sending signal 0 to a process you don't
      // own may throw EPERM — that's fine (the process exists, we
      // just lack permission).  ESRCH means the process is gone.
      try {
        process.kill(originalPpid, 0)
      } catch (err: unknown) {
        if (isErrnoException(err) && err.code === 'ESRCH') {
          onOrphaned(`parent PID ${originalPpid} no longer exists (ESRCH)`)
          clearInterval(timer)
        }
      }
    } catch {
      // process.ppid may be undefined in exotic environments — ignore.
    }
  }, intervalMs)

  // Don't let the watchdog keep the process alive if everything else
  // has cleaned up.  The timer is the only thing holding the event loop
  // open in that case, and we want the process to exit naturally.
  timer.unref?.()

  return () => clearInterval(timer)
}

function isErrnoException(err: unknown): err is NodeJS.ErrnoException {
  return err instanceof Error && 'code' in err
}
