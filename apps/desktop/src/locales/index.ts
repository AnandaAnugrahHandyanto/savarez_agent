import { atom } from 'nanostores'
import { persistString, storedString } from '@/lib/storage'

import en, { type Translations } from './en'
import zh from './zh'

export type { Translations }

// ── Language store ──────────────────────────────────────────

const LANGUAGE_STORAGE_KEY = 'hermes.desktop.language'
const DEFAULT_LANGUAGE = 'en'

export type Language = 'en' | 'zh'

export const LANGUAGES: Record<Language, { label: string; flag: string }> = {
  en: { label: 'English', flag: '🇺🇸' },
  zh: { label: '简体中文', flag: '🇨🇳' }
}

const translations: Record<Language, Translations> = { en, zh }

export const $language = atom<Language>(
  (storedString(LANGUAGE_STORAGE_KEY) as Language) || DEFAULT_LANGUAGE
)

$language.subscribe(lang => persistString(LANGUAGE_STORAGE_KEY, lang))

export function setLanguage(lang: Language) {
  $language.set(lang)
}

export function getLanguage(): Language {
  return $language.get()
}

// ── Translation helper ─────────────────────────────────────

/**
 * Get the full translation object for the current language.
 * Use this for destructured access: `const { save, cancel } = t().common`
 */
export function t(): Translations {
  return translations[$language.get()] || en
}

/**
 * Deep merge override into base (only for test/fallback).
 */
function getNestedValue(obj: Record<string, unknown>, path: string): string | undefined {
  const parts = path.split('.')
  let current: unknown = obj

  for (const part of parts) {
    if (current && typeof current === 'object' && part in (current as Record<string, unknown>)) {
      current = (current as Record<string, unknown>)[part]
    } else {
      return undefined
    }
  }

  return typeof current === 'string' ? current : undefined
}

/**
 * Dot-path translation: `tp('common.save')` → 'Save' / '保存'
 * Supports {n}, {x}, {label} etc. placeholders via the `params` object.
 */
export function tp(key: string, params?: Record<string, string | number>): string {
  const lang = $language.get()
  const value = getNestedValue(translations[lang] as Record<string, unknown>, key) ?? getNestedValue(en as Record<string, unknown>, key)

  if (value === undefined) {
    return key
  }

  if (!params) return value

  return value.replace(/\{(\w+)\}/g, (_, name) => {
    const v = params[name]
    return v !== undefined ? String(v) : `{${name}}`
  })
}

// ── React hook (nanostores-based) ───────────────────────────

import { useStore } from '@nanostores/react'

/**
 * React hook that returns the current translations and re-renders on language change.
 *
 * Usage:
 *   const { common, settings } = useTranslations()
 *   <Button>{common.save}</Button>
 */
export function useTranslations(): Translations {
  const lang = useStore($language)
  return translations[lang] || en
}

/**
 * React hook for dot-path translation with params.
 *
 * Usage:
 *   const t = useT()
 *   <span>{t('about.version', { x: '1.2.3' })}</span>
 */
export function useT(): (key: string, params?: Record<string, string | number>) => string {
  const lang = useStore($language)

  return (key: string, params?: Record<string, string | number>) => {
    const value = getNestedValue(translations[lang] as Record<string, unknown>, key) ?? getNestedValue(en as Record<string, unknown>, key)

    if (value === undefined) return key
    if (!params) return value

    return value.replace(/\{(\w+)\}/g, (_, name) => {
      const v = params[name]
      return v !== undefined ? String(v) : `{${name}}`
    })
  }
}
