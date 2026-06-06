import { cn } from '@/lib/utils'

const assetPath = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\/+/, '')}`

// Brand badge: the nous-girl mark (white keyed to transparent, so only the
// black line-art remains). Light mode shows the black art over a transparent
// tile; dark mode inverts it to white on a near-black (#222) tile. Replaces the
// generic Sparkles hero glyph. The art fills the tile (no padding, no radius);
// size comes from the caller's className (default size-14).
export function BrandMark({ className, ...props }: React.ComponentProps<'span'>) {
  return (
    <span
      className={cn(
        'inline-flex size-14 shrink-0 items-center justify-center dark:bg-[#222]',
        className
      )}
      {...props}
    >
      <img alt="" className="size-full object-contain dark:invert" src={assetPath('nous-girl.webp')} />
    </span>
  )
}
