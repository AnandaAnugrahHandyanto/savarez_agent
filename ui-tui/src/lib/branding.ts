/**
 * Branding module that integrates with i18n
 * This module must be imported after i18n is initialized
 */

import { initLocalizedBrand, type ThemeBrand } from '../theme.js'
import { t, getCurrentLocale, setLocale, type LanguageCode, initI18n } from './i18n.js'
import { getSystemLocaleLanguage } from '@hermes/ink/utils/intl'

/**
 * Get localized brand information
 */
export function getLocalizedBrand(): ThemeBrand {
  return {
    name: t('brand.name', 'Hermes Agent'),
    icon: '⚕',
    prompt: '❯',
    welcome: t('brand.welcome', 'Type your message or /help for commands.'),
    goodbye: t('brand.goodbye', 'Goodbye! ⚕'),
    tool: '┊',
    helpHeader: t('brand.help_header', '(^_^)? Commands')
  }
}

/**
 * Initialize i18n and branding system
 * @param locale Optional locale code to force (auto-detects if not provided)
 */
export function initI18nAndBranding(locale?: LanguageCode): void {
  // Initialize i18n
  initI18n(locale)

  // Register localized brand getter with theme system
  initLocalizedBrand(getLocalizedBrand)
}

/**
 * Set language and reload branding
 */
export function setLanguage(locale: LanguageCode): void {
  setLocale(locale)
  initLocalizedBrand(getLocalizedBrand)
}

/**
 * Get current language code
 */
export function getCurrentLanguage(): LanguageCode {
  return getCurrentLocale()
}

/**
 * Detect system language
 */
export function detectSystemLanguage(): LanguageCode {
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

export * from './i18n.js'
