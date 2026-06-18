import { useStore } from '@nanostores/react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Tip } from '@/components/ui/tooltip'
import { useI18n } from '@/i18n'
import { Check, ChevronDown, Pause, Play, Square, X } from '@/lib/icons'
import { cn } from '@/lib/utils'
import {
  $goalBySession,
  type GoalLifecycleState,
  refreshSessionGoal,
  sendGoalCommand
} from '@/store/goal'

// ---------------------------------------------------------------------------
// State dot
// ---------------------------------------------------------------------------

interface StateDotProps {
  state: GoalLifecycleState
}

function StateDot({ state }: StateDotProps) {
  const color =
    state === 'active'
      ? 'bg-emerald-500'
      : state === 'paused'
        ? 'bg-amber-400'
        : state === 'waiting'
          ? 'bg-sky-400'
          : state === 'completed'
            ? 'bg-emerald-400'
            : 'bg-destructive'

  return (
    <span
      aria-hidden
      className={cn(
        'relative inline-flex size-2 shrink-0 rounded-full',
        color,
        // Pulsing ring only while actively running
        state === 'active' && 'after:absolute after:inset-0 after:animate-ping after:rounded-full after:bg-emerald-500/50'
      )}
    />
  )
}

// ---------------------------------------------------------------------------
// State icon (for completed/failed)
// ---------------------------------------------------------------------------

function StateIcon({ state }: { state: GoalLifecycleState }) {
  if (state === 'completed') {
    return <Check className="size-2.5 text-emerald-400" />
  }

  if (state === 'failed') {
    return <X className="size-2.5 text-destructive" />
  }

  return <StateDot state={state} />
}

// ---------------------------------------------------------------------------
// Age helper
// ---------------------------------------------------------------------------

function useRelativeAge(updatedAt: number, justNow: string, minutesAgo: (n: number) => string): string {
  const [age, setAge] = useState(() => formatAge(updatedAt, justNow, minutesAgo))

  useEffect(() => {
    setAge(formatAge(updatedAt, justNow, minutesAgo))
    const interval = setInterval(() => setAge(formatAge(updatedAt, justNow, minutesAgo)), 30_000)

    return () => clearInterval(interval)
  }, [updatedAt, justNow, minutesAgo])

  return age
}

function formatAge(updatedAt: number, justNow: string, minutesAgo: (n: number) => string): string {
  const minutes = Math.floor((Date.now() - updatedAt) / 60_000)

  return minutes < 1 ? justNow : minutesAgo(minutes)
}

// ---------------------------------------------------------------------------
// GoalStatusBar
// ---------------------------------------------------------------------------

interface GoalStatusBarProps {
  sessionId: string | null
}

/**
 * A compact, always-visible strip that shows the current /goal lifecycle state
 * above the composer. Collapses to nothing when no goal is active.
 *
 * The bar uses the same composerDockCard visual language as the status stack.
 */
export function GoalStatusBar({ sessionId }: GoalStatusBarProps) {
  const { t } = useI18n()
  const c = t.goalBar
  const goalBySession = useStore($goalBySession)
  const goal = sessionId ? goalBySession[sessionId] : undefined

  const [expanded, setExpanded] = useState(false)

  // Fetch the goal state once when we switch to this session.
  // message.complete events keep it refreshed during active runs.
  useEffect(() => {
    if (sessionId) {
      void refreshSessionGoal(sessionId)
    }
  }, [sessionId])

  const age = useRelativeAge(
    goal?.updatedAt ?? Date.now(),
    c.justNow,
    c.minutesAgo
  )

  if (!goal) {
    return null
  }

  const isDone = goal.state === 'completed' || goal.state === 'failed'
  const isPaused = goal.state === 'paused'
  const stateLabel = c.states[goal.state]

  const handlePause = () => {
    if (sessionId) void sendGoalCommand(sessionId, 'pause')
  }

  const handleResume = () => {
    if (sessionId) void sendGoalCommand(sessionId, 'resume')
  }

  const handleEnd = () => {
    if (sessionId) void sendGoalCommand(sessionId, 'end')
  }

  return (
    <div
      aria-label={c.ariaLabel}
      className={cn(
        'mx-2 mb-px rounded-t-[0.65rem] border border-b-0',
        'border-[color-mix(in_srgb,var(--dt-composer-ring)_25%,transparent)]',
        'bg-[color-mix(in_srgb,var(--dt-background)_82%,var(--dt-composer-ring)_18%)]',
        'px-2.5 py-1.5',
        'transition-all duration-150'
      )}
      role="region"
    >
      {/* ── Compact row ── */}
      <div className="flex items-center gap-2">
        {/* State indicator */}
        <StateIcon state={goal.state} />

        {/* State label */}
        <span className="shrink-0 text-[0.65rem] font-medium leading-none tabular-nums text-muted-foreground/80">
          {stateLabel}
        </span>

        {/* Goal title */}
        <span
          className={cn(
            'min-w-0 flex-1 truncate text-[0.73rem] leading-none',
            isDone ? 'text-muted-foreground/60' : 'text-foreground/90'
          )}
          title={goal.title}
        >
          {goal.title}
        </span>

        {/* Age */}
        <span className="shrink-0 text-[0.63rem] text-muted-foreground/50">{age}</span>

        {/* Expand toggle */}
        {(goal.nextStep || isDone) && (
          <Tip label={c.details}>
            <Button
              aria-label={c.details}
              aria-pressed={expanded}
              className="size-4 shrink-0 text-muted-foreground/60 hover:text-foreground/80"
              onClick={() => setExpanded(v => !v)}
              size="icon-xs"
              type="button"
              variant="ghost"
            >
              <ChevronDown
                className={cn('size-2.5 transition-transform duration-150', expanded && 'rotate-180')}
              />
            </Button>
          </Tip>
        )}

        {/* ── Action buttons ── */}
        {!isDone && (
          <div className="flex shrink-0 items-center gap-0.5">
            {isPaused ? (
              <Tip label={c.resume}>
                <Button
                  aria-label={c.resume}
                  className="size-5 text-muted-foreground/70 hover:text-emerald-400"
                  onClick={handleResume}
                  size="icon-xs"
                  type="button"
                  variant="ghost"
                >
                  <Play size={10} />
                </Button>
              </Tip>
            ) : (
              <Tip label={c.pause}>
                <Button
                  aria-label={c.pause}
                  className="size-5 text-muted-foreground/70 hover:text-amber-400"
                  onClick={handlePause}
                  size="icon-xs"
                  type="button"
                  variant="ghost"
                >
                  <Pause size={10} />
                </Button>
              </Tip>
            )}
            <Tip label={c.end}>
              <Button
                aria-label={c.end}
                className="size-5 text-muted-foreground/60 hover:text-destructive/80"
                onClick={handleEnd}
                size="icon-xs"
                type="button"
                variant="ghost"
              >
                <Square size={9} />
              </Button>
            </Tip>
          </div>
        )}
      </div>

      {/* ── Expanded next-step detail ── */}
      {expanded && goal.nextStep && (
        <div className="mt-1.5 pl-4">
          <p className="text-[0.67rem] leading-snug text-muted-foreground/70">
            <span className="font-medium text-muted-foreground/90">{c.nextStep} </span>
            {goal.nextStep}
          </p>
        </div>
      )}
    </div>
  )
}
