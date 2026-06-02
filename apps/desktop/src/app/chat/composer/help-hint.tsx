import type { ReactNode } from 'react'

import { useTranslations } from '@/locales'

import { COMPLETION_DRAWER_CLASS } from './completion-drawer'

function getCommonCommands(t: ReturnType<typeof useTranslations>): [string, string][] {
  const h = t.helpHint
  return [
    ['/help', h.helpFullList],
    ['/clear', h.clearSession],
    ['/resume', h.resumeSession],
    ['/details', h.detailsLevel],
    ['/copy', h.copyMessage],
    ['/quit', h.exitHermes]
  ]
}

function getHotkeys(t: ReturnType<typeof useTranslations>): [string, string][] {
  const h = t.helpHint
  return [
    ['@', h.refFiles],
    ['/', h.slashPalette],
    ['?', h.quickHelp],
    ['Enter', h.sendNewline],
    ['Cmd/Ctrl+K', h.sendQueued],
    ['Cmd/Ctrl+L', h.redraw],
    ['Esc', h.closeCancel],
    ['↑ / ↓', h.cycleHistory]
  ]
}

export function HelpHint() {
  const t = useTranslations()
  const commonCommands = getCommonCommands(t)
  const hotkeys = getHotkeys(t)

  return (
    <div className={COMPLETION_DRAWER_CLASS} data-slot="composer-completion-drawer" data-state="open" role="dialog">
      <Section title={t.helpHint.commonCommands}>
        {commonCommands.map(([key, desc]) => (
          <Row description={desc} key={key} keyLabel={key} mono />
        ))}
      </Section>

      <Section title={t.helpHint.hotkeys}>
        {hotkeys.map(([key, desc]) => (
          <Row description={desc} key={key} keyLabel={key} />
        ))}
      </Section>

      <p className="px-2.5 py-1 text-xs text-muted-foreground/80">
        <span className="font-mono text-foreground/80">/help</span> {t.helpHint.helpPanelHint}
      </p>
    </div>
  )
}

function Section({ children, title }: { children: ReactNode; title: string }) {
  return (
    <div className="grid gap-0.5 pt-0.5">
      <p className="px-2.5 pb-0.5 pt-1 text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground/75">
        {title}
      </p>
      {children}
    </div>
  )
}

function Row({ description, keyLabel, mono = false }: { description: string; keyLabel: string; mono?: boolean }) {
  return (
    <div className="flex min-w-0 items-baseline gap-2 rounded-md px-2.5 py-1 text-xs">
      <span
        className={
          mono ? 'shrink-0 truncate font-mono font-medium text-foreground/85' : 'shrink-0 truncate text-foreground/85'
        }
      >
        {keyLabel}
      </span>
      <span className="min-w-0 truncate text-muted-foreground/80">{description}</span>
    </div>
  )
}
