import { useEffect, useRef } from 'react'

import { getLogs } from '@/hermes'
import { notify } from '@/store/notifications'

const POLL_MS = 30_000
const DEDUPE_WINDOW_MS = 10 * 60_000

const RENDERER_FAILURE_PATTERNS: Array<[RegExp, string]> = [
  [/webContents became unresponsive/i, 'Desktop renderer became unresponsive recently.'],
  [/render-process-gone/i, 'Desktop renderer process exited unexpectedly.'],
  [/renderer process (?:gone|crashed|terminated|killed)/i, 'Desktop renderer process crashed or was terminated.'],
  [/\bGPU process crashed\b/i, 'Desktop GPU process crashed; renderer stability may be affected.']
]

function getRendererFailureSignals(desktopLines: string[]) {
  const signals: string[] = []

  for (const [pattern, message] of RENDERER_FAILURE_PATTERNS) {
    if (desktopLines.some(line => pattern.test(line))) {
      signals.push(message)
    }
  }

  return signals
}

function signature(signals: string[]) {
  return signals.join('\n')
}

export function DesktopRenderWatchdog() {
  const lastAlertRef = useRef<{ signature: string; at: number } | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    let timer: number | null = null
    let running = false

    async function poll() {
      if (running) {
        return
      }

      running = true

      try {
        const desktop = await getLogs({ file: 'desktop', lines: 180 }).catch(() => getLogs({ lines: 180 }))
        const signals = getRendererFailureSignals(desktop.lines)

        if (signals.length === 0) {
          return
        }

        const nextSignature = signature(signals)
        const now = Date.now()
        const last = lastAlertRef.current

        if (last && last.signature === nextSignature && now - last.at < DEDUPE_WINDOW_MS) {
          return
        }

        lastAlertRef.current = { signature: nextSignature, at: now }
        notify({
          id: 'desktop-render-freeze-risk',
          kind: 'warning',
          title: 'Hermes Desktop renderer became unresponsive',
          message: 'The Desktop renderer reported an actual unresponsive/crash signal. Save your work if possible, then restart Desktop or open a fresh session.',
          detail: `${signals.map(signal => `- ${signal}`).join('\n')}\n\nBest move: restart Hermes Desktop or open a fresh Desktop session before continuing heavy work.`,
          action: window.hermesDesktop?.revealLogs
            ? {
                label: 'Open logs',
                onClick: () => void window.hermesDesktop?.revealLogs()?.catch(() => undefined)
              }
            : undefined,
          durationMs: 0
        })
      } finally {
        running = false

        if (mountedRef.current) {
          timer = window.setTimeout(poll, POLL_MS)
        }
      }
    }

    timer = window.setTimeout(poll, 10_000)

    return () => {
      mountedRef.current = false

      if (timer !== null) {
        window.clearTimeout(timer)
      }
    }
  }, [])

  return null
}
