import { useEffect } from "react";
import { ShieldAlert, X } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  callId: string;
  command: string;
  description: string;
  allowPermanent?: boolean;
  onDecide: (decision: "once" | "session" | "always" | "deny") => void;
}

export function ApprovalDialog({
  command,
  description,
  allowPermanent = true,
  onDecide,
}: Props) {
  // Escape = deny (consistent with the CLI prompt's default).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDecide("deny");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onDecide]);

  return (
    <div className="fixed inset-0 z-50 bg-background/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-xl rounded-lg border border-destructive/40 bg-card shadow-xl">
        <div className="flex items-start gap-3 p-4 border-b border-border">
          <ShieldAlert className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="text-sm font-semibold text-foreground">
              Dangerous command — approve before running?
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              {description}
            </div>
          </div>
          <button
            type="button"
            onClick={() => onDecide("deny")}
            className="text-muted-foreground hover:text-foreground"
            title="Deny (Esc)"
            aria-label="Deny"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-4">
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
            Command
          </div>
          <pre className="font-mono text-xs whitespace-pre-wrap break-all rounded-md bg-muted/40 border border-border px-2 py-2 text-foreground">
            {command}
          </pre>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2 px-4 pb-4">
          <Button variant="ghost" size="sm" onClick={() => onDecide("deny")}>
            Deny
          </Button>
          <Button variant="outline" size="sm" onClick={() => onDecide("once")}>
            Allow once
          </Button>
          <Button variant="outline" size="sm" onClick={() => onDecide("session")}>
            Allow this session
          </Button>
          {allowPermanent && (
            <Button variant="default" size="sm" onClick={() => onDecide("always")}>
              Always allow
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
