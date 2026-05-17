import { useRef, useEffect } from "react";
import { Send, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MicButton } from "@/components/MicButton";

interface Props {
  value: string;
  onChange: (text: string) => void;
  onSend: () => void;
  onCancel?: () => void;
  busy?: boolean;          // a turn is in progress
  disabled?: boolean;
}

export function ChatComposer({
  value,
  onChange,
  onSend,
  onCancel,
  busy = false,
  disabled = false,
}: Props) {
  const taRef = useRef<HTMLTextAreaElement>(null);

  // Auto-grow textarea up to ~6 lines.
  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 140) + "px";
  }, [value]);

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!busy && value.trim()) onSend();
    }
  };

  const handleSendClick = () => {
    if (busy && onCancel) onCancel();
    else if (value.trim()) onSend();
  };

  return (
    <div className="flex items-end gap-1.5 rounded-lg border border-border bg-card p-1.5">
      <MicButton
        onTranscript={(text) => {
          if (!text) return;
          const newVal = value ? value + " " + text : text;
          onChange(newVal);
          taRef.current?.focus();
        }}
        onError={(msg) => console.error("[mic]", msg)}
      />
      <textarea
        ref={taRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKey}
        placeholder={busy ? "agent is responding…" : "Ask Hermes anything (Enter to send, Shift+Enter for newline)"}
        disabled={disabled}
        rows={1}
        className="flex-1 resize-none bg-transparent outline-none px-1.5 py-1 text-sm text-foreground placeholder:text-muted-foreground disabled:opacity-50 min-h-[24px] max-h-[140px]"
      />
      <Button
        type="button"
        size="sm"
        variant={busy ? "outline" : "default"}
        onClick={handleSendClick}
        disabled={disabled || (!busy && !value.trim())}
        title={busy ? "Cancel turn" : "Send"}
        aria-label={busy ? "Cancel turn" : "Send"}
      >
        {busy ? <Square className="h-3.5 w-3.5" /> : <Send className="h-3.5 w-3.5" />}
      </Button>
    </div>
  );
}
