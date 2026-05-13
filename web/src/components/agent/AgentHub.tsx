import type { Agent } from "@/types";
import { ChatConsole } from "@/components/ChatConsole";
import { AgentGrid } from "./AgentGrid";

const AGENTS: Agent[] = [
  {
    id: "orchestrator",
    name: "Orchestrator",
    role: "orchestrator",
    status: "thinking",
    capabilities: ["routing", "planning", "handoff"],
  },
  {
    id: "worker-alpha",
    name: "Worker Alpha",
    role: "worker",
    status: "executing",
    capabilities: ["patch", "build", "verify"],
  },
  {
    id: "worker-beta",
    name: "Worker Beta",
    role: "worker",
    status: "idle",
    capabilities: ["research", "triage", "logs"],
  },
];

export default function AgentHub() {
  return (
    <main className="min-h-full bg-warm-white text-ink">
      <section className="grid gap-6">
        <header className="border-[3px] border-ink bg-memphis-yellow p-5 shadow-brutal-lg rounded-none">
          <p className="font-mono text-xs font-bold uppercase tracking-[0.18em]">
            Neo-Brutalist Agentic Workflow Hub
          </p>
          <h1 className="mt-3 font-display text-4xl font-black leading-none tracking-normal sm:text-6xl">
            Hermes Agent UI
          </h1>
        </header>

        <AgentGrid agents={AGENTS} />

        <div className="grid gap-5 xl:grid-cols-[1fr_22rem]">
          <ChatConsole />
          <aside className="border-[3px] border-ink bg-memphis-coral p-4 text-ink shadow-brutal rounded-none">
            <p className="font-mono text-xs font-black uppercase tracking-[0.16em]">
              Metrics
            </p>
            <div className="mt-4 grid gap-3">
              {[
                ["ACTIVE", "03"],
                ["TASKS", "18"],
                ["LATENCY", "360MS"],
              ].map(([label, value]) => (
                <div
                  className="border-[3px] border-ink bg-white p-3 shadow-brutal"
                  key={label}
                >
                  <p className="font-mono text-[0.65rem] uppercase tracking-[0.12em]">
                    {label}
                  </p>
                  <p className="font-metric text-4xl font-black leading-none">
                    {value}
                  </p>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </section>
    </main>
  );
}
