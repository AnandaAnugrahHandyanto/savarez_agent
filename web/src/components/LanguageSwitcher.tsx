import { Button } from "@nous-research/ui/ui/components/button";
import { Typography } from "@/components/NouiTypography";
import { useI18n } from "@/i18n/context";

/**
 * Compact language toggle — cycles between English, Chinese, and Korean.
 * Persists choice to localStorage.
 */
export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n();

  const cycle = () => {
    if (locale === "en") setLocale("zh");
    else if (locale === "zh") setLocale("ko");
    else setLocale("en");
  };

  const flag = locale === "en" ? "🇬🇧" : locale === "zh" ? "🇨🇳" : "🇰🇷";
  const label = locale === "en" ? "EN" : locale === "zh" ? "中文" : "한국어";

  return (
    <Button
      ghost
      onClick={cycle}
      title={t.language.switchTo}
      aria-label={t.language.switchTo}
      className="px-2 py-1 normal-case tracking-normal font-normal text-xs text-muted-foreground hover:text-foreground"
    >
      <span className="inline-flex items-center gap-1.5">
        <span className="text-base leading-none">{flag}</span>

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
