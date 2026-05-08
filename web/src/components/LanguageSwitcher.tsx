import { Button } from "@nous-research/ui/ui/components/button";
import { Typography } from "@/components/NouiTypography";
import { useI18n } from "@/i18n/context";
import type { Locale } from "@/i18n/types";

const CYCLE: Locale[] = ["en", "zh", "es", "ru", "fr", "de", "ko"];

const FLAGS: Record<Locale, string> = {
  en: "🇬🇧",
  zh: "🇨🇳",
  es: "🇪🇸",
  ru: "🇷🇺",
  fr: "🇫🇷",
  de: "🇩🇪",
  ko: "🇰🇷",
};

const LABELS: Record<Locale, string> = {
  en: "EN",
  zh: "中文",
  es: "ES",
  ru: "RU",
  fr: "FR",
  de: "DE",
  ko: "한국어",
};

/**
 * Compact language toggle — cycles through English, Chinese, Spanish, Russian,
 * French, German, and Korean. Persists choice to localStorage.
 */
export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n();

  const toggle = () => {
    const idx = CYCLE.indexOf(locale);
    const next = CYCLE[(idx + 1) % CYCLE.length];
    setLocale(next);
  };

  return (
    <Button
      ghost
      onClick={toggle}
      title={t.language.switchTo}
      aria-label={t.language.switchTo}
      className="px-2 py-1 normal-case tracking-normal font-normal text-xs text-muted-foreground hover:text-foreground"
    >
      <span className="inline-flex items-center gap-1.5">
        <span className="text-base leading-none">
          {FLAGS[locale]}
        </span>

        <Typography
          mondwest
          className="hidden sm:inline tracking-wide uppercase text-[0.65rem]"
        >
          {LABELS[locale]}
        </Typography>
      </span>
    </Button>
  );
}
