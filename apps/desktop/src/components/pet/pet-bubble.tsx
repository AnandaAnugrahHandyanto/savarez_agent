import { useStore } from '@nanostores/react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { AlertCircle, Clock, type IconComponent, StarFilled } from '@/lib/icons'
import { $petActivity, $petState, type PetState } from '@/store/pet'

/**
 * Speech bubble + status glyph that sits above the floating pet — the
 * "notification" half of the mascot. It externalizes what the agent is doing
 * (Codex-style) so a glance at the pet replaces switching back to the window.
 *
 * Text is derived purely from the same `$petState` / `$petActivity` the sprite
 * already reacts to, so it never drifts from the animation. The bubble is shown
 * only when there's something worth saying (working / reviewing / a transient
 * done/error beat / waiting on the user) and is hidden at plain idle.
 */

interface Bubble {
  /** Optional — a glyph-only bubble (e.g. the "done" check) collapses to a badge. */
  text?: string
  glyph?: IconComponent
  /** Tone → glyph color. Text stays neutral for legibility. */
  tone?: 'done' | 'error' | 'wait'
}

// A couple of phrasings per working state, rotated for a touch of life.
const WORKING_LINES = ['working…', 'on it…', 'crunching…']
const REVIEW_LINES = ['thinking…', 'reading…', 'reviewing…']

// How long the "done" star stays after a finish. Longer than the celebrate jump
// (~2.2s) so the badge lingers a beat past the animation settling.
const STAR_HOLD_MS = 3200

function bubbleFor(state: PetState, awaitingInput: boolean, tick: number): Bubble | null {
  switch (state) {
    // Done beats are a gold star that pops in — the bubble collapses to a badge.
    case 'jump':
    case 'wave':
      return { glyph: StarFilled, tone: 'done' }

    case 'failed':
      return { text: 'hit a snag', glyph: AlertCircle, tone: 'error' }

    case 'run':
      return { text: WORKING_LINES[tick % WORKING_LINES.length] }

    case 'review':
      return { text: REVIEW_LINES[tick % REVIEW_LINES.length] }

    default:
      // Idle: only speak up if the agent is blocked waiting on the user.
      return awaitingInput ? { text: 'your turn', glyph: Clock, tone: 'wait' } : null
  }
}

const TONE_COLOR: Record<NonNullable<Bubble['tone']>, string> = {
  done: 'var(--ui-yellow)',
  error: 'var(--ui-red)',
  wait: 'var(--ui-yellow)'
}

export function PetBubble() {
  const state = useStore($petState)
  const activity = useStore($petActivity)
  const [tick, setTick] = useState(0)

  const rotating = state === 'run' || state === 'review'

  // Advance the phrasing while the agent keeps working; reset when it stops so
  // the next working spell starts on the first line.
  useEffect(() => {
    if (!rotating) {
      setTick(0)

      return
    }

    const id = window.setInterval(() => setTick(t => t + 1), 2600)

    return () => window.clearInterval(id)
  }, [rotating])

  const stateBubble = useMemo(
    () => bubbleFor(state, Boolean(activity.awaitingInput), tick),
    [state, activity.awaitingInput, tick]
  )

  // The "done" star outlives the jump animation: the sprite settles back to idle
  // after a couple of bounces, but the badge hangs a beat longer so a glance
  // still catches "it finished". A fresh activity bubble (working/review/error/
  // waiting) supersedes the lingering star immediately.
  const done = state === 'jump' || state === 'wave'
  const [lingerStar, setLingerStar] = useState(false)
  const lingerTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  useEffect(() => {
    if (!done) {
      return
    }

    setLingerStar(true)
    clearTimeout(lingerTimerRef.current)
    lingerTimerRef.current = setTimeout(() => setLingerStar(false), STAR_HOLD_MS)
  }, [done])
  useEffect(() => () => clearTimeout(lingerTimerRef.current), [])

  const bubble: Bubble | null = stateBubble ?? (lingerStar ? { glyph: StarFilled, tone: 'done' } : null)

  // Pop the star in with a little overshoot + spin each time a done beat lands.
  const glyphRef = useRef<HTMLSpanElement | null>(null)
  useEffect(() => {
    if (!done) {
      return
    }

    glyphRef.current?.animate(
      [
        { opacity: 0, transform: 'scale(0.3) rotate(-35deg)' },
        { offset: 0.6, opacity: 1, transform: 'scale(1.25) rotate(10deg)' },
        { transform: 'scale(1) rotate(0deg)' }
      ],
      { duration: 380, easing: 'cubic-bezier(0.2, 0.9, 0.2, 1)' }
    )
  }, [done])

  if (!bubble) {
    return null
  }

  const Glyph = bubble.glyph
  const hasText = Boolean(bubble.text)

  return (
    <div
      style={{
        alignItems: 'center',
        // Solid, theme-driven surface (the prior --ui-bg-card mixes in
        // `transparent`, so the bubble was see-through).
        background: 'var(--ui-bg-elevated)',
        border: '1px solid var(--ui-stroke-secondary)',
        borderRadius: hasText ? 10 : 999,
        boxShadow: '0 4px 14px rgba(0,0,0,0.22)',
        color: 'var(--foreground)',
        display: 'inline-flex',
        fontSize: 11,
        fontWeight: 500,
        gap: hasText ? 5 : 0,
        lineHeight: 1,
        // Glyph-only bubbles collapse to a tight, symmetric badge.
        padding: hasText ? '5px 8px' : 5,
        pointerEvents: 'none',
        whiteSpace: 'nowrap'
      }}
    >
      {Glyph && (
        <span ref={glyphRef} style={{ display: 'inline-flex' }}>
          <Glyph style={{ color: bubble.tone ? TONE_COLOR[bubble.tone] : 'currentColor', height: 13, width: 13 }} />
        </span>
      )}
      {bubble.text}
    </div>
  )
}
