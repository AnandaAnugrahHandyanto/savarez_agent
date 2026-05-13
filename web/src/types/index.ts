export interface Agent {
  id: string;
  name: string;
  role: "orchestrator" | "worker";
  status: "idle" | "thinking" | "executing";
  capabilities: string[];
}

export interface Message {
  id: string;
  role: "user" | "agent";
  content: string;
  metadata?: {
    latency?: number;
    tools?: string[];
  };
}

export interface Task {
  taskId: string;
  status: "pending" | "success" | "failed";
  nodes: string[];
}
