import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

// --- Types ---
export type Locale = 'en' | 'zh-CN' | 'ja' | 'ko' | 'de' | 'es' | 'fr'

export const SUPPORTED_LOCALES: Locale[] = ['en', 'zh-CN', 'ja', 'ko', 'de', 'es', 'fr']

export const LANGUAGE_LABELS: Record<Locale, string> = {
  'en': 'English',
  'zh-CN': '中文（简体）',
  'ja': '日本語',
  'ko': '한국어',
  'de': 'Deutsch',
  'es': 'Español',
  'fr': 'Français',
}

const STORAGE_KEY = 'hermes-desktop-locale'

// --- Auto-discover locale modules ---
// To add a new language, just add the Locale type above + a new JSON file in src/locales/
// No other code changes needed — the import map below is the single registration point.
const localeLoaders: Record<string, () => Promise<Record<string, string>>> = {
  'en':  () => import('../locales/en.json').then(m => (m.default ?? m) as Record<string, string>),
  'zh-CN': () => import('../locales/zh-CN.json').then(m => (m.default ?? m) as Record<string, string>),
  'ja': () => import('../locales/ja.json').then(m => (m.default ?? m) as Record<string, string>),
  'ko': () => import('../locales/ko.json').then(m => (m.default ?? m) as Record<string, string>),
  'de': () => import('../locales/de.json').then(m => (m.default ?? m) as Record<string, string>),
  'es': () => import('../locales/es.json').then(m => (m.default ?? m) as Record<string, string>),
  'fr': () => import('../locales/fr.json').then(m => (m.default ?? m) as Record<string, string>),
}

// --- Module-level cache ---
const allTranslations: Record<string, Record<string, string>> = {}
let _currentLocale: Locale = getInitialLocale()

// --- Helpers ---
function normalizeLocale(raw: string): Locale {
  const lc = raw.toLowerCase()
  if (lc.startsWith('zh')) return 'zh-CN'
  if (lc.startsWith('ja')) return 'ja'
  if (lc.startsWith('ko')) return 'ko'
  if (lc.startsWith('de')) return 'de'
  if (lc.startsWith('es')) return 'es'
  if (lc.startsWith('fr')) return 'fr'
  return 'en'
}

function getInitialLocale(): Locale {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved && (SUPPORTED_LOCALES as string[]).includes(saved)) {
      return saved as Locale
    }
  } catch {}
  return normalizeLocale(typeof navigator !== 'undefined' ? navigator.language : 'en')
}

async function ensureLocale(locale: Locale): Promise<void> {
  if (allTranslations[locale]) return
  const loader = localeLoaders[locale]
  if (loader) {
    try {
      allTranslations[locale] = await loader()
    } catch {
      // Fall through — English fallback below
    }
  }
  // Fallback: load English if available
  if (!allTranslations[locale] && locale !== 'en') {
    if (!allTranslations['en']) {
      const enLoader = localeLoaders['en']
      if (enLoader) allTranslations['en'] = await enLoader()
    }
    allTranslations[locale] = allTranslations['en'] ?? {}
  }
}

// --- React Context ---
interface I18nContextValue {
  locale: Locale
  t: (key: string, params?: Record<string, unknown>) => string
  setLocale: (locale: Locale) => void
  availableLocales: Locale[]
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(_currentLocale)

  const setLocale = useCallback((newLocale: Locale) => {
    if (!(SUPPORTED_LOCALES as string[]).includes(newLocale)) return
    _currentLocale = newLocale
    setLocaleState(newLocale)
    try { localStorage.setItem(STORAGE_KEY, newLocale) } catch {}
    // Preload translations
    ensureLocale(newLocale)
  }, [])

  const t = useCallback((key: string, params?: Record<string, unknown>): string => {
    const translations = allTranslations[_currentLocale]
    const fallback = allTranslations['en']
    let value = translations?.[key] ?? fallback?.[key] ?? key
    if (params) {
      value = Object.entries(params).reduce(
        (str, [k, v]) => str.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v)),
        value,
      )
    }
    return value
  }, [locale])

  return (
    <I18nContext.Provider value={{ locale, t, setLocale, availableLocales: SUPPORTED_LOCALES }}>
      <div key={locale}>{children}</div>
    </I18nContext.Provider>
  )
}

export function useTranslation(): I18nContextValue {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useTranslation must be used within I18nProvider')
  return ctx
}

// --- Standalone t() for non-React code ---
export function t(key: string, params?: Record<string, unknown>): string {
  const translations = allTranslations[_currentLocale]
  const fallback = allTranslations['en']
  let value = translations?.[key] ?? fallback?.[key] ?? key
  if (params) {
    value = Object.entries(params).reduce(
      (str, [k, v]) => str.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v)),
      value,
    )
  }
  return value
}


// --- Provider description translation ---
// Maps known backend description strings to i18n keys.
// When a provider description matches, use the translated version.
const PROVIDER_DESC_KEYS: Record<string, string> = {
  "Arcee AI API key": "provider.desc.arcee",
  "Arcee AI base URL override": "provider.desc.arcee",
  "AWS region for Bedrock API calls (e.g. us-east-1, eu-central-1)": "provider.desc.awsbedrock",
  "AWS named profile for Bedrock authentication (from ~/.aws/credentials)": "provider.desc.awsbedrock",
  "Alibaba Cloud DashScope API key (Qwen + multi-provider models)": "provider.desc.dashscope",
  "Custom DashScope base URL (default: coding-intl OpenAI-compat endpoint)": "provider.desc.dashscope",
  "DeepSeek API key for direct DeepSeek access": "provider.desc.deepseek",
  "Custom DeepSeek API base URL (advanced)": "provider.desc.deepseek",
  "Exa API key for AI-native web search and contents": "provider.desc.exa",
  "Firecrawl API key for web search and scraping": "provider.desc.firecrawl",
  "Firecrawl API URL for self-hosted instances (optional)": "provider.desc.firecrawl",
  "Google AI Studio API key (alias for GOOGLE_API_KEY)": "provider.desc.gemini",
  "Google AI Studio base URL override": "provider.desc.gemini",
  "Google OAuth client ID for google-gemini-cli (optional; defaults to Google's public gemini-cli client)": "provider.desc.gemini",
  "Google OAuth client secret for google-gemini-cli (optional)": "provider.desc.gemini",
  "GCP project ID for paid Gemini tiers (free tier auto-provisions)": "provider.desc.gemini",
  "GMI Cloud API key": "provider.desc.gmi",
  "GMI Cloud base URL override": "provider.desc.gmi",
  "Google AI Studio API key (also recognized as GEMINI_API_KEY)": "provider.desc.google",
  "Hugging Face token for Inference Providers (20+ open models via router.huggingface.co)": "provider.desc.huggingface",
  "Hugging Face Inference Providers base URL override": "provider.desc.huggingface",
  "Kimi / Moonshot API key": "provider.desc.kimi",
  "Kimi / Moonshot base URL override": "provider.desc.kimi",
  "Kimi / Moonshot China API key": "provider.desc.kimi",
  "LM Studio bearer token for auth-enabled local servers": "provider.desc.lmstudio",
  "LM Studio base URL override": "provider.desc.lmstudio",
  "Z.AI / GLM API key (also recognized as ZAI_API_KEY / Z_AI_API_KEY)": "provider.desc.lmstudio",
  "Z.AI / GLM base URL override": "provider.desc.lmstudio",
  "MiniMax API key (international)": "provider.desc.minimax",
  "MiniMax base URL override": "provider.desc.minimax",
  "MiniMax API key (China endpoint)": "provider.desc.minimax",
  "MiniMax (China) base URL override": "provider.desc.minimax",
  "Nous Portal base URL override": "provider.desc.nous",
  "NVIDIA NIM API key (build.nvidia.com or local NIM endpoint)": "provider.desc.nvidia",
  "NVIDIA NIM base URL override (e.g. http://localhost:8000/v1 for local NIM)": "provider.desc.nvidia",
  "Ollama Cloud API key (ollama.com — cloud-hosted open models)": "provider.desc.ollamacloud",
  "Ollama Cloud base URL override (default: https://ollama.com/v1)": "provider.desc.ollamacloud",
  "OpenCode Go API key ($10/month subscription for open models)": "provider.desc.opencodego",
  "OpenCode Go base URL override": "provider.desc.opencodego",
  "OpenRouter API key (for vision, web scraping helpers, and MoA)": "provider.desc.openrouter",
  "Parallel API key for AI-native web search and extract": "provider.desc.parallel",
  "Qwen Portal base URL override (default: https://portal.qwen.ai/v1)": "provider.desc.qwenportal",
  "StepFun Step Plan API key": "provider.desc.stepfun",
  "StepFun Step Plan base URL override": "provider.desc.stepfun",
  "xAI API key": "provider.desc.xai",
  "xAI base URL override": "provider.desc.xai",
  "Xiaomi MiMo API key for MiMo models (mimo-v2.5-pro, mimo-v2.5, mimo-v2-pro, mimo-v2-omni, mimo-v2-flash)": "provider.desc.xiaomi",
  "Xiaomi MiMo base URL override (default: https://api.xiaomimimo.com/v1)": "provider.desc.xiaomi",
  "Z.AI API key (alias for GLM_API_KEY)": "provider.desc.zai",
  "OpenCode Zen API key (pay-as-you-go access to curated models)": "provider.desc.zai",
  "OpenCode Zen base URL override": "provider.desc.zai",
  "Azure Foundry API key for custom Azure endpoints": "provider.desc.zai",
  "Azure Foundry base URL (set via 'hermes model' for endpoint-specific config)": "provider.desc.zai",
}

export function translateProviderDesc(desc: string): string {
  const key = PROVIDER_DESC_KEYS[desc]
  if (key) {
    const translations = allTranslations[_currentLocale]
    const fallback = allTranslations['en']
    return translations?.[key] ?? fallback?.[key] ?? desc
  }
  return desc
}

// --- Bootstrap: preload English + saved locale ---
;(async () => {
  await ensureLocale('en')
  const saved = _currentLocale
  if (saved !== 'en') await ensureLocale(saved)
})()
