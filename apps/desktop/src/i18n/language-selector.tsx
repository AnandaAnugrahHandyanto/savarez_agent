import { Globe } from '@/lib/icons'

import { useI18n } from '@/i18n/context'

export function LanguageSelector() {
  const { locale, locales, setLocale, t } = useI18n()

  const currentLocale = locales.find(l => l.code === locale)

  return (
    <div
      className="flex h-full items-center gap-0.5"
      title={t('language.change')}
    >
      {/* Language indicator — subtle globe icon + 2-letter code */}
      <button
        className="inline-flex h-full items-center gap-1 px-1.5 text-[0.6875rem] text-(--ui-text-tertiary) transition-colors hover:bg-(--chrome-action-hover) hover:text-foreground"
        onClick={() => {
          // Cycle to next locale on click
          const currentIndex = locales.findIndex(l => l.code === locale)
          const nextIndex = (currentIndex + 1) % locales.length
          setLocale(locales[nextIndex].code)
        }}
        type="button"
      >
        <Globe className="size-3" />
        <span className="uppercase">{locale}</span>
      </button>
    </div>
  )
}
