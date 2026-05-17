import { Markdown } from "@/components/Markdown";
import { SpeakButton } from "@/components/SpeakButton";
import { CheckCircle2, XCircle, Loader2, AlertCircle, ChevronDown, ChevronRight, Info } from "lucide-react";
import { useState } from "react";

/* ------------------------------------------------------------------ */
/*  Item types — flat list state for ChatPage                          */
/* ------------------------------------------------------------------ */

export type ChatItem =
  | { id: string; kind: "user"; text: string }
  | { id: string; kind: "assistant"; text: string; pending?: boolean }
  | {
      id: string;
      kind: "tool";
      callId: string;
      tool: string;
      args: string;
      status: "running" | "ok" | "failed";
      summary?: string;
    }
  | { id: string; kind: "system"; detail: string }
  | { id: string; kind: "error"; detail: string };

/* ------------------------------------------------------------------ */
/*  Renderers                                                          */
/* ------------------------------------------------------------------ */

export function UserMessage({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-lg bg-primary px-3 py-1.5 text-primary-foreground text-sm whitespace-pre-wrap">
        {text}
      </div>
    </div>
  );
}

export function AssistantMessage({
  text,
  pending,
}: {
  text: string;
  pending?: boolean;
}) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] flex flex-col gap-1">
        <div className="rounded-lg bg-card border border-border px-3 py-2">
          {text ? (
            <div className="text-sm">
              <Markdown content={text} />
            </div>
          ) : pending ? (
            <div className="text-sm text-muted-foreground flex items-center gap-1.5">
              <Loader2 className="h-3 w-3 animate-spin" />
              <span>thinking…</span>
            </div>
          ) : null}
        </div>
        {text && !pending && (
          <div className="flex items-center gap-1 px-1">
            <SpeakButton text={text} variant="ghost" size="sm" />
          </div>
        )}
      </div>
    </div>
  );
}

export function ToolCallCard({
  tool,
  args,
  status,
  summary,
}: {
  tool: string;
  args: string;
  status: "running" | "ok" | "failed";
  summary?: string;
}) {
  const [open, setOpen] = useState(false);
  const Icon = status === "running" ? Loader2 : status === "ok" ? CheckCircle2 : XCircle;
  const color =
    status === "running"
      ? "text-muted-foreground"
      : status === "ok"
      ? "text-success"
      : "text-destructive";

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] w-full rounded-md border border-border bg-muted/30 text-xs overflow-hidden">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1.5 w-full px-2 py-1 hover:bg-muted/50"
        >
          {open ? (
            <ChevronDown className="h-3 w-3 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3 w-3 text-muted-foreground" />
          )}
          <Icon className={`h-3.5 w-3.5 ${color} ${status === "running" ? "animate-spin" : ""}`} />
          <code className="font-mono text-foreground">{tool}</code>
          {summary && status !== "running" && (
            <span className="text-muted-foreground truncate ml-1">— {summary}</span>
          )}
        </button>
        {open && (
          <div className="border-t border-border bg-background/50 p-2">
            <div className="text-muted-foreground text-[10px] uppercase tracking-wider mb-1">
              args
            </div>
            <pre className="font-mono text-[11px] whitespace-pre-wrap break-all text-foreground">
              {args || "(empty)"}
            </pre>
            {summary && (
              <>
                <div className="text-muted-foreground text-[10px] uppercase tracking-wider mb-1 mt-2">
                  result
                </div>
                <pre className="font-mono text-[11px] whitespace-pre-wrap break-all text-foreground">
                  {summary}
                </pre>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function SystemBubble({ detail }: { detail: string }) {
  return (
    <div className="flex justify-center">
      <div className="max-w-[90%] rounded-md border border-border bg-muted/40 px-3 py-2 text-xs flex items-start gap-2">
        <Info className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" />
        <pre className="whitespace-pre-wrap font-mono text-foreground/80 leading-snug">{detail}</pre>
      </div>
    </div>
  );
}

export function ErrorBanner({ detail }: { detail: string }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm flex items-start gap-2">
        <AlertCircle className="h-4 w-4 text-destructive mt-0.5 shrink-0" />
        <div className="text-destructive whitespace-pre-wrap">{detail}</div>
      </div>
    </div>
  );
}

export function MessageItem({ item }: { item: ChatItem }) {
  switch (item.kind) {
    case "user":
      return <UserMessage text={item.text} />;
    case "assistant":
      return <AssistantMessage text={item.text} pending={item.pending} />;
    case "tool":
      return (
        <ToolCallCard
          tool={item.tool}
          args={item.args}
          status={item.status}
          summary={item.summary}
        />
      );
    case "system":
      return <SystemBubble detail={item.detail} />;
    case "error":
      return <ErrorBanner detail={item.detail} />;
  }
}
