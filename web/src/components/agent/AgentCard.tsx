import { motion } from "framer-motion";
import { Cpu, Network, Wrench } from "lucide-react";
import type { Agent } from "@/types";
import { cn } from "@/lib/utils";

const ROLE_ICON = {
  orchestrator: Network,
  worker: Wrench,
} satisfies Record<Agent["role"], typeof Cpu>;

const STATUS_CLASS = {
  idle: "bg-warm-beige",
  thinking: "bg-memphis-yellow",
  executing: "bg-memphis-mint",
} satisfies Record<Agent["status"], string>;

export function AgentCard({ agent, index }: AgentCardProps) {
  const Icon = ROLE_ICON[agent.role];
  const isThinking = agent.status === "thinking";

  return (
    <motion.article
      animate={
        isThinking
          ? {
              boxShadow: [
                "4px 4px 0 0 #1A1A1A",
                "8px 8px 0 0 #1A1A1A",
                "4px 4px 0 0 #1A1A1A",
              ],
            }
          : { boxShadow: "4px 4px 0 0 #1A1A1A" }
      }
      className="border-[3px] border-ink bg-warm-beige p-4 text-ink shadow-brutal rounded-none"
      initial={{ opacity: 0, y: 14 }}
      transition={{
        delay: index * 0.06,
        duration: isThinking ? 1.4 : 0.18,
        repeat: isThinking ? Infinity : 0,
      }}
      viewport={{ once: true }}
      whileInView={{ opacity: 1, y: 0 }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="grid h-12 w-12 place-items-center rounded-none border-[3px] border-ink bg-memphis-yellow shadow-brutal">
          <Icon className="h-6 w-6" />
        </div>
        <span
          className={cn(
            "rounded-none border-[3px] border-ink px-2 py-1 font-mono text-[0.65rem] uppercase tracking-[0.12em] shadow-brutal",
            STATUS_CLASS[agent.status],
          )}
        >
          {agent.status}
        </span>
      </div>

      <div className="mt-5">
        <h3 className="font-display text-2xl font-black leading-none tracking-normal">
          {agent.name}
        </h3>
        <p className="mt-2 font-mono text-xs uppercase tracking-[0.16em]">
          {agent.role}
        </p>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {agent.capabilities.map((capability) => (
          <span
            className="rounded-none border-[3px] border-ink bg-white px-2 py-1 font-mono text-[0.65rem] uppercase tracking-[0.08em]"
            key={capability}
          >
            {capability}
          </span>
        ))}
      </div>
    </motion.article>
  );
}

interface AgentCardProps {
  agent: Agent;
  index: number;
}
