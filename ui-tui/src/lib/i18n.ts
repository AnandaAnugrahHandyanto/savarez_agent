import { readFileSync } from 'fs'
import { join } from 'path'
import { fileURLToPath } from 'url'
import { getSystemLocaleLanguage } from '@hermes/ink/utils/intl'

// Type definitions for translation structure
export interface Translations {
  brand: {
    name: string
    welcome: string
    goodbye: string
    help_header: string
  }
  placeholders: string[]
  status: {
    background_task_singular: string
    background_task_plural: string
    interrupt: string
  }
  language: {
    name: string
    native_name: string
    auto: string
  }
  settings: {
    language: string
    appearance: string
    theme: string
  }
}

// Supported languages
export const SUPPORTED_LANGUAGES = [
  { code: 'en', name: 'English', native_name: 'English' },
  { code: 'zh', name: 'Simplified Chinese', native_name: '简体中文' },
  { code: 'ja', name: 'Japanese', native_name: '日本語' },
  { code: 'ko', name: 'Korean', native_name: '한국어' },
  { code: 'de', name: 'German', native_name: 'Deutsch' },
  { code: 'es', name: 'Spanish', native_name: 'Español' },
  { code: 'fr', name: 'French', native_name: 'Français' },
] as const

export type LanguageCode = typeof SUPPORTED_LANGUAGES[number]['code']

// Locale cache
let currentLocale: LanguageCode = 'en'
let translations: Translations | null = null

/**
 * Get the locales directory path
 */
function getLocalesDir(): string {
  // In development/build context, locales are in ui-tui/locales
  // In production, they might be bundled elsewhere
  const __filename = fileURLToPath(import.meta.url)
  const __dirname = join(__filename, '..')
  return join(__dirname, '..', '..', 'locales')
}

/**
 * Load translations from a YAML file
 */
function loadTranslations(locale: LanguageCode): Translations {
  const localesDir = getLocalesDir()
  const filePath = join(localesDir, `${locale}.yaml`)

  try {
    const content = readFileSync(filePath, 'utf-8')
    return parseYaml(content)
  } catch (error) {
    console.warn(`Failed to load translations for ${locale}, falling back to en`)
    // Fallback to English if the requested locale is not available
    if (locale !== 'en') {
      return loadTranslations('en')
    }
    // Return minimal translations if even English fails
    return {
      brand: {
        name: 'Hermes Agent',
        welcome: 'Type your message or /help for commands.',
        goodbye: 'Goodbye! ⚕',
        help_header: '(^_^)? Commands',
      },
      placeholders: [
        'Ask me anything…',
        'Try "explain this codebase"',
        'Try "write a test for…"',
        'Try "refactor the auth module"',
        'Try "/help" for commands',
        'Try "fix the lint errors"',
        'Try "how does the config loader work?"',
      ],
      status: {
        background_task_singular: 'background task running',
        background_task_plural: 'background tasks running',
        interrupt: 'Ctrl+C to interrupt…',
      },
      language: {
        name: 'English',
        native_name: 'English',
        auto: 'Follow system language',
      },
      settings: {
        language: 'Language',
        appearance: 'Appearance',
        theme: 'Theme',
      },
    }
  }
}

/**
 * Simple YAML parser for our translation files
 * This is a minimal parser that handles the structure we need
 */
function parseYaml(content: string): Translations {
  const result: any = {}
  const lines = content.split('\n')
  let stack: Array<{ obj: any; indent: number }> = [{ obj: result, indent: -1 }]

  for (const line of lines) {
    // Skip comments and empty lines
    if (line.trim().startsWith('#') || line.trim() === '') {
      continue
    }

    const indent = line.search(/\S/)
    const trimmed = line.trim()

    // Pop stack to the correct level
    while (stack.length > 1 && stack[stack.length - 1]!.indent >= indent) {
      stack.pop()
    }

    const current = stack[stack.length - 1]!.obj

    // Check for array items
    const arrayMatch = trimmed.match(/^-\s*(.+)$/)
    if (arrayMatch) {
      if (!Array.isArray(current)) {
        // Parent should have been an array
        const parent = stack[stack.length - 2]!.obj
        const lastKey = Object.keys(parent).pop()
        if (lastKey) {
          parent[lastKey] = []
          stack[stack.length - 1]!.obj = parent[lastKey]
        }
      }
      if (Array.isArray(current)) {
        const value = parseValue(arrayMatch[1]!)
        current.push(value)
      }
      continue
    }

    // Check for key-value pair
    const kvMatch = trimmed.match(/^([^:]+):\s*(.*)$/)
    if (kvMatch) {
      const key = kvMatch[1]!
      const valueStr = kvMatch[2]!
      const value = valueStr === '' ? {} : parseValue(valueStr)

      // If current is an array, we're setting properties on array items
      // which shouldn't happen in our format
      if (Array.isArray(current)) {
        continue
      }

      current[key] = value

      // If the value is an object (empty string), push to stack for nested properties
      if (valueStr === '') {
        stack.push({ obj: current[key], indent })
      }
    }
  }

  return result as Translations
}

/**
 * Parse a YAML value (string, number, boolean)
 */
function parseValue(str: string): string | number | boolean {
  str = str.trim()

  // Remove quotes if present
  if ((str.startsWith('"') && str.endsWith('"')) || (str.startsWith("'") && str.endsWith("'"))) {
    return str.slice(1, -1)
  }

  // Check for boolean
  if (str === 'true') return true
  if (str === 'false') return false

  // Check for number
  const num = Number(str)
  if (!isNaN(num)) {
    return num
  }

  // Return as string
  return str
}

/**
 * Detect system locale and map to supported language code
 */
function detectSystemLocale(): LanguageCode {
  const systemLang = getSystemLocaleLanguage()

  if (!systemLang) {
    return 'en'
  }

  // Map common locale codes to our supported languages
  const localeMap: Record<string, LanguageCode> = {
    'zh': 'zh',
    'ja': 'ja',
    'ko': 'ko',
    'de': 'de',
    'es': 'es',
    'fr': 'fr',
  }

  // Extract the language code (e.g., 'zh' from 'zh-Hans-CN')
  const langCode = systemLang.split('-')[0]!
  return localeMap[langCode] || 'en'
}

/**
 * Initialize the i18n system with the given locale or auto-detect
 */
export function initI18n(locale?: LanguageCode): void {
  const resolvedLocale = locale || detectSystemLocale()
  currentLocale = resolvedLocale
  translations = loadTranslations(currentLocale)
}

/**
 * Get the current locale code
 */
export function getCurrentLocale(): LanguageCode {
  return currentLocale
}

/**
 * Set the current locale and reload translations
 */
export function setLocale(locale: LanguageCode): void {
  if (!SUPPORTED_LANGUAGES.some(lang => lang.code === locale)) {
    console.warn(`Unsupported locale: ${locale}, falling back to en`)
    locale = 'en'
  }
  currentLocale = locale
  translations = loadTranslations(currentLocale)
}

/**
 * Get a translation value by path
 * @example t('brand.welcome')
 */
export function t(path: string, fallback?: string): string {
  if (!translations) {
    initI18n()
  }

  const keys = path.split('.')
  let value: any = translations

  for (const key of keys) {
    if (value && typeof value === 'object' && key in value) {
      value = value[key]
    } else {
      return fallback || path
    }
  }

  return typeof value === 'string' ? value : fallback || path
}

/**
 * Get a random placeholder from the placeholders list
 */
export function getPlaceholder(): string {
  if (!translations) {
    initI18n()
  }

  const placeholders = translations?.placeholders || []
  return placeholders[Math.floor(Math.random() * placeholders.length)] || 'Ask me anything…'
}

/**
 * Get pluralized text for background tasks
 */
export function getBackgroundTaskText(count: number): string {
  if (!translations) {
    initI18n()
  }

  if (count === 1) {
    return `${count} ${t('status.background_task_singular')}`
  } else {
    return `${count} ${t('status.background_task_plural')}`
  }
}

/**
 * Get all supported languages
 */
export function getSupportedLanguages(): typeof SUPPORTED_LANGUAGES {
  return SUPPORTED_LANGUAGES
}

/**
 * Export initialization for use in app
 */
export { getSystemLocaleLanguage }
