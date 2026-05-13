import type { Agent } from "@/types";
import { AgentCard } from "./AgentCard";

export function AgentGrid({ agents }: AgentGridProps) {
  return (
    <section className="grid grid-cols-1 gap-5 md:grid-cols-3">
      {agents.map((agent, index) => (
        <AgentCard agent={agent} index={index} key={agent.id} />
      ))}
    </section>
  );
}

interface AgentGridProps {
  agents: Agent[];
}
