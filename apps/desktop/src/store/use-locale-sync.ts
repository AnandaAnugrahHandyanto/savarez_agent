import { useEffect, useState } from 'react'
import { onLocaleChange } from './i18n'

/**
 * Forces the component to re-render whenever the locale changes.
 * Use in components that import `t()` directly from @/store/i18n
 * instead of using the reactive `useTranslation()` hook.
 */
export function useLocaleSync() {
  const [, tick] = useState(0)
  useEffect(() => onLocaleChange(() => tick(n => n + 1)), [])
}
