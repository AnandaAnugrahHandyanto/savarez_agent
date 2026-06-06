import { cn } from '@/lib/utils'

const assetPath = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\/+/, '')}`

// Brand badge: the white Hermes logo on a hardcoded brand-blue tile in light
// mode and a near-black tile in dark. Replaces the generic Sparkles glyph used
// as a hero mark in overlays. Size + radius come from the caller's className
// (defaults to the size-14/rounded-2xl hero treatment); the logo scales to a
// share of the tile so padding stays proportional at any size.
export function BrandMark({ className, ...props }: React.ComponentProps<'span'>) {
  return (
    <span
      className={cn(
        'inline-flex size-14 shrink-0 items-center justify-center rounded-2xl bg-[#0000F2] dark:bg-[#222]',
        className
      )}
      {...props}
    >
      {/* logo.png is blue line-art on transparent; force it white so it reads
          on both the brand-blue and near-black tiles. */}
      <img alt="" className="size-[62%] object-contain brightness-0 invert" src={assetPath('logo.png')} />
    </span>
  )
}
