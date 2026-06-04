'use client'

import { useStore } from '@nanostores/react'
import { type FC, useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'
import { triggerHaptic } from '@/lib/haptics'
import { ChevronDown, Loader2, Terminal } from '@/lib/icons'
import { $gateway } from '@/store/gateway'
import { notifyError } from '@/store/notifications'
import { $approvalRequest, type ApprovalRequest, clearApprovalRequest } from '@/store/prompts'

import type { ToolPart } from './tool-fallback-model'

// Inline, Cursor-style command-approval card. Rendered under the pending tool
// row that raised the approval instead of as a modal overlay.
//
// Binding is POSITIONAL, not command-matched: the desktop `tool.start` payload
// carries no structured args (only tool_id/name/context — see
// tui_gateway/server.py::_on_tool_start), so we cannot join the approval to the
// row by command string. But `approval.request` only ever fires from the
// `terminal` / `execute_code` guards and the agent thread blocks on exactly one
// approval at a time, so the single pending row of those tools IS the row that
// raised it. The command/description text comes from `$approvalRequest` (the
// event payload), which is the only place that data reliably exists.
const APPROVAL_TOOLS = new Set(['terminal', 'execute_code'])

// Canonical gateway choices (ui-tui/src/components/prompts.tsx).
type ApprovalChoice = 'once' | 'session' | 'always' | 'deny'

export const PendingToolApproval: FC<{ part: ToolPart }> = ({ part }) => {
  const request = useStore($approvalRequest)

  if (!request || !APPROVAL_TOOLS.has(part.toolName)) {
    return null
  }

  return <ApprovalBar request={request} />
}

const isMac = typeof navigator !== 'undefined' && /Mac|iP(hone|ad|od)/.test(navigator.platform)

const ApprovalBar: FC<{ request: ApprovalRequest }> = ({ request }) => {
  const gateway = useStore($gateway)
  const [submitting, setSubmitting] = useState<ApprovalChoice | null>(null)
  const busy = submitting !== null

  const respond = useCallback(
    async (choice: ApprovalChoice) => {
      // Another bar (or the keyboard path) may have already resolved this
      // approval; the atom is the single source of truth, so bail if it's gone.
      if (busy || !$approvalRequest.get()) {
        return
      }

      if (!gateway) {
        notifyError(new Error('Hermes gateway is not connected'), 'Could not send approval response')

        return
      }

      setSubmitting(choice)

      try {
        await gateway.request<{ resolved?: boolean }>('approval.respond', {
          choice,
          session_id: request.sessionId ?? undefined
        })
        triggerHaptic(choice === 'deny' ? 'cancel' : 'submit')
        clearApprovalRequest()
      } catch (error) {
        notifyError(error, 'Could not send approval response')
        setSubmitting(null)
      }
    },
    [busy, gateway, request.sessionId]
  )

  // ⌘/Ctrl+Enter → Run, Esc → Reject — matching Cursor's accept/skip bindings.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        void respond('once')
      } else if (event.key === 'Escape') {
        event.preventDefault()
        void respond('deny')
      }
    }

    window.addEventListener('keydown', onKeyDown, true)

    return () => window.removeEventListener('keydown', onKeyDown, true)
  }, [respond])

  const command = request.command.trim()

  return (
    <div
      className="mt-1.5 overflow-hidden rounded-lg border border-(--ui-stroke-secondary) bg-(--ui-bg-elevated) text-sm"
      data-slot="tool-approval-inline"
    >
      <div className="flex items-start gap-2 px-3 py-2.5">
        <Terminal className="mt-px size-3.5 shrink-0 text-(--ui-text-tertiary)" />
        <pre className="min-w-0 flex-1 overflow-x-auto whitespace-pre-wrap break-words font-mono text-[0.8125rem] leading-snug text-foreground">
          {command || request.description}
        </pre>
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-(--ui-stroke-tertiary) bg-[color-mix(in_srgb,var(--foreground)_3%,transparent)] px-2.5 py-1.5">
        <span className="min-w-0 truncate text-xs text-(--ui-text-tertiary)">{request.description}</span>

        <div className="flex shrink-0 items-center gap-1.5">
          <Button className="gap-1.5" disabled={busy} onClick={() => void respond('deny')} size="sm" variant="ghost">
            {submitting === 'deny' ? <Loader2 className="size-3.5 animate-spin" /> : 'Reject'}
            {submitting !== 'deny' && <span className="text-[0.6875rem] opacity-55">Esc</span>}
          </Button>

          <div className="flex items-stretch">
            <Button className="gap-1.5 rounded-r-none" disabled={busy} onClick={() => void respond('once')} size="sm">
              {submitting === 'once' ? <Loader2 className="size-3.5 animate-spin" /> : 'Run'}
              {submitting !== 'once' && (
                <span className="text-[0.6875rem] opacity-70">{isMac ? '⌘⏎' : 'Ctrl⏎'}</span>
              )}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  aria-label="More approval options"
                  className="rounded-l-none border-l border-primary-foreground/25 px-1.5"
                  disabled={busy}
                  size="sm"
                >
                  <ChevronDown className="size-3.5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-44">
                <DropdownMenuItem onSelect={() => void respond('session')}>Allow this session</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => void respond('always')}>Always allow</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => void respond('deny')} variant="destructive">
                  Reject
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>
    </div>
  )
}
