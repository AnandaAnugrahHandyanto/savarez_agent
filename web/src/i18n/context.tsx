import { useState, useCallback, type ReactNode } from "react";
import type { Locale, Translations } from "./types";
import { I18nContext, type I18nContextValue } from "./base";
import { en } from "./en";
import { ko } from "./ko";
import { zh } from "./zh";

const TRANSLATIONS: Record<Locale, Translations> = { en, zh, ko };
const STORAGE_KEY = "hermes-locale";
const LOCALES = new Set<Locale>(["en", "zh", "ko"]);

function isLocale(value: string | null): value is Locale {
  return value !== null && LOCALES.has(value as Locale);
}

function getInitialLocale(): Locale {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (isLocale(stored)) return stored;
  } catch {
    // SSR or privacy mode
  }
  return "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(getInitialLocale);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      // ignore
    }
  }, []);

  const value: I18nContextValue = {
    locale,
    setLocale,
    t: TRANSLATIONS[locale],
  };

  return (
    <I18nContext.Provider value={value}>
      {children}
    </I18nContext.Provider>
  );
}
