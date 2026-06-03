import { useStore } from '@nanostores/react'
import { useCallback, useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { triggerHaptic } from '@/lib/haptics'
import { AlertTriangle, Loader2 } from '@/lib/icons'
import { cn } from '@/lib/utils'
import { $approvalRequest, type ApprovalChoice, clearApprovalRequest } from '@/store/approval'
import { $gateway } from '@/store/gateway'
import { notifyError } from '@/store/notifications'

// Order mirrors the TUI overlay (1 once → 2 session → 3 always → 4 deny). Deny
// is rendered last and styled destructive so it reads as the safe way out.
const CHOICES: { choice: ApprovalChoice; label: string; variant: 'default' | 'destructive' | 'outline' }[] = [
  { choice: 'once', label: 'Approve once', variant: 'default' },
  { choice: 'session', label: 'Approve for session', variant: 'outline' },
  { choice: 'always', label: 'Always allow', variant: 'outline' },
  { choice: 'deny', label: 'Deny', variant: 'destructive' }
]

// Top-level modal for dangerous-command approvals. Unlike clarify (an inline
// tool card), approval is an interception of the terminal tool, so it has no
// message part to render against — it lives as a controller-level overlay
// driven purely by the `approval.request` gateway event. The Python agent is
// blocked on `approval.respond` until a choice lands (silence denies on
// timeout), which is why a desktop-only user was hanging on every gate.
export function ApprovalOverlay() {
  const request = useStore($approvalRequest)
  const gateway = useStore($gateway)
  const [submitting, setSubmitting] = useState<ApprovalChoice | null>(null)

  const respond = useCallback(
    async (choice: ApprovalChoice) => {
      if (!request || submitting) {
        return
      }

      if (!gateway) {
        notifyError(new Error('Hermes gateway is not connected'), 'Could not send approval response')

        return
      }

      setSubmitting(choice)

      try {
        await gateway.request<{ ok?: boolean }>('approval.respond', {
          choice,
          session_id: request.sessionId ?? ''
        })
        triggerHaptic('submit')
        clearApprovalRequest(request.sessionId ?? undefined)
      } catch (error) {
        notifyError(error, 'Could not send approval response')
        setSubmitting(null)
      }
    },
    [gateway, request, submitting]
  )

  // Escape denies — same safe default as the TUI (escape → 'deny'). Only wired
  // while a request is open so it never shadows other Escape handlers.
  useEffect(() => {
    if (!request) {
      return
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        void respond('deny')
      }
    }

    window.addEventListener('keydown', onKeyDown, true)

    return () => window.removeEventListener('keydown', onKeyDown, true)
  }, [request, respond])

  if (!request) {
    return null
  }

  const busy = submitting !== null

  return (
    <div
      aria-modal="true"
      className="fixed inset-0 z-[1300] grid place-items-center bg-black/55 p-6 backdrop-blur-sm"
      role="alertdialog"
    >
      <div
        className={cn(
          'grid w-full max-w-lg gap-4 rounded-2xl border border-border/70 bg-card px-5 py-5 text-sm shadow-2xl',
          'shadow-[0_24px_60px_-20px_rgba(0,0,0,0.55)]'
        )}
        data-slot="approval-overlay"
      >
        <div className="flex items-start gap-3">
          <span
            aria-hidden
            className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg bg-destructive/12 text-destructive ring-1 ring-inset ring-destructive/25"
          >
            <AlertTriangle className="size-4" />
          </span>
          <div className="grid flex-1 gap-1">
            <span className="text-[0.6875rem] font-medium uppercase tracking-wide text-muted-foreground/85">
              Dangerous command — approval required
            </span>
            <span className="whitespace-pre-wrap leading-snug text-foreground">{request.description}</span>
          </div>
        </div>

        <pre className="max-h-48 overflow-auto rounded-lg border border-border/70 bg-background/70 px-3 py-2.5 font-mono text-[0.8125rem] leading-relaxed text-foreground/95 wrap-anywhere whitespace-pre-wrap">
          {request.command}
        </pre>

        <div className="grid gap-1.5 sm:grid-cols-2">
          {CHOICES.map(({ choice, label, variant }) => (
            <Button
              className="justify-center"
              disabled={busy}
              key={choice}
              onClick={() => void respond(choice)}
              type="button"
              variant={variant}
            >
              {submitting === choice ? <Loader2 className="size-3.5 animate-spin" /> : label}
            </Button>
          ))}
        </div>

        <span className="text-[0.6875rem] text-muted-foreground/85">
          Esc denies. “Always allow” adds this command to the permanent allowlist on the agent host.
        </span>
      </div>
    </div>
  )
}
