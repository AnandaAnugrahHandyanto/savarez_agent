import { cn } from "@/lib/utils";

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "flex h-9 w-full rounded-[calc(var(--theme-radius)+2px)] border border-border/70",
        "bg-background-base/35 px-3 py-1 font-courier text-sm backdrop-blur-xl transition-colors",
        "placeholder:text-muted-foreground",
        "focus-visible:border-midground/45 focus-visible:outline-none",
        "focus-visible:ring-1 focus-visible:ring-midground/35",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  );
}
