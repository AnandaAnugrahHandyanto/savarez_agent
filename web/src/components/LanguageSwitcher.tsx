import { Select, SelectOption } from "@nous-research/ui/ui/components/select";
import { useI18n } from "@/i18n";
import type { Locale } from "@/i18n/types";

/**
 * Compact language selector. Persists choice to localStorage.
 */
export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n();

  return (
    <div title={t.language.switchTo} aria-label={t.language.switchTo}>
      <Select
        value={locale}
        onValueChange={(value) => setLocale(value as Locale)}
        className="h-8 w-[5.5rem] text-xs"
      >
        <SelectOption value="en">🇬🇧 EN</SelectOption>
        <SelectOption value="zh">🇨🇳 中文</SelectOption>
        <SelectOption value="ko">🇰🇷 한국어</SelectOption>
      </Select>
    </div>
  );
}
