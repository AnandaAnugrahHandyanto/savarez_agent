import { Box, Text, useInput, useStdout } from '@hermes/ink'
import { useCallback, useEffect, useState } from 'react'

import type { GatewayClient } from '../gatewayClient.js'
import type { SessionActiveItem, SessionActiveListResponse } from '../gatewayTypes.js'
import { asRpcResult, rpcErrorMessage } from '../lib/rpc.js'
import type { Theme } from '../theme.js'

import { OverlayHint, useOverlayKeys, windowOffset } from './overlayControls.js'

const VISIBLE = 12
const MIN_WIDTH = 64
const MAX_WIDTH = 128

const STATUS_GLYPH: Record<string, string> = {
  idle: '✓',
  starting: '…',
  waiting: '?',
  working: '▶'
}

const STATUS_LABEL: Record<string, string> = {
  idle: 'idle',
  starting: 'starting',
  waiting: 'waiting',
  working: 'working'
}

const shortModel = (model = '') => model.replace(/^.*\//, '') || 'model?'

export function ActiveSessionSwitcher({ currentSessionId, gw, onCancel, onNew, onSelect, t }: ActiveSessionSwitcherProps) {
  const [items, setItems] = useState<SessionActiveItem[]>([])
  const [err, setErr] = useState('')
  const [sel, setSel] = useState(0)
  const [loading, setLoading] = useState(true)
  const { stdout } = useStdout()
  const width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, (stdout?.columns ?? 80) - 6))

  const load = useCallback(
    (quiet = false) => {
      if (!quiet) {
        setLoading(true)
      }

      gw.request<SessionActiveListResponse>('session.active_list', { current_session_id: currentSessionId })
        .then(raw => {
          const r = asRpcResult<SessionActiveListResponse>(raw)

          if (!r) {
            setErr('invalid response: session.active_list')
            setLoading(false)

            return
          }

          const next = r.sessions ?? []
          setItems(next)
          setSel(s => Math.max(0, Math.min(s, next.length - 1)))
          setErr('')
          setLoading(false)
        })
        .catch((e: unknown) => {
          setErr(rpcErrorMessage(e))
          setLoading(false)
        })
    },
    [currentSessionId, gw]
  )

  useOverlayKeys({ onClose: onCancel })

  useEffect(() => {
    load()
    const timer = setInterval(() => load(true), 1500)

    return () => clearInterval(timer)
  }, [load])

  useInput((ch, key) => {
    if (key.upArrow && sel > 0) {
      return setSel(s => s - 1)
    }

    if (key.downArrow && sel < items.length - 1) {
      return setSel(s => s + 1)
    }

    if ((key.return || ch === ' ') && items[sel]) {
      return onSelect(items[sel]!.id)
    }

    if (ch?.toLowerCase() === 'n') {
      return onNew()
    }

    if (ch?.toLowerCase() === 'r') {
      return load()
    }

    const n = parseInt(ch ?? '', 10)

    if (n >= 1 && n <= Math.min(9, items.length)) {
      onSelect(items[n - 1]!.id)
    }
  })

  if (loading) {
    return <Text color={t.color.muted}>loading live sessions…</Text>
  }

  if (err && !items.length) {
    return (
      <Box flexDirection="column">
        <Text color={t.color.label}>error: {err}</Text>
        <OverlayHint t={t}>r refresh · n new · Esc/q cancel</OverlayHint>
      </Box>
    )
  }

  if (!items.length) {
    return (
      <Box flexDirection="column">
        <Text color={t.color.muted}>no live sessions</Text>
        <OverlayHint t={t}>n new · Esc/q cancel</OverlayHint>
      </Box>
    )
  }

  const offset = windowOffset(items.length, sel, VISIBLE)

  return (
    <Box flexDirection="column" width={width}>
      <Text bold color={t.color.accent}>
        Live Sessions
      </Text>

      {offset > 0 && <Text color={t.color.muted}>  ↑ {offset} more</Text>}

      {items.slice(offset, offset + VISIBLE).map((s, vi) => {
        const i = offset + vi
        const selected = sel === i
        const status = s.status ?? 'idle'
        const current = s.current || s.id === currentSessionId
        const title = s.title || s.preview || '(untitled)'

        return (
          <Box key={s.id}>
            <Text bold={selected} color={selected ? t.color.accent : t.color.muted} inverse={selected}>
              {selected ? '▸ ' : '  '}
            </Text>

            <Box width={5}>
              <Text bold={selected} color={selected ? t.color.accent : t.color.muted} inverse={selected}>
                {String(i + 1).padStart(2)}.
              </Text>
            </Box>

            <Box width={11}>
              <Text bold={selected} color={selected ? t.color.accent : current ? t.color.label : t.color.muted} inverse={selected}>
                {current ? 'current' : s.id}
              </Text>
            </Box>

            <Box width={11}>
              <Text color={status === 'working' ? t.color.ok : status === 'waiting' ? t.color.label : t.color.muted} inverse={selected}>
                {STATUS_GLYPH[status] ?? '·'} {STATUS_LABEL[status] ?? status}
              </Text>
            </Box>

            <Box width={18}>
              <Text color={selected ? t.color.accent : t.color.muted} inverse={selected} wrap="truncate-end">
                {shortModel(s.model)}
              </Text>
            </Box>

            <Text bold={selected} color={selected ? t.color.accent : t.color.muted} inverse={selected} wrap="truncate-end">
              {title}
            </Text>
          </Box>
        )
      })}

      {offset + VISIBLE < items.length && <Text color={t.color.muted}>  ↓ {items.length - offset - VISIBLE} more</Text>}
      {err && <Text color={t.color.label}>error: {err}</Text>}
      <OverlayHint t={t}>↑/↓ select · Enter switch · 1-9 quick · n new · r refresh · Esc/q close</OverlayHint>
    </Box>
  )
}

interface ActiveSessionSwitcherProps {
  currentSessionId: null | string
  gw: GatewayClient
  onCancel: () => void
  onNew: () => void
  onSelect: (id: string) => void
  t: Theme
}
