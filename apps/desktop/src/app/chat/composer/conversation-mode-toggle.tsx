import { useStore } from '@nanostores/react'

import { Button } from '@/components/ui/button'
import { Tip } from '@/components/ui/tooltip'
import { useI18n } from '@/i18n'
import { Layers3, Zap } from '@/lib/icons'
import { cn } from '@/lib/utils'
import { $conversationModeBySession, toggleConversationMode } from '@/store/conversation-mode'

// ---------------------------------------------------------------------------
// ConversationModeToggle
// ---------------------------------------------------------------------------

interface ConversationModeToggleProps {
  sessionId: string | null
  disabled?: boolean
}

/**
 * A compact pill/chip that sits in the composer toolbar.
 *
 * - ⚡ Guidance — Hermes responds immediately, drives the goal forward.
 * - 📋 Queue    — messages are enqueued; Hermes acknowledges briefly.
 *
 * Clicking toggles between the two modes and persists the choice to
 * localStorage via `$conversationModeBySession`.
 */
export function ConversationModeToggle({ sessionId, disabled }: ConversationModeToggleProps) {
  const { t } = useI18n()
  const c = t.conversationMode
  const modeBySession = useStore($conversationModeBySession)
  const sid = sessionId?.trim() ?? ''
  const mode = sid ? (modeBySession[sid] ?? 'guidance') : 'guidance'
  const isQueue = mode === 'queue'

  const label = isQueue ? c.queue : c.guidance
  const tooltip = isQueue ? c.queueDesc : c.guidanceDesc

  const handleToggle = () => {
    if (sid) toggleConversationMode(sid)
  }

  return (
    <Tip label={tooltip}>
      <Button
        aria-label={c.toggleAria(label)}
        aria-pressed={isQueue}
        className={cn(
          'h-(--composer-control-size) shrink-0 gap-1 rounded-md px-2 text-xs font-normal',
          'transition-colors duration-150',
          isQueue
            ? 'text-sky-400/90 hover:bg-sky-400/10 hover:text-sky-400'
            : 'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground'
        )}
        disabled={disabled || !sid}
        onClick={handleToggle}
        type="button"
        variant="ghost"
      >
        {isQueue ? <Layers3 className="size-3 shrink-0" /> : <Zap className="size-3 shrink-0" />}
        <span>{label}</span>
      </Button>
    </Tip>
  )
}
