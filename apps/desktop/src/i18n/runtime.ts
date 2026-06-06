import { TRANSLATIONS } from './catalog'
import { DEFAULT_LOCALE } from './languages'
import type { Locale, Translations } from './types'

let runtimeLocale: Locale = DEFAULT_LOCALE

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function resolvePath(catalog: Translations, key: string): unknown {
  return key.split('.').reduce<unknown>((current, part) => {
    if (!isRecord(current)) {
      return undefined
    }

    return current[part]
  }, catalog)
}

function renderTranslation(value: unknown, args: unknown[]): string | null {
  if (typeof value === 'string') {
    return value
  }

  if (typeof value === 'function') {
    return (value as (...args: unknown[]) => string)(...args)
  }

  return null
}

export function setRuntimeI18nLocale(locale: Locale) {
  runtimeLocale = locale
}

/**
 * Resolve a typed value from the active locale catalog, falling back to the
 * default locale if the active one doesn't define it. Returns undefined when
 * neither locale defines the value, so callers can supply a hardcoded fallback.
 *
 * Use this from non-React modules (stores, lib helpers) where useI18n() isn't
 * available but you still want UI strings to follow the active locale.
 */
export function translateValue<T>(selector: (t: Translations) => T | undefined): T | undefined {
  const active = selector(TRANSLATIONS[runtimeLocale])
  if (active !== undefined) {
    return active
  }
  if (runtimeLocale !== DEFAULT_LOCALE) {
    return selector(TRANSLATIONS[DEFAULT_LOCALE])
  }
  return undefined
}

export function translateNow(key: string, ...args: unknown[]): string {
  const active = renderTranslation(resolvePath(TRANSLATIONS[runtimeLocale], key), args)

  if (active !== null) {
    return active
  }

  if (runtimeLocale !== DEFAULT_LOCALE) {
    const fallback = renderTranslation(resolvePath(TRANSLATIONS[DEFAULT_LOCALE], key), args)

    if (fallback !== null) {
      return fallback
    }
  }

  return key
}
