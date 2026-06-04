'use client'

import { useStore } from '@nanostores/react'
import { type FC, useCallback, useState } from 'react'

import { Button } from '@/components/ui/button'
import { triggerHaptic } from '@/lib/haptics'
import { AlertTriangle, Loader2, Play, X } from '@/lib/icons'
import { cn } from '@/lib/utils'
import { $gateway } from '@/store/gateway'
import { notifyError } from '@/store/notifications'
import { $approvalRequest, type ApprovalRequest, clearApprovalRequest } from '@/store/prompts'

import type { ToolPart } from './tool-fallback-model'

// Inline, Cursor-style approval bar. Rendered under the pending tool row that
// raised the approval instead of as a modal overlay.
//
// Binding is POSITIONAL, not command-matched: the desktop `tool.start` payload
// carries no structured args (only tool_id/name/context — see
// tui_gateway/server.py::_on_tool_start), so we cannot join the approval to the
// row by command string. But `approval.request` only ever fires from the
// `terminal` / `execute_code` guards, and the agent thread blocks on exactly
// one approval at a time, so the single pending row of those tools IS the row
// that raised it. The command/description text comes from `$approvalRequest`
// (the event payload), which is the only place that data reliably exists.
const APPROVAL_TOOLS = new Set(['terminal', 'execute_code'])

// Canonical gateway choices (ui-tui/src/components/prompts.tsx).
type ApprovalChoice = 'once' | 'session' | 'always' | 'deny'

const APPROVAL_CMD_PREVIEW_LINES = 8

export const PendingToolApproval: FC<{ part: ToolPart }> = ({ part }) => {
  const request = useStore($approvalRequest)

  if (!request || !APPROVAL_TOOLS.has(part.toolName)) {
    return null
  }

  return <ApprovalBar request={request} />
}

const ApprovalBar: FC<{ request: ApprovalRequest }> = ({ request }) => {
  const gateway = useStore($gateway)
  const [submitting, setSubmitting] = useState<ApprovalChoice | null>(null)
  const busy = submitting !== null

  const respond = useCallback(
    async (choice: ApprovalChoice) => {
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
    [gateway, request.sessionId]
  )

  const rawLines = request.command.split('\n')
  const shown = rawLines.slice(0, APPROVAL_CMD_PREVIEW_LINES)
  const overflow = rawLines.length - shown.length

  return (
    <div
      className={cn(
        'mt-1.5 grid gap-2.5 rounded-[0.625rem] border border-amber-500/30 bg-amber-500/[0.06] px-3 py-2.5 text-sm',
        'shadow-[inset_0_1px_0_color-mix(in_srgb,var(--foreground)_3%,transparent)]'
      )}
      data-slot="tool-approval-inline"
    >
      <div className="flex items-start gap-2.5">
        <span
          aria-hidden
          className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-md bg-amber-500/15 text-amber-600 ring-1 ring-inset ring-amber-500/25 dark:text-amber-400"
        >
          <AlertTriangle className="size-3.5" />
        </span>
        <div className="grid flex-1 gap-0.5">
          <span className="text-[0.6875rem] font-medium uppercase tracking-wide text-amber-700/90 dark:text-amber-300/90">
            Approval required
          </span>
          <span className="leading-snug text-foreground/90">
            {request.description || 'This command needs your approval before it runs.'}
          </span>
        </div>
      </div>

      {request.command.trim() && (
        <pre
          className={cn(
            'max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-md border border-(--ui-stroke-tertiary)',
            'bg-(--ui-chat-surface-background) px-2.5 py-1.5 font-mono text-[0.75rem] leading-snug text-foreground'
          )}
        >
          {shown.join('\n')}
          {overflow > 0 ? `\n… +${overflow} more line${overflow === 1 ? '' : 's'}` : ''}
        </pre>
      )}

      <div className="flex flex-wrap items-center gap-1.5">
        <Button disabled={busy} onClick={() => void respond('once')} size="sm" type="button">
          {submitting === 'once' ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
          Run
        </Button>
        <Button disabled={busy} onClick={() => void respond('session')} size="sm" type="button" variant="outline">
          {submitting === 'session' && <Loader2 className="size-3.5 animate-spin" />}
          Allow this session
        </Button>
        <Button disabled={busy} onClick={() => void respond('always')} size="sm" type="button" variant="ghost">
          {submitting === 'always' && <Loader2 className="size-3.5 animate-spin" />}
          Always allow
        </Button>
        <Button
          className="ml-auto text-destructive hover:text-destructive"
          disabled={busy}
          onClick={() => void respond('deny')}
          size="sm"
          type="button"
          variant="ghost"
        >
          {submitting === 'deny' ? <Loader2 className="size-3.5 animate-spin" /> : <X className="size-3.5" />}
          Reject
        </Button>
      </div>
    </div>
  )
}
