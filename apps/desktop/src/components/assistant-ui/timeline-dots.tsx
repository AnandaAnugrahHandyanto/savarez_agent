import { useStore } from '@nanostores/react'
import { type FC, useCallback, useState } from 'react'

import { cn } from '@/lib/utils'
import { $activeTurnIndex, $timelineTurns, scrollToTimelineGroup } from '@/store/timeline'

/**
 * Timeline navigation dots — a subtle vertical track on the right edge of the
 * chat viewport.  Each dot represents a user turn; clicking one smooth-scrolls
 * to that turn.  The dots are faded by default and become fully opaque on hover.
 */
export const TimelineDots: FC = () => {
  const turns = useStore($timelineTurns)
  const activeIndex = useStore($activeTurnIndex)
  const [hovered, setHovered] = useState(false)

  const handleClick = useCallback((groupIndex: number) => {
    scrollToTimelineGroup(groupIndex)
  }, [])

  // Don't render anything for very short conversations.
  if (turns.length < 2) {
    return null
  }

  return (
    <div
      className={cn(
        'pointer-events-auto absolute right-0 top-0 z-10 flex h-full flex-col items-center justify-center gap-1 pr-1.5',
        'transition-opacity duration-300',
        hovered ? 'opacity-100' : 'opacity-0 hover:opacity-100'
      )}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Invisible hover target so the dots area is discoverable */}
      <div className="absolute inset-y-0 -left-2 w-2" />

      {turns.map((turn, i) => (
        <button
          key={turn.id}
          aria-label={`Jump to turn ${i + 1}`}
          className={cn(
            'size-2 rounded-full border-0 p-0 transition-all duration-200',
            'cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-(--ui-accent)',
            i === activeIndex
              ? 'bg-(--ui-accent) scale-125 shadow-[0_0_4px_var(--ui-accent)]'
              : 'bg-(--ui-base) opacity-40 hover:opacity-80 hover:scale-110'
          )}
          onClick={() => handleClick(turn.groupIndex)}
        />
      ))}
    </div>
  )
}
