import { appendFileSync, mkdirSync } from 'node:fs'
import { homedir } from 'node:os'
import { join } from 'node:path'

// Mirror the Python gateway's panic log (tui_gateway/server.py::_CRASH_LOG) from
// the Node parent so lifecycle breadcrumbs interleave, by timestamp, with the
// child's `=== SIGTERM received ===` / `=== gateway exit ===` entries.
//
// A backend SIGTERM is ALWAYS a parent action — `gw.kill()` (graceful-exit on a
// signal to Node, or an explicit /quit) or `start()` replacing a live child —
// but #31051 left those breadcrumbs in an in-memory CircularBuffer that dies
// with the process, so SIGTERM crash reports arrived with no parent context and
// no way to tell a signal-driven kill from a memory-critical `process.exit(137)`
// (which closes the child's stdin → clean EOF, not SIGTERM). Persisting the
// death-explaining events here is what makes those reports diagnosable.
const logDir = join(process.env.HERMES_HOME?.trim() || join(homedir(), '.hermes'), 'logs')
const CRASH_LOG = join(logDir, 'tui_gateway_crash.log')

// Skipped under vitest so unit tests exercising start()/kill() can't write into
// a real ~/.hermes (tests must stay hermetic — see AGENTS.md).
const enabled = !process.env.VITEST
let warned = false

export function recordParentLifecycle(line: string): void {
  if (!enabled) {
    return
  }

  try {
    mkdirSync(logDir, { recursive: true })
    appendFileSync(CRASH_LOG, `[tui-parent] ${new Date().toISOString()} ${line}\n`)
  } catch {
    if (!warned) {
      warned = true
      process.stderr.write('hermes-tui: parent lifecycle log unavailable\n')
    }
  }
}
