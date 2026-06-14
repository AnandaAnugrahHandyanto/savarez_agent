import { Button } from "@nous-research/ui/ui/components/button";
import { cn } from "@/lib/utils";
import { Check, Copy, GitBranch } from "lucide-react";
import { useCallback, useState } from "react";

import { useI18n } from "@/i18n";

interface Props {
  text: string;
  align: "start" | "end";
  onFork?: () => void;
  forking?: boolean;
}

export function MessageBubbleActions({
  text,
  align,
  onFork,
  forking,
}: Props) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    const value = text.trim();
    if (!value) return;
    void navigator.clipboard.writeText(value).then(
      () => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      },
      () => {},
    );
  }, [text]);

  const canCopy = text.trim().length > 0;

  return (
    <div
      className={cn(
        "flex items-center gap-0.5 pt-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100",
        align === "end" ? "justify-end" : "justify-start",
      )}
    >
      <Button
        type="button"
        ghost
        size="icon"
        className="h-7 w-7 shrink-0 text-text-tertiary hover:text-foreground"
        disabled={!canCopy}
        aria-label={copied ? t.chatSession.copied : t.chatSession.copyMessage}
        title={copied ? t.chatSession.copied : t.chatSession.copyMessage}
        onClick={handleCopy}
      >
        {copied ? (
          <Check className="h-3.5 w-3.5 shrink-0" aria-hidden />
        ) : (
          <Copy className="h-3.5 w-3.5 shrink-0" aria-hidden />
        )}
      </Button>
      {onFork && (
        <Button
          type="button"
          ghost
          size="icon"
          className="h-7 w-7 shrink-0 text-text-tertiary hover:text-foreground"
          disabled={forking || !canCopy}
          aria-label={t.chatSession.forkMessage}
          title={t.chatSession.forkMessage}
          onClick={onFork}
        >
          <GitBranch className="h-3.5 w-3.5 shrink-0" aria-hidden />
        </Button>
      )}
    </div>
  );
}
