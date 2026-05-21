import { createContext, type ReactNode, useContext, useMemo } from 'react'

export const LOCALES = ['en', 'zh'] as const
export type Locale = (typeof LOCALES)[number]

export { TRAIL_PATTERNS } from './i18n-consts.js'

export interface I18nApi {
  locale: Locale
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string
  tStatus: (status: string) => string
  toolVerb: (name: string) => string
  verbs: string[]
}


import {
  TOOL_VERBS_EN,
  TOOL_VERBS_ZH,
  VERBS_EN,
  VERBS_ZH,
  STATUS_EN,
  STATUS_ZH,
  EN,
  ZH,
  type TranslationKey,
} from './i18n-strings.js'


const CATALOGS: Record<Locale, Record<TranslationKey, string | string[] | Record<string, string>>> = { en: EN, zh: ZH }
const STATUS_CATALOGS: Record<Locale, Record<string, string>> = { en: STATUS_EN, zh: STATUS_ZH }
const TOOL_VERB_CATALOGS: Record<Locale, Record<string, string>> = { en: TOOL_VERBS_EN, zh: TOOL_VERBS_ZH }
const VERB_CATALOGS: Record<Locale, string[]> = { en: VERBS_EN, zh: VERBS_ZH }

const interpolate = (template: string, vars: Record<string, string | number> = {}) =>
  template.replace(/\{(\w+)\}/g, (_m, key: string) => String(vars[key] ?? `{${key}}`))

export const normalizeLocale = (value: unknown): Locale => {
  if (typeof value !== 'string') return 'en'
  const raw = value.trim().toLowerCase()
  if (!raw) return 'en'
  if (raw === 'zh' || raw === 'zh-cn' || raw === 'zh-hans' || raw === 'chinese') return 'zh'
  // zh-tw / zh-hant are separate languages — not mapped to zh. Fall through to en.
  return raw === 'en' || raw === 'en-us' || raw === 'en-gb' || raw === 'english' ? 'en' : 'en'
}

export const translate = (locale: Locale, key: TranslationKey, vars?: Record<string, string | number>) => {
  const value = CATALOGS[locale][key] ?? CATALOGS.en[key] ?? key
  return typeof value === 'string' ? interpolate(value, vars) : key
}

export const translateStatus = (locale: Locale, status: string) => STATUS_CATALOGS[locale][status] ?? status
export const getToolVerb = (locale: Locale, name: string) => TOOL_VERB_CATALOGS[locale][name] ?? TOOL_VERBS_EN[name] ?? 'running'
export const getThinkingVerbs = (locale: Locale) => VERB_CATALOGS[locale] ?? VERBS_EN

const defaultApi: I18nApi = {
  locale: 'en',
  t: (key, vars) => translate('en', key, vars),
  tStatus: status => translateStatus('en', status),
  toolVerb: name => getToolVerb('en', name),
  verbs: VERBS_EN
}

const I18nContext = createContext<I18nApi>(defaultApi)

export function I18nProvider({ children, locale }: { children: ReactNode; locale: Locale }) {
  const api = useMemo<I18nApi>(
    () => ({
      locale,
      t: (key, vars) => translate(locale, key, vars),
      tStatus: status => translateStatus(locale, status),
      toolVerb: name => getToolVerb(locale, name),
      verbs: getThinkingVerbs(locale)
    }),
    [locale]
  )
  return <I18nContext.Provider value={api}>{children}</I18nContext.Provider>
}

export const useI18n = () => useContext(I18nContext)

/** Raw toolset name, with or without the _tools suffix, to display label. */
export const toolsetLabel = (raw: string, locale: Locale): string => {
  const key = raw.endsWith('_tools') ? raw.slice(0, -6) : raw
  if (locale !== 'zh') return key
  // Fall back to the original name when no localized label is available.
  const zh = ZH[`toolset.${key}` as keyof typeof ZH]
  return (zh as string) ?? key
}
