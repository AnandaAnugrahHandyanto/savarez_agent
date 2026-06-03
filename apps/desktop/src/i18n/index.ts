/**
 * i18n initialization for the desktop app.
 *
 * Language detection priority:
 *   1. System language (navigator.language)
 *   2. User override (localStorage: 'hermes-desktop-lang')
 *   3. Fallback to 'en'
 *
 * Heuristic for locale vs. language code: we differentiate zh-CN from zh-TW
 * but treat zh-Hans / zh-Hant / zh-CN / zh-SG as zh-CN, and zh-TW / zh-HK
 * as zh-TW.  All other languages fall back to 'en' when the exact locale
 * file is missing (i18next's fallbackLng handles this).
 */

import i18n from 'i18next'
import languageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'

import zhCN from './locales/zh-CN/translation.json'

const LANGUAGE_DETECTION_ORDER = ['localStorage', 'navigator', 'htmlTag']
const LOCALSTORAGE_KEY = 'hermes-desktop-lang'

const SUPPORTED_LOCALES = ['en', 'zh-CN', 'zh-TW'] as const

function normalizeLanguage(lng: string): string {
  const lower = lng.toLowerCase().replace(/_/g, '-')

  if (lower.startsWith('zh')) {
    if (lower.startsWith('zh-tw') || lower.startsWith('zh-hk') || lower.startsWith('zh-hant')) {
      return 'zh-TW'
    }

    return 'zh-CN'
  }

  return 'en'
}

void i18n
  .use(languageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      'zh-CN': { translation: zhCN }
    },
    fallbackLng: 'en',
    debug: import.meta.env.DEV,
    interpolation: {
      escapeValue: false // React already escapes
    },
    detection: {
      lookupLocalStorage: LOCALSTORAGE_KEY,
      order: LANGUAGE_DETECTION_ORDER,
      caches: ['localStorage'],
      convertDetectedLanguage: normalizeLanguage
    },
    returnObjects: false
  })

export default i18n

/** Switch locale at runtime and persist the choice. */
export function setLocale(lng: string): void {
  const normalized = SUPPORTED_LOCALES.includes(lng as any) ? lng : 'en'
  localStorage.setItem(LOCALSTORAGE_KEY, normalized)
  void i18n.changeLanguage(normalized)
}

/** Current displayed locale (resolved, not the raw stored value). */
export function currentLocale(): string {
  return i18n.language || 'en'
}
