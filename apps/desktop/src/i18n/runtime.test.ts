import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { TRANSLATIONS } from './catalog'
import { setRuntimeI18nLocale, translateNow } from './runtime'

describe('desktop i18n runtime translator', () => {
  beforeEach(() => {
    setRuntimeI18nLocale('en')
  })

  afterEach(() => {
    setRuntimeI18nLocale('en')
  })

  it('translates string paths for the active runtime locale', () => {
    setRuntimeI18nLocale('zh')

    expect(translateNow('boot.ready')).toBe('Hermes Desktop 已就绪')
  })

  it('registers Korean translations in the runtime catalog', () => {
    setRuntimeI18nLocale('ko')

    expect(TRANSLATIONS.ko.common.save).toBe('저장')
    expect(translateNow('language.label')).toBe('언어')
  })

  it('passes arguments to function translations', () => {
    expect(translateNow('notifications.updateReadyMessage', 2)).toBe('2 new changes available.')
  })

  it('returns the key when no locale can resolve a path', () => {
    setRuntimeI18nLocale('zh')

    expect(translateNow('missing.path')).toBe('missing.path')
  })
})
