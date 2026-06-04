import { useMemo, useState } from 'react'

import { Command, CommandEmpty, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Check, ChevronDown, World } from '@/lib/icons'
import { cn } from '@/lib/utils'

// Maximum rows rendered at once. cmdk isn't virtualized and the full IANA list
// is ~400 entries, so we cap the visible set and lean on the search box to
// narrow things down. A footer hint appears whenever the list is capped.
const MAX_VISIBLE = 150

interface TimezoneOption {
  /** IANA identifier, e.g. "America/New_York". */
  id: string
  /** Human label including the current UTC offset, e.g. "America/New_York (GMT-5)". */
  label: string
}

function offsetLabel(timeZone: string): string {
  try {
    const parts = new Intl.DateTimeFormat('en-US', { timeZone, timeZoneName: 'shortOffset' }).formatToParts(new Date())

    return parts.find(p => p.type === 'timeZoneName')?.value ?? ''
  } catch {
    return ''
  }
}

function listTimeZones(): string[] {
  // supportedValuesOf is available in modern Electron/Chromium; guard anyway so
  // an older runtime degrades to a plain text entry rather than throwing.
  const supported = (Intl as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf

  if (typeof supported === 'function') {
    try {
      return supported('timeZone')
    } catch {
      /* fall through */
    }
  }

  return []
}

function toOption(id: string): TimezoneOption {
  const offset = offsetLabel(id)

  return { id, label: offset ? `${id} (${offset})` : id }
}

export function TimezoneCombobox({
  value,
  onChange,
  className
}: {
  value: string
  onChange: (value: string) => void
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')

  // The IANA list never changes for the lifetime of the runtime, so build it
  // (and its offset labels) once rather than on every selection.
  const baseOptions = useMemo<TimezoneOption[]>(() => listTimeZones().map(toOption), [])

  const options = useMemo<TimezoneOption[]>(() => {
    // Surface a previously-saved value that the runtime doesn't enumerate
    // (custom or deprecated zone) so it stays selectable.
    if (value && !baseOptions.some(o => o.id === value)) {
      return [toOption(value), ...baseOptions]
    }

    return baseOptions
  }, [baseOptions, value])

  const query = search.trim().toLowerCase()

  const filtered = useMemo(() => {
    if (!query) {
      return options.slice(0, MAX_VISIBLE)
    }

    const hits: TimezoneOption[] = []

    for (const option of options) {
      if (option.label.toLowerCase().includes(query) || option.id.replace(/_/g, ' ').toLowerCase().includes(query)) {
        hits.push(option)

        if (hits.length >= MAX_VISIBLE) {
          break
        }
      }
    }

    return hits
  }, [options, query])

  // Keep "System default" filterable so a non-matching query can reach the
  // empty state instead of leaving a lone, always-present row.
  const showSystemDefault = !query || 'system default'.includes(query)
  const trimmed = filtered.length >= MAX_VISIBLE

  const select = (next: string) => {
    onChange(next)
    setOpen(false)
    setSearch('')
  }

  const triggerLabel = value ? (options.find(o => o.id === value)?.label ?? value) : 'System default'

  return (
    <Popover
      onOpenChange={next => {
        setOpen(next)

        if (!next) {
          setSearch('')
        }
      }}
      open={open}
    >
      <PopoverTrigger
        aria-expanded={open}
        className={cn(
          'flex h-8 w-full items-center justify-between gap-2 rounded-lg border border-input bg-background px-3 py-2 text-sm whitespace-nowrap shadow-xs outline-none transition-[color,box-shadow] focus-visible:border-ring focus-visible:ring-[0.1875rem] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        role="combobox"
        type="button"
      >
        <span className={cn('flex min-w-0 items-center gap-2', !value && 'text-muted-foreground')}>
          <World className="size-3.5 shrink-0 opacity-60" />
          <span className="truncate">{triggerLabel}</span>
        </span>
        <ChevronDown className="size-4 shrink-0 opacity-60" />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(22rem,90vw)] p-0">
        <Command shouldFilter={false}>
          <CommandInput onValueChange={setSearch} placeholder="Search timezones..." value={search} />
          <CommandList>
            <CommandEmpty>No timezone found.</CommandEmpty>
            {showSystemDefault && (
              <CommandItem onSelect={() => select('')} value="__system_default__">
                <Check className={cn('size-4 shrink-0', value ? 'opacity-0' : 'opacity-100')} />
                <span className="truncate">System default</span>
              </CommandItem>
            )}
            {filtered.map(option => (
              <CommandItem className="font-mono" key={option.id} onSelect={() => select(option.id)} value={option.id}>
                <Check className={cn('size-4 shrink-0', value === option.id ? 'opacity-100' : 'opacity-0')} />
                <span className="truncate">{option.label}</span>
              </CommandItem>
            ))}
            {trimmed && (
              <div className="px-3 py-2 text-xs text-muted-foreground">
                Showing the first {MAX_VISIBLE}. Keep typing to narrow results.
              </div>
            )}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
