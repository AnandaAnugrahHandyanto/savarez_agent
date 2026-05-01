import { useCallback, useEffect, useRef, useState } from "react";
import { Palette, Check } from "lucide-react";
import { Button } from "@nous-research/ui/ui/components/button";
import { ListItem } from "@nous-research/ui/ui/components/list-item";
import { Typography } from "@/components/NouiTypography";
import { BUILTIN_THEMES, useTheme } from "@/themes";
import type { DashboardTheme } from "@/themes/types";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";

/**
 * Compact theme picker mounted next to the language switcher in the header.
 * Built-in themes render a compact chromatic icon derived from their palette
 * so users can preview the color direction before committing. User-defined
 * themes from `~/.hermes/dashboard-themes/*.yaml` that aren't in
 * `BUILTIN_THEMES` render with a neutral placeholder.
 *
 * When placed at the bottom of a container (e.g. the sidebar rail), pass
 * `dropUp` so the menu opens above the trigger instead of clipping below
 * the viewport.
 */
export function ThemeSwitcher({ dropUp = false }: ThemeSwitcherProps) {
  const { themeName, availableThemes, setTheme } = useTheme();
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const close = useCallback(() => setOpen(false), []);

  useEffect(() => {
    if (!open) return;
    const onMouseDown = (e: MouseEvent) => {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        close();
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, close]);

  const current = availableThemes.find((th) => th.name === themeName);
  const currentPreset = BUILTIN_THEMES[themeName];
  const label = current?.label ?? themeName;

  return (
    <div ref={wrapperRef} className="relative">
      <Button
        ghost
        onClick={() => setOpen((o) => !o)}
        className="px-2 py-1 normal-case tracking-normal font-normal text-xs text-muted-foreground hover:text-foreground"
        title={t.theme?.switchTheme ?? "Switch theme"}
        aria-label={t.theme?.switchTheme ?? "Switch theme"}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <span className="inline-flex items-center gap-1.5">
          {currentPreset ? (
            <ThemeToneIcon theme={currentPreset} className="h-4 w-4" />
          ) : (
            <Palette className="h-3.5 w-3.5" />
          )}

          <Typography
            mondwest
            className="hidden sm:inline tracking-wide uppercase text-[0.65rem]"
          >
            {label}
          </Typography>
        </span>
      </Button>

      {open && (
        <div
          role="listbox"
          aria-label={t.theme?.title ?? "Theme"}
          className={cn(
            "absolute z-50 min-w-[240px]",
            dropUp ? "left-0 bottom-full mb-1" : "right-0 top-full mt-1",
            "border border-current/20 bg-background-base/95 backdrop-blur-sm",
            "shadow-[0_12px_32px_-8px_rgba(0,0,0,0.6)]",
          )}
        >
          <div className="border-b border-current/20 px-3 py-2">
            <Typography
              mondwest
              className="text-[0.65rem] tracking-[0.15em] uppercase text-midground/70"
            >
              {t.theme?.title ?? "Theme"}
            </Typography>
          </div>

          {availableThemes.map((th) => {
            const isActive = th.name === themeName;
            const preset = BUILTIN_THEMES[th.name];

            return (
              <ListItem
                key={th.name}
                active={isActive}
                role="option"
                aria-selected={isActive}
                onClick={() => {
                  setTheme(th.name);
                  close();
                }}
                className="gap-3"
              >
                {preset ? (
                  <ThemeToneIcon theme={preset} />
                ) : (
                  <PlaceholderThemeIcon />
                )}

                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <Typography
                    mondwest
                    className="truncate text-[0.75rem] tracking-wide uppercase"
                  >
                    {th.label}
                  </Typography>
                  {th.description && (
                    <Typography className="truncate text-[0.65rem] normal-case tracking-normal text-midground/50">
                      {th.description}
                    </Typography>
                  )}
                </div>

                <Check
                  className={cn(
                    "h-3 w-3 shrink-0 text-midground",
                    isActive ? "opacity-100" : "opacity-0",
                  )}
                />
              </ListItem>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ThemeToneIcon({
  className,
  theme,
}: {
  className?: string;
  theme: DashboardTheme;
}) {
  const { background, midground, warmGlow } = theme.palette;
  const accent = theme.colorOverrides?.accent ?? warmGlow;
  const primary = theme.colorOverrides?.primary ?? midground.hex;
  const toneWheel = `conic-gradient(from 210deg, ${background.hex} 0 28%, ${accent} 28% 50%, ${midground.hex} 50% 73%, ${primary} 73% 88%, ${warmGlow} 88% 100%)`;

  return (
    <span
      aria-hidden
      className={cn(
        "relative h-5 w-5 shrink-0 overflow-hidden rounded-full border border-current/25",
        "shadow-[inset_0_0_0_1px_rgba(255,255,255,0.25)]",
        className,
      )}
      style={{ background: toneWheel }}
    />
  );
}

function PlaceholderThemeIcon() {
  return (
    <span
      aria-hidden
      className="h-5 w-5 shrink-0 rounded-full border border-dashed border-current/25"
    />
  );
}

interface ThemeSwitcherProps {
  dropUp?: boolean;
}
