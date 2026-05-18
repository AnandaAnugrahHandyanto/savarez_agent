import type { VRChatOwnAvatarController } from "../own-avatar/controller.js";
import type { AudioOutputRouter } from "./audio-output.js";
import type { VRChatChatBoxSender } from "./chatbox.js";
import type { AutonomousVrchatAiConfig } from "./config.js";
import type { AgentDecision } from "./decision.js";
import type { InputHub, InputHubEvent } from "./input-hub.js";
import type { GPT55LowOrchestrator } from "./orchestrator.js";
import type { VOICEVOXAdapter } from "./voicevox.js";

export interface AutonomousVrchatAiRuntimeOptions {
  config: AutonomousVrchatAiConfig;
  inputHub: InputHub;
  orchestrator: GPT55LowOrchestrator;
  voicevox: VOICEVOXAdapter;
  audioOutput: AudioOutputRouter;
  ownAvatarController: VRChatOwnAvatarController;
  chatBox: VRChatChatBoxSender;
  log?: {
    info?: (operation: string, details?: Record<string, unknown>) => void;
    warn?: (operation: string, details?: Record<string, unknown>) => void;
    error?: (operation: string, error: string, details?: Record<string, unknown>) => void;
  };
}

export interface ApplyDecisionResult {
  decision: AgentDecision;
  voiceRouted: boolean;
  chatBoxSent: boolean;
}

export class AutonomousVrchatAiRuntime {
  constructor(private readonly options: AutonomousVrchatAiRuntimeOptions) {}

  ingest(event: InputHubEvent): ReturnType<InputHub["push"]> {
    return this.options.inputHub.push(event);
  }

  async processBufferedInputs(): Promise<ApplyDecisionResult> {
    const snapshot = this.options.inputHub.flush();
    this.options.ownAvatarController.applyState("thinking");
    const decision = await this.options.orchestrator.decide(snapshot);
    return this.applyDecision(decision);
  }

  async applyDecision(decision: AgentDecision): Promise<ApplyDecisionResult> {
    if (decision.emergencyStop) {
      this.options.ownAvatarController.emergencyStop();
      return { decision, voiceRouted: false, chatBoxSent: false };
    }

    this.options.ownAvatarController.applyState(decision.state);
    this.options.ownAvatarController.applyEmotion(decision.emotion);
    if (decision.action !== null) {
      this.options.ownAvatarController.triggerAction(decision.action);
    }
    if (typeof decision.lookX === "number" || typeof decision.lookY === "number") {
      this.options.ownAvatarController.setLook(decision.lookX ?? 0, decision.lookY ?? 0);
    }

    let voiceRouted = false;
    if (decision.replyText.trim()) {
      this.options.ownAvatarController.handleLlmOutput(decision.replyText);
    }
    if (
      this.options.config.autonomousVrchatAi.enabled &&
      this.options.config.voicevox.enabled &&
      decision.useVoice &&
      decision.replyText.trim()
    ) {
      try {
        const audio = await this.options.voicevox.synthesize({ text: decision.replyText });
        await this.options.audioOutput.route(audio, { text: decision.replyText });
        voiceRouted = true;
      } catch (error) {
        this.options.log?.error?.(
          "vrchat.ai_avatar.voicevox",
          error instanceof Error ? error.message : String(error),
        );
      }
    }

    let chatBoxSent = false;
    const chatBoxText = decision.chatBoxText ?? null;
    if (this.options.config.autonomousVrchatAi.enabled && chatBoxText) {
      const result = this.options.chatBox.send({ text: chatBoxText });
      chatBoxSent = result.success;
      if (!result.success) {
        this.options.log?.warn?.("vrchat.ai_avatar.chatbox_blocked", {
          error: result.error,
          retryAfterMs: result.retryAfterMs,
        });
      }
    }

    return { decision, voiceRouted, chatBoxSent };
  }
}
