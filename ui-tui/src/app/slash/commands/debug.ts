import { formatBytes, performHeapDump } from '../../../lib/memory.js'
import {
  isKeyDebugEnabled,
  keyDebugDestination,
  setKeyDebugEnabled,
  setKeyDebugSink,
  toggleKeyDebug
} from '../../keyDebugStore.js'
import type { SlashCommand } from '../types.js'

export const debugCommands: SlashCommand[] = [
  {
    help: 'toggle composer key event logging [on|off|toggle|status]',
    name: 'debug-keys',
    run: (arg, ctx) => {
      const mode = arg.trim().toLowerCase()

      setKeyDebugSink(line => ctx.transcript.sys(line))

      if (!mode || mode === 'toggle') {
        const next = toggleKeyDebug()

        return ctx.transcript.sys(`key debug ${next ? `on (${keyDebugDestination()})` : 'off'}`)
      }

      if (mode === 'on' || mode === 'true' || mode === '1') {
        setKeyDebugEnabled(true)

        return ctx.transcript.sys(`key debug on (${keyDebugDestination()})`)
      }

      if (mode === 'off' || mode === 'false' || mode === '0') {
        setKeyDebugEnabled(false)

        return ctx.transcript.sys('key debug off')
      }

      if (mode === 'status') {
        return ctx.transcript.sys(
          `key debug ${isKeyDebugEnabled() ? `on (${keyDebugDestination()})` : 'off'}`
        )
      }

      return ctx.transcript.sys('usage: /debug-keys [on|off|toggle|status]')
    }
  },

  {
    help: 'write a V8 heap snapshot + memory diagnostics (see HERMES_HEAPDUMP_DIR)',
    name: 'heapdump',
    run: (_arg, ctx) => {
      const { heapUsed, rss } = process.memoryUsage()

      ctx.transcript.sys(`writing heap dump (heap ${formatBytes(heapUsed)} · rss ${formatBytes(rss)})…`)

      void performHeapDump('manual').then(r => {
        if (ctx.stale()) {
          return
        }

        if (!r.success) {
          return ctx.transcript.sys(`heapdump failed: ${r.error ?? 'unknown error'}`)
        }

        ctx.transcript.sys(`heapdump: ${r.heapPath}`)
        ctx.transcript.sys(`diagnostics: ${r.diagPath}`)
      })
    }
  },

  {
    help: 'print live V8 heap + rss numbers',
    name: 'mem',
    run: (_arg, ctx) => {
      const { arrayBuffers, external, heapTotal, heapUsed, rss } = process.memoryUsage()

      ctx.transcript.panel('Memory', [
        {
          rows: [
            ['heap used', formatBytes(heapUsed)],
            ['heap total', formatBytes(heapTotal)],
            ['external', formatBytes(external)],
            ['array buffers', formatBytes(arrayBuffers)],
            ['rss', formatBytes(rss)],
            ['uptime', `${process.uptime().toFixed(0)}s`]
          ]
        }
      ])
    }
  }
]
