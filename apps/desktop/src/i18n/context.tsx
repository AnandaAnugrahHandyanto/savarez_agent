import { createContext, useContext, useEffect, useMemo, useState } from 'react'

// ---------- types ----------

export type SupportedLocale = 'en' | 'fr'

export interface LocaleEntry {
  code: SupportedLocale
  label: string
  nativeLabel: string
}

export const SUPPORTED_LOCALES: LocaleEntry[] = [
  { code: 'en', label: 'English', nativeLabel: 'English' },
  { code: 'fr', label: 'Français', nativeLabel: 'Français' },
]

export const LOCALE_STORAGE_KEY = 'hermes-desktop-locale'

// ---------- resolution ----------

function resolveDefaultLocale(): SupportedLocale {
  // 1. Check localStorage first (user's explicit choice)
  try {
    const stored = localStorage.getItem(LOCALE_STORAGE_KEY)
    if (stored && SUPPORTED_LOCALES.some(l => l.code === stored)) {
      return stored as SupportedLocale
    }
  } catch {
    // localStorage unavailable
  }

  // 2. Fall back to browser language
  const browserLang = (navigator.language ?? 'en').slice(0, 2)
  if (SUPPORTED_LOCALES.some(l => l.code === browserLang)) {
    return browserLang as SupportedLocale
  }

  // 3. Ultimate fallback
  return 'en'
}

// ---------- message loading ----------

const messageModules: Record<SupportedLocale, () => Promise<Record<string, string>>> = {
  en: () => import('./messages/en.json').then(m => m.default as Record<string, string>),
  fr: () => import('./messages/fr.json').then(m => m.default as Record<string, string>),
}

interface I18nContextValue {
  /** Current locale code */
  locale: SupportedLocale
  /** Translation function */
  t: (key: string, params?: Record<string, string>) => string
  /** Change the active locale */
  setLocale: (locale: SupportedLocale) => void
  /** Available locales */
  locales: LocaleEntry[]
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<SupportedLocale>(resolveDefaultLocale)
  const [messages, setMessages] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)

  // Load messages when locale changes
  useEffect(() => {
    let cancelled = false
    setLoading(true)

    messageModules[locale]().then((mod) => {
      if (!cancelled) {
        setMessages(mod)
        setLoading(false)
      }
    }).catch(() => {
      // If a locale bundle fails, fall back to English
      if (!cancelled) {
        messageModules['en']().then((mod) => {
          if (!cancelled) {
            setMessages(mod)
            setLoading(false)
          }
        })
      }
    })

    return () => { cancelled = true }
  }, [locale])

  const setLocale = (newLocale: SupportedLocale) => {
    setLocaleState(newLocale)
    try {
      localStorage.setItem(LOCALE_STORAGE_KEY, newLocale)
    } catch {
      // localStorage unavailable
    }
  }

  const t = useMemo(
    () => (key: string, params?: Record<string, string>): string => {
      let msg = messages[key] ?? key
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          msg = msg.replace(new RegExp(`\\{${k}\\}`, 'g'), v)
        })
      }
      return msg
    },
    [messages],
  )

  if (loading) {
    // Messages are JSON — they load virtually instantly.
    // We render children anyway to avoid a flash.
  }

  const value = useMemo<I18nContextValue>(
    () => ({ locale, t, setLocale, locales: SUPPORTED_LOCALES }),
    [locale, t, setLocale],
  )

  return <I18nContext value={value}>{children}</I18nContext>
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext)
  if (!ctx) {
    throw new Error('useI18n must be used within <I18nProvider>')
  }
  return ctx
}

// Shorthand — most components just need `t`
export function useTranslation(): (key: string, params?: Record<string, string>) => string {
  const { t } = useI18n()
  return t
}
