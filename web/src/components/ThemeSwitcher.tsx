import { useCallback } from "react";
import { Moon, Sun } from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { useTheme } from "@/themes";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";

/**
 * 9router.com-style dark/light mode toggle with Moon/Sun icons.
 * Switches between the default dark theme and "nous-blue" light theme.
 * Persisted via ThemeProvider's localStorage handling.
 *
 * Accepts the same positional props as the previous palette-dropdown
 * version for backward compatibility with call sites in App.tsx/SystemPage.
 */
export function ThemeSwitcher() {
  const { themeName, setTheme } = useTheme();
  const { t } = useI18n();

  const isDarkMode = themeName === "default";

  const toggleTheme = useCallback(() => {
    setTheme(isDarkMode ? "nous-blue" : "default");
  }, [isDarkMode, setTheme]);

  return (
    <Button
      ghost
      size="icon"
      onClick={toggleTheme}
      className={cn(
        "p-1 rounded-full transition-colors duration-200",
        "hover:bg-[var(--color-accent)] hover:text-white",
        "text-[var(--color-accent)] focus-visible:ring-[var(--color-accent)]",
        "flex items-center justify-center"
      )}
      title={t.theme?.switchTheme ?? "Switch theme"}
      aria-label={t.theme?.switchTheme ?? "Switch theme"}
    >
      {isDarkMode ? (
        <Sun className="h-4 w-4" />
      ) : (
        <Moon className="h-4 w-4" />
      )}
    </Button>
  );
}
