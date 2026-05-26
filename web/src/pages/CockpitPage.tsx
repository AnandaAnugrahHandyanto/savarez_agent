import { Button } from "@nous-research/ui/ui/components/button";
import { Typography } from "@/components/NouiTypography";
import { usePageHeader } from "@/contexts/usePageHeader";
import { api, type CockpitStatusResponse } from "@/lib/api";
import type { AguiEvent } from "@/lib/agui";
import { cn } from "@/lib/utils";
import { Bot, CheckCircle2, CircleAlert, CircleDot, Radio, Send, Square, Wrench } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

type TimelineItem = {
  id: string;
  type: string;
  title: string;
  detail?: string;
  ts: number;
  tone?: "ok" | "warn" | "error" | "info";
};

type Message = { role: "user" | "assistant"; content: string };

function eventDetail(event: AguiEvent): string {
  const content = event.delta ?? event.content ?? event.message ?? event.error ?? event.result;
  if (typeof content === "string") return content;
  if (content == null) return "";
  try {
    return JSON.stringify(content);
  } catch {
    return String(content);
  }
}

function titleForEvent(event: AguiEvent): string {
  if (event.type === "TOOL_CALL_START") return `Tool started: ${String(event.toolCallName ?? "tool")}`;
  if (event.type === "TOOL_CALL_END") return `Tool finished: ${String(event.toolCallName ?? "tool")}`;
  if (event.type === "TOOL_CALL_REQUIRES_ACTION") return "Approval needed";
  if (event.type === "RUN_STARTED") return "Run started";
  if (event.type === "RUN_FINISHED") return "Run finished";
  if (event.type === "RUN_ERROR") return "Run failed";
  if (event.type === "TEXT_MESSAGE_CONTENT") return "Assistant streamed text";
  return event.type;
}

function eventTone(event: AguiEvent): TimelineItem["tone"] {
  if (event.type === "RUN_ERROR" || event.error) return "error";
  if (event.type === "TOOL_CALL_REQUIRES_ACTION") return "warn";
  if (event.type === "RUN_FINISHED" || event.type === "TOOL_CALL_END") return "ok";
  return "info";
}

function buildTimelineItem(event: AguiEvent, index: number): TimelineItem {
  return {
    id: `${Date.now()}-${index}-${event.type}`,
    type: event.type,
    title: titleForEvent(event),
    detail: event.type === "TEXT_MESSAGE_CONTENT" ? undefined : eventDetail(event),
    ts: Date.now(),
    tone: eventTone(event),
  };
}

function StatusPill({ status }: { status: CockpitStatusResponse | null }) {
  const apiServer = status?.api_server;
  const ready = Boolean(apiServer?.configured && apiServer?.reachable);
  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm",
        ready
          ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-100"
          : "border-amber-400/40 bg-amber-400/10 text-amber-100",
      )}
    >
      <CircleDot className="h-3.5 w-3.5" />
      {ready ? "AG-UI online" : apiServer?.configured ? "API Server unreachable" : "API Server not configured"}
    </div>
  );
}

export default function CockpitPage() {
  const { setAfterTitle, setTitle } = usePageHeader();
  const [status, setStatus] = useState<CockpitStatusResponse | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("Give me a concise status check and say what tools you can use from this cockpit.");
  const [messages, setMessages] = useState<Message[]>([]);
  const [assistantDraft, setAssistantDraft] = useState("");
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setTitle("Cockpit");
    setAfterTitle(<span className="text-sm text-white/45">AG-UI live run control</span>);
    return () => {
      setTitle(null);
      setAfterTitle(null);
    };
  }, [setAfterTitle, setTitle]);

  useEffect(() => {
    let cancelled = false;
    api
      .getCockpitStatus()
      .then((next) => {
        if (!cancelled) setStatus(next);
      })
      .catch((err) => {
        if (!cancelled) setStatusError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const ready = Boolean(status?.api_server.configured && status?.api_server.reachable);
  const featureReady = Boolean(
    (status?.capabilities as { features?: { agui_run_streaming?: unknown } } | null)?.features
      ?.agui_run_streaming,
  );

  const visibleMessages = useMemo(() => {
    const out = [...messages];
    if (assistantDraft) out.push({ role: "assistant", content: assistantDraft });
    return out;
  }, [assistantDraft, messages]);

  async function startRun() {
    const text = prompt.trim();
    if (!text || running) return;
    setRunError(null);
    setAssistantDraft("");
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setTimeline([]);
    const controller = new AbortController();
    abortRef.current = controller;
    setRunning(true);
    let assistantText = "";
    let eventIndex = 0;

    try {
      await api.streamCockpitAguiRun(
        {
          threadId: "dashboard-cockpit",
          messages: [{ role: "user", content: text }],
        },
        (event) => {
          if (event.type === "TEXT_MESSAGE_CONTENT") {
            const delta = String(event.delta ?? event.content ?? "");
            assistantText += delta;
            setAssistantDraft(assistantText);
          }
          if (event.type === "RUN_ERROR") {
            setRunError(eventDetail(event) || "Run failed");
          }
          if (event.type !== "TEXT_MESSAGE_START" && event.type !== "TEXT_MESSAGE_END") {
            setTimeline((prev) => [buildTimelineItem(event, eventIndex++), ...prev].slice(0, 80));
          }
        },
        controller.signal,
      );
      if (assistantText) {
        setMessages((prev) => [...prev, { role: "assistant", content: assistantText }]);
      }
      setAssistantDraft("");
    } catch (err) {
      if ((err as { name?: string }).name !== "AbortError") {
        setRunError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

  function stopRun() {
    abortRef.current?.abort();
    setRunning(false);
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-5 overflow-auto p-4 md:p-6">
      <section className="rounded-3xl border border-white/10 bg-gradient-to-br from-[#123131] to-[#071c1c] p-5 shadow-2xl">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <Typography as="h2" variant="lg" className="font-bold">Hermes Cockpit</Typography>
              <StatusPill status={status} />
            </div>
            <Typography className="max-w-2xl text-white/65">
              Start an agent run through the AG-UI bridge and watch structured lifecycle events,
              tool calls, approvals, and streamed assistant text in one place.
            </Typography>
          </div>
          <div className="grid min-w-64 gap-2 rounded-2xl border border-white/10 bg-black/20 p-3 text-sm text-white/70">
            <div className="flex justify-between gap-3"><span>Endpoint</span><span>{status?.api_server.base_url ?? "checking..."}</span></div>
            <div className="flex justify-between gap-3"><span>Auth</span><span>{status?.api_server.auth_configured ? status.api_server.key_preview : "not set"}</span></div>
            <div className="flex justify-between gap-3"><span>AG-UI</span><span>{featureReady ? "advertised" : "unknown"}</span></div>
          </div>
        </div>
        {statusError && <div className="mt-4 rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100">{statusError}</div>}
      </section>

      <div className="grid min-h-[620px] gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="flex min-h-0 flex-col rounded-3xl border border-white/10 bg-[#0b2323] shadow-xl">
          <div className="border-b border-white/10 p-4">
            <Typography as="h3" variant="sm" className="font-bold uppercase">Run console</Typography>
          </div>
          <div className="min-h-0 flex-1 space-y-3 overflow-auto p-4">
            {visibleMessages.length === 0 ? (
              <div className="flex h-full min-h-72 items-center justify-center rounded-2xl border border-dashed border-white/10 text-center text-white/50">
                <div>
                  <Bot className="mx-auto mb-3 h-8 w-8" />
                  Send a prompt to start a cockpit run.
                </div>
              </div>
            ) : (
              visibleMessages.map((message, idx) => (
                <div
                  key={`${message.role}-${idx}`}
                  className={cn(
                    "max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6",
                    message.role === "user"
                      ? "ml-auto bg-emerald-300 text-emerald-950"
                      : "bg-white/8 text-white/85",
                  )}
                >
                  <div className="mb-1 text-xs uppercase tracking-wide opacity-60">{message.role}</div>
                  <div className="whitespace-pre-wrap">{message.content}</div>
                </div>
              ))
            )}
          </div>
          <div className="border-t border-white/10 p-4">
            {runError && <div className="mb-3 rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100">{runError}</div>}
            <div className="flex flex-col gap-3 md:flex-row">
              <textarea
                className="min-h-24 flex-1 resize-none rounded-2xl border border-white/10 bg-black/25 p-3 text-sm text-white outline-none placeholder:text-white/35 focus:border-emerald-300/60"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") void startRun();
                }}
                placeholder="Ask Hermes to do something..."
              />
              <div className="flex gap-2 md:flex-col">
                <Button onClick={startRun} disabled={!prompt.trim() || running || !ready} className="gap-2">
                  <Send className="h-4 w-4" />
                  Start
                </Button>
                <Button onClick={stopRun} disabled={!running} className="gap-2">
                  <Square className="h-4 w-4" />
                  Stop
                </Button>
              </div>
            </div>
            {!ready && <p className="mt-2 text-xs text-amber-100/80">Enable and restart the API Server to run cockpit prompts.</p>}
          </div>
        </section>

        <aside className="flex min-h-0 flex-col rounded-3xl border border-white/10 bg-[#0b2323] shadow-xl">
          <div className="flex items-center gap-2 border-b border-white/10 p-4">
            <Radio className="h-4 w-4 text-emerald-200" />
            <Typography as="h3" variant="sm" className="font-bold uppercase">Live events</Typography>
          </div>
          <div className="min-h-0 flex-1 overflow-auto p-4">
            {timeline.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-white/10 p-5 text-sm text-white/50">
                AG-UI events will appear here as soon as a run starts.
              </div>
            ) : (
              <div className="space-y-3">
                {timeline.map((item) => (
                  <div key={item.id} className="rounded-2xl border border-white/10 bg-black/20 p-3">
                    <div className="flex items-start gap-3">
                      {item.tone === "ok" ? (
                        <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-300" />
                      ) : item.tone === "warn" || item.tone === "error" ? (
                        <CircleAlert className="mt-0.5 h-4 w-4 text-amber-300" />
                      ) : (
                        <Wrench className="mt-0.5 h-4 w-4 text-sky-300" />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-white/90">{item.title}</div>
                        <div className="text-xs text-white/35">{new Date(item.ts).toLocaleTimeString()}</div>
                        {item.detail && <pre className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap rounded-xl bg-black/25 p-2 text-xs text-white/60">{item.detail}</pre>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
