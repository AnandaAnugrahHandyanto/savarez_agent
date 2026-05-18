import { describe, expect, it } from "vitest";
import { DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG } from "./config.js";
import { validateAgentDecision } from "./decision.js";
import { InputHub } from "./input-hub.js";
import { GPT55LowOrchestrator } from "./orchestrator.js";

describe("AgentDecision", () => {
  it("validates a structured autonomous avatar decision", () => {
    const result = validateAgentDecision({
      schemaVersion: 1,
      replyText: "Hello from OpenClaw.",
      state: "speaking",
      emotion: "happy",
      action: "small_nod",
      useVoice: true,
      emergencyStop: false,
      lookX: 0.2,
      lookY: -0.1,
      chatBoxText: "Hello VRChat",
    });

    expect(result.ok).toBe(true);
    expect(result.decision).toMatchObject({
      state: "speaking",
      emotion: "happy",
      action: "small_nod",
      useVoice: true,
    });
  });

  it("rejects invalid states, emotions, and action ids", () => {
    const result = validateAgentDecision({
      schemaVersion: 1,
      replyText: "bad",
      state: "walking",
      emotion: "panic",
      action: 99,
      useVoice: true,
      emergencyStop: false,
    });

    expect(result.ok).toBe(false);
    expect(result.errors.join("\n")).toContain("state must be one of");
    expect(result.errors.join("\n")).toContain("emotion must be one of");
    expect(result.errors.join("\n")).toContain("action id must be in the configured allowlist");
  });
});

describe("GPT55LowOrchestrator", () => {
  it("builds gpt-5.5 low-reasoning structured JSON requests by default", () => {
    const hub = new InputHub({
      config: DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.inputHub,
      speechToText: DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.speechToText,
    });
    hub.pushTextBox("hello");
    const orchestrator = new GPT55LowOrchestrator({
      config: DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.orchestrator,
    });

    const request = orchestrator.buildRequest(hub.snapshot());

    expect(request.model).toBe("gpt-5.5");
    expect(request.reasoning.effort).toBe("low");
    expect(request.responseFormat.name).toBe("AgentDecision");
    expect(request.messages.at(-1)?.content).toContain("hello");
  });

  it("returns validated AgentDecision JSON from an injected runtime completion", async () => {
    const orchestrator = new GPT55LowOrchestrator({
      config: DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.orchestrator,
      complete: async () =>
        JSON.stringify({
          schemaVersion: 1,
          replyText: "I am listening.",
          state: "listening",
          emotion: "neutral",
          action: "small_nod",
          useVoice: true,
          emergencyStop: false,
        }),
    });

    await expect(orchestrator.decide({ events: [] })).resolves.toMatchObject({
      state: "listening",
      action: "small_nod",
      useVoice: true,
    });
  });
});
