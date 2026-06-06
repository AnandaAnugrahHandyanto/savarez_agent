import { en } from './en'
import { ptBr } from './pt-br'
import type { Locale, Translations } from './types'
import { zh } from './zh'

export const TRANSLATIONS: Record<Locale, Translations> = {
  en,
  'pt-br': ptBr,
  zh
}
