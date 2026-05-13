import { useActionState, useOptimistic, useRef } from "react";
import { SendHorizontal } from "lucide-react";
import type { Message } from "@/types";

const initialMessages: Message[] = [
  {
    id: "system-boot",
    role: "agent",
    content: "ORCHESTRATION BUS READY.",
    metadata: { latency: 12, tools: ["router", "scheduler"] },
  },
];

interface ChatState {
  messages: Message[];
}

async function submitMessage(
  state: ChatState,
  formData: FormData,
): Promise<ChatState> {
  const content = String(formData.get("message") ?? "").trim();
  if (!content) return state;

  await new Promise((resolve) => window.setTimeout(resolve, 360));

  return {
    messages: [
      ...state.messages,
      {
        id: crypto.randomUUID(),
        role: "agent",
        content: `ACK: ${content}`,
        metadata: { latency: 360, tools: ["orchestrator"] },
      },
    ],
  };
}

export function ChatConsole() {
  const formRef = useRef<HTMLFormElement>(null);
  const [state, formAction, pending] = useActionState(submitMessage, {
    messages: initialMessages,
  });
  const [optimisticMessages, addOptimisticMessage] = useOptimistic(
    state.messages,
    (messages, content: string) => [
      ...messages,
      {
        id: `optimistic-${Date.now()}`,
        role: "user" as const,
        content,
        metadata: { tools: ["optimistic"] },
      },
    ],
  );

  return (
    <section className="border-[3px] border-ink bg-warm-beige p-4 text-ink shadow-brutal rounded-none">
      <div className="mb-4 flex items-center justify-between border-[3px] border-ink bg-memphis-blue px-3 py-2 text-white shadow-brutal">
        <h2 className="font-display text-xl font-black">ChatConsole</h2>
        <span className="font-metric text-sm font-black uppercase tracking-[0.16em]">
          {pending ? "routing" : "online"}
        </span>
      </div>

      <div className="grid max-h-[22rem] gap-3 overflow-y-auto border-[3px] border-ink bg-warm-white p-3">
        {optimisticMessages.map((message) => (
          <article
            className={
              message.role === "user"
                ? "ml-auto max-w-[85%] border-[3px] border-ink bg-memphis-yellow p-3 shadow-brutal"
                : "mr-auto max-w-[85%] border-[3px] border-ink bg-white p-3 shadow-brutal"
            }
            key={message.id}
          >
            <p className="font-mono text-xs uppercase tracking-[0.12em]">
              {message.role}
            </p>
            <p className="mt-2 font-sans text-sm font-bold leading-snug">
              {message.content}
            </p>
            {message.metadata?.tools?.length ? (
              <p className="mt-2 font-mono text-[0.65rem] uppercase tracking-[0.1em]">
                tools: {message.metadata.tools.join(", ")}
              </p>
            ) : null}
          </article>
        ))}
      </div>

      <form
        action={(formData) => {
          const content = String(formData.get("message") ?? "").trim();
          if (content) addOptimisticMessage(content);
          formRef.current?.reset();
          formAction(formData);
        }}
        className="mt-4 flex gap-3"
        ref={formRef}
      >
        <input
          className="min-w-0 flex-1 rounded-none border-[3px] border-ink bg-white px-3 py-3 font-mono text-sm text-ink shadow-brutal outline-none focus:shadow-brutal-lg"
          name="message"
          placeholder="ROUTE MESSAGE..."
          type="text"
        />
        <button
          className="rounded-none border-[3px] border-ink bg-memphis-mint px-4 py-3 font-mono text-sm font-black uppercase tracking-[0.12em] text-ink shadow-brutal transition-transform hover:-translate-x-1 hover:-translate-y-1 hover:shadow-brutal-lg active:translate-x-1 active:translate-y-1 active:shadow-none"
          type="submit"
        >
          <SendHorizontal className="h-5 w-5" />
        </button>
      </form>
    </section>
  );
}
