import { Button } from "@nous-research/ui/ui/components/button";
import { Typography } from "@/components/NouiTypography";
import { useI18n } from "@/i18n/context";

/**
 * Compact language toggle — cycles through English, Chinese, and Hungarian.
 * Persists choice to localStorage.
 */
export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n();

  const toggle = () => {
    if (locale === "en") setLocale("zh");
    else if (locale === "zh") setLocale("hu");
    else setLocale("en");
  };

  const flag = locale === "en" ? "🇬🇧" : locale === "zh" ? "🇨🇳" : "🇭🇺";
  const label = locale === "en" ? "EN" : locale === "zh" ? "中文" : "HU";

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
          {flag}
        </span>

        <Typography
          mondwest
          className="hidden sm:inline tracking-wide uppercase text-[0.65rem]"
        >
          {label}
        </Typography>
      </span>
    </Button>
  );
}
