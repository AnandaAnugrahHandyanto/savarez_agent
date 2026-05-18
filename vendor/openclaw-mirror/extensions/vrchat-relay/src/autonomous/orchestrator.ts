import type { GPT55LowOrchestratorConfig } from "./config.js";
import {
  AGENT_DECISION_JSON_SCHEMA,
  parseAgentDecisionJson,
  validateAgentDecision,
  type AgentDecision,
} from "./decision.js";
import type { InputHubSnapshot } from "./input-hub.js";

export interface GPT55LowOrchestratorRequest {
  model: string;
  reasoning: {
    effort: "low" | "medium" | "high" | "xhigh";
  };
  maxOutputTokens: number;
  responseFormat: {
    type: "json_schema";
    name: "AgentDecision";
    schema: typeof AGENT_DECISION_JSON_SCHEMA;
  };
  messages: Array<{
    role: "system" | "user";
    content: string;
  }>;
}

export type AgentDecisionCompletion = (
  request: GPT55LowOrchestratorRequest,
) => Promise<string | unknown>;

export interface GPT55LowOrchestratorOptions {
  config: GPT55LowOrchestratorConfig;
  complete?: AgentDecisionCompletion;
}

export class GPT55LowOrchestrator {
  constructor(private readonly options: GPT55LowOrchestratorOptions) {}

  buildRequest(snapshot: InputHubSnapshot): GPT55LowOrchestratorRequest {
    return {
      model: this.options.config.model,
      reasoning: {
        effort: this.options.config.reasoning.effort,
      },
      maxOutputTokens: this.options.config.maxOutputTokens,
      responseFormat: {
        type: "json_schema",
        name: "AgentDecision",
        schema: AGENT_DECISION_JSON_SCHEMA,
      },
      messages: [
        {
          role: "system",
          content: [
            "You are OpenClaw's VRChat own-avatar orchestrator.",
            "Return only JSON matching AgentDecision.",
            "Use subtle avatar actions. Do not request VRChat login, client modification, DLL injection, EAC bypass, or automatic world joins.",
            "Keep public-instance behavior restrained. Do not use movement unless explicit configuration enables it.",
          ].join("\n"),
        },
        {
          role: "user",
          content: JSON.stringify(
            {
              inputEvents: snapshot.events.map((event) => ({
                source: event.source,
                text: event.text,
                atMs: event.atMs,
                metadata: event.metadata ?? {},
              })),
              latestText: snapshot.latestText,
              latestSpeechToText: snapshot.latestSpeechToText,
              latestVisionObservation: snapshot.latestVisionObservation,
              latestStreamComment: snapshot.latestStreamComment,
            },
            null,
            2,
          ),
        },
      ],
    };
  }

  async decide(snapshot: InputHubSnapshot): Promise<AgentDecision> {
    if (!this.options.complete) {
      throw new Error("GPT55LowOrchestrator requires an injected completion function");
    }
    const raw = await this.options.complete(this.buildRequest(snapshot));
    const result =
      typeof raw === "string" ? parseAgentDecisionJson(raw) : validateAgentDecision(raw);
    if (!result.ok || !result.decision) {
      throw new Error(`Invalid AgentDecision: ${result.errors.join("; ")}`);
    }
    return result.decision;
  }
}
