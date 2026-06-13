import { useStore } from '@nanostores/react'
import { useRef } from 'react'

import { Codicon } from '@/components/ui/codicon'
import { useI18n } from '@/i18n'
import { triggerHaptic } from '@/lib/haptics'
import { cn } from '@/lib/utils'
import { $approvalInView, requestScrollToApproval } from '@/store/approval-scroll'
import { $approvalRequest } from '@/store/prompts'

/**
 * Floating "jump to approval" pill. The turn is BLOCKED on an approval whose
 * only response surface is the inline Run/Reject bar on the pending tool row
 * (components/assistant-ui/tool-approval.tsx). Scroll that row out of view and
 * the session looks stalled with no visible action — the symptom this fixes.
 *
 * Surfaces ONLY when an approval is pending for the active session AND its
 * inline bar is scrolled out of view ($approvalInView === false; the bar mirrors
 * its own IntersectionObserver state). Clicking scrolls the bar back into view —
 * it never duplicates the approve/reject controls. Reuses the jump-button motion
 * + clearance vars and sits just above the scroll-to-bottom button so the two
 * never collide.
 */
export function ScrollToApprovalButton() {
  const { t } = useI18n()
  const request = useStore($approvalRequest)
  const inView = useStore($approvalInView)
  const visible = Boolean(request) && inView === false
  const hasShownRef = useRef(false)

  if (visible) {
    hasShownRef.current = true
  }

  const state = visible ? 'in' : hasShownRef.current ? 'out' : 'idle'

  return (
    <button
      aria-hidden={!visible}
      aria-label={t.assistant.approval.jumpToApproval}
      className={cn(
        'thread-jump-button absolute left-1/2 z-20 flex h-8 items-center gap-1.5 rounded-full px-3',
        'border border-primary/40 bg-(--composer-fill) text-primary hover:bg-primary/10',
        'backdrop-blur-[0.75rem] [-webkit-backdrop-filter:blur(0.75rem)]',
        !visible && 'pointer-events-none'
      )}
      data-state={state}
      onClick={() => {
        triggerHaptic('selection')
        requestScrollToApproval()
      }}
      style={{
        bottom: 'calc(var(--composer-measured-height) + var(--status-stack-measured-height) + 3.375rem)'
      }}
      tabIndex={visible ? 0 : -1}
      type="button"
    >
      <Codicon name="arrow-down" size="0.875rem" />
      <span className="text-xs font-medium">{t.assistant.approval.jumpToApproval}</span>
    </button>
  )
}
