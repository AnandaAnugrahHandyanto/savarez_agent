import type { OSCMessage } from "../osc/types.js";
import { BehaviorPlanner } from "./behavior-planner.js";
import type { OwnAvatarControllerConfig, OwnAvatarEmotion, OwnAvatarState } from "./config.js";
import { DEFAULT_OWN_AVATAR_CONFIG } from "./config.js";
import type { OwnAvatarOscSender } from "./osc.js";
import {
  inferEmotionFromText,
  mapEmotionToOcEmotion,
  mapOpenClawStateToOcState,
  resolveActionId,
  type OwnAvatarActionName,
} from "./parameter-mapper.js";
import type { VRChatAvatarRegistrySnapshot } from "./registry.js";
import { VRChatAvatarRegistry } from "./registry.js";
import { VRChatSafetyGate } from "./safety-gate.js";

export interface OwnAvatarControllerStatus {
  enabled: boolean;
  currentState: OwnAvatarState;
  currentEmotion: OwnAvatarEmotion;
  currentAvatarId: string | null;
  supported: boolean;
  missingRequiredParameters: string[];
  manualLock: boolean;
  lastActionId: number;
  lastActionPulse: boolean;
}

export interface VRChatOwnAvatarControllerOptions {
  config?: OwnAvatarControllerConfig;
  sender: OwnAvatarOscSender;
  registry?: VRChatAvatarRegistry;
  nowMs?: () => number;
  setTimeoutFn?: typeof setTimeout;
  clearTimeoutFn?: typeof clearTimeout;
  random?: () => number;
  log?: {
    info?: (operation: string, details?: Record<string, unknown>) => void;
    warn?: (operation: string, details?: Record<string, unknown>) => void;
    error?: (operation: string, error: string, details?: Record<string, unknown>) => void;
    skip?: (operation: string, reason: string, details?: Record<string, unknown>) => void;
  };
}

type TimerHandle = ReturnType<typeof setTimeout>;

export class VRChatOwnAvatarController {
  private readonly config: OwnAvatarControllerConfig;
  private readonly registry: VRChatAvatarRegistry;
  private readonly safetyGate: VRChatSafetyGate;
  private readonly planner: BehaviorPlanner;
  private readonly nowMs: () => number;
  private readonly random: () => number;
  private readonly setTimeoutFn: typeof setTimeout;
  private readonly clearTimeoutFn: typeof clearTimeout;
  private readonly log: NonNullable<VRChatOwnAvatarControllerOptions["log"]>;
  private idleTimer: TimerHandle | null = null;
  private speakingTimer: TimerHandle | null = null;
  private enabled = false;
  private currentState: OwnAvatarState = "idle";
  private currentEmotion: OwnAvatarEmotion = "neutral";
  private currentAvatarId: string | null = null;
  private lastActionId = 0;
  private actionPulse = false;
  private lastEmotionAt = Number.NEGATIVE_INFINITY;

  constructor(private readonly options: VRChatOwnAvatarControllerOptions) {
    this.config = options.config ?? DEFAULT_OWN_AVATAR_CONFIG;
    this.registry =
      options.registry ??
      new VRChatAvatarRegistry({
        oscJsonRoot: this.config.vrchatOsc.oscJsonRoot,
      });
    this.nowMs = options.nowMs ?? Date.now;
    this.random = options.random ?? Math.random;
    this.safetyGate = new VRChatSafetyGate(this.config, this.registry, this.nowMs);
    this.planner = new BehaviorPlanner(this.config.behavior, this.random);
    this.setTimeoutFn = options.setTimeoutFn ?? setTimeout;
    this.clearTimeoutFn = options.clearTimeoutFn ?? clearTimeout;
    this.log = options.log ?? {};
  }

  getStatus(): OwnAvatarControllerStatus {
    const current = this.registry.getCurrent();
    return {
      enabled: this.enabled,
      currentState: this.currentState,
      currentEmotion: this.currentEmotion,
      currentAvatarId: this.currentAvatarId,
      supported: current?.supported ?? false,
      missingRequiredParameters: current?.missingRequiredParameters ?? [],
      manualLock: this.safetyGate.isManualLocked(),
      lastActionId: this.lastActionId,
      lastActionPulse: this.actionPulse,
    };
  }

  async handleAvatarChange(avatarId: string): Promise<VRChatAvatarRegistrySnapshot> {
    this.currentAvatarId = avatarId;
    const snapshot = await this.registry.loadAvatar(avatarId);
    if (snapshot.supported) {
      this.log.info?.("vrchat.own_avatar.ready", {
        avatarId,
        parameters: snapshot.parameters.length,
        sourcePath: snapshot.sourcePath,
      });
    } else {
      this.log.warn?.("vrchat.own_avatar.unsupported_avatar", {
        avatarId,
        missingRequiredParameters: snapshot.missingRequiredParameters,
      });
    }
    return snapshot;
  }

  handleOscMessage(message: OSCMessage): void {
    if (message.address === "/avatar/change") {
      const avatarId = message.args.find((value): value is string => typeof value === "string");
      if (avatarId) {
        void this.handleAvatarChange(avatarId).catch((error) => {
          this.log.error?.(
            "vrchat.own_avatar.avatar_change",
            error instanceof Error ? error.message : String(error),
            { avatarId },
          );
        });
      }
      return;
    }

    const manualLockAddress = `/avatar/parameters/${this.config.avatarControl.manualLockParam}`;
    if (message.address === manualLockAddress) {
      const locked = message.args.find((value): value is boolean => typeof value === "boolean");
      if (typeof locked === "boolean") {
        this.safetyGate.setManualLock(locked);
        this.log.info?.("vrchat.own_avatar.manual_lock", { locked });
      }
    }
  }

  setAutoEnabled(enabled: boolean): boolean {
    this.enabled = enabled;
    if (enabled) {
      const sent = this.sendParameter(this.config.avatarControl.autoEnabledParam, true, {
        bypassManualLock: true,
      });
      this.scheduleIdleLoop();
      return sent;
    }

    this.stopIdleLoop();
    this.clearSpeakingTimer();
    this.currentState = "idle";
    this.currentEmotion = "neutral";
    this.lastActionId = 0;
    const resetAction = this.sendParameter(this.config.avatarControl.actionParam, 0, {
      bypassManualLock: true,
      bypassRateLimit: true,
    });
    const resetState = this.sendParameter(this.config.avatarControl.stateParam, 0, {
      bypassManualLock: true,
      bypassRateLimit: true,
    });
    const resetEmotion = this.sendParameter(this.config.avatarControl.emotionParam, 0, {
      bypassManualLock: true,
      bypassRateLimit: true,
    });
    const sent = this.sendParameter(this.config.avatarControl.autoEnabledParam, false, {
      bypassManualLock: true,
      bypassRateLimit: true,
    });
    return resetAction && resetState && resetEmotion && sent;
  }

  applyState(state: OwnAvatarState): boolean {
    this.currentState = state;
    const sent = this.sendParameter(
      this.config.avatarControl.stateParam,
      mapOpenClawStateToOcState(state),
    );
    this.planContextAction();
    return sent;
  }

  applyEmotion(emotion: OwnAvatarEmotion, options: { bypassCooldown?: boolean } = {}): boolean {
    if (
      !options.bypassCooldown &&
      emotion !== "neutral" &&
      this.nowMs() - this.lastEmotionAt < this.config.behavior.emotionCooldownMs
    ) {
      this.log.skip?.("vrchat.own_avatar.emotion", "cooldown", { emotion });
      return false;
    }
    this.currentEmotion = emotion;
    const sent = this.sendParameter(
      this.config.avatarControl.emotionParam,
      mapEmotionToOcEmotion(emotion),
    );
    if (sent && emotion !== "neutral") {
      this.lastEmotionAt = this.nowMs();
    }
    return sent;
  }

  triggerAction(action: OwnAvatarActionName | number): boolean {
    const actionId = resolveActionId(action);
    if (actionId === null) {
      this.log.skip?.("vrchat.own_avatar.action", "action-not-allowed", { action });
      return false;
    }
    this.lastActionId = actionId;
    const actionSent = this.sendParameter(this.config.avatarControl.actionParam, actionId);
    this.actionPulse = !this.actionPulse;
    const pulseSent = this.sendParameter(
      this.config.avatarControl.actionPulseParam,
      this.actionPulse,
    );
    return actionSent && pulseSent;
  }

  handleLlmInput(): void {
    if (!this.enabled) {
      return;
    }
    this.applyState("thinking");
  }

  handleLlmOutput(text: string): void {
    if (!this.enabled || !text.trim()) {
      return;
    }
    this.applyState("speaking");
    this.applyEmotion(inferEmotionFromText(text));
    this.scheduleReturnToIdle();
  }

  handleToolStart(): void {
    if (!this.enabled) {
      return;
    }
    this.applyState("tool_running");
  }

  handleToolEnd(): void {
    if (!this.enabled || this.currentState !== "tool_running") {
      return;
    }
    this.applyState("idle");
  }

  setLook(x: number, y: number): boolean {
    const lookX = Math.max(-1, Math.min(1, x));
    const lookY = Math.max(-1, Math.min(1, y));
    const sentX = this.sendParameter(this.config.avatarControl.lookXParam, lookX);
    const sentY = this.sendParameter(this.config.avatarControl.lookYParam, lookY);
    return sentX && sentY;
  }

  emergencyStop(): void {
    this.enabled = false;
    this.stopIdleLoop();
    this.clearSpeakingTimer();
    this.currentState = "idle";
    this.currentEmotion = "neutral";
    this.lastActionId = 0;
    this.sendParameter(this.config.avatarControl.resetParam, true, {
      bypassManualLock: true,
      bypassRateLimit: true,
    });
    this.sendParameter(this.config.avatarControl.actionParam, 0, {
      bypassManualLock: true,
      bypassRateLimit: true,
    });
    this.sendParameter(this.config.avatarControl.stateParam, 0, {
      bypassManualLock: true,
      bypassRateLimit: true,
    });
    this.sendParameter(this.config.avatarControl.emotionParam, 0, {
      bypassManualLock: true,
      bypassRateLimit: true,
    });
    this.sendParameter(this.config.avatarControl.autoEnabledParam, false, {
      bypassManualLock: true,
      bypassRateLimit: true,
    });
  }

  private planContextAction(): void {
    const decision = this.planner.plan({
      state: this.currentState,
      emotion: this.currentEmotion,
      nowMs: this.nowMs(),
      manualLock: this.safetyGate.isManualLocked(),
      autoEnabled: this.enabled,
    });
    if (decision.action) {
      this.triggerAction(decision.action);
    }
  }

  private sendParameter(
    name: string,
    value: boolean | number,
    options: { bypassManualLock?: boolean; bypassRateLimit?: boolean } = {},
  ): boolean {
    if (!this.config.vrchatOsc.enabled) {
      this.log.skip?.("vrchat.own_avatar.parameter", "osc-disabled", { name });
      return false;
    }
    const decision = this.safetyGate.validateParameter(name, options);
    if (!decision.allowed) {
      this.log.skip?.("vrchat.own_avatar.parameter", decision.reason ?? "blocked", { name });
      return false;
    }
    this.options.sender.sendAvatarParameter(name, value);
    this.log.info?.("vrchat.own_avatar.parameter", { name, value });
    return true;
  }

  private scheduleReturnToIdle(): void {
    this.clearSpeakingTimer();
    if (this.config.behavior.speakingHoldMs <= 0) {
      this.applyState("idle");
      this.applyEmotion("neutral", { bypassCooldown: true });
      return;
    }
    this.speakingTimer = this.setTimeoutFn(() => {
      this.speakingTimer = null;
      if (this.enabled && this.currentState === "speaking") {
        this.applyState("idle");
        this.applyEmotion("neutral", { bypassCooldown: true });
      }
    }, this.config.behavior.speakingHoldMs);
  }

  private clearSpeakingTimer(): void {
    if (this.speakingTimer) {
      this.clearTimeoutFn(this.speakingTimer);
      this.speakingTimer = null;
    }
  }

  private scheduleIdleLoop(): void {
    this.stopIdleLoop();
    if (this.config.behavior.mode === "off") {
      return;
    }
    const min = Math.max(1_000, this.config.behavior.idleMinIntervalMs);
    const max = Math.max(min, this.config.behavior.idleMaxIntervalMs);
    const delayMs = min + Math.floor(this.random() * (max - min + 1));
    this.idleTimer = this.setTimeoutFn(() => {
      this.idleTimer = null;
      if (this.enabled && this.currentState === "idle") {
        this.planContextAction();
      }
      if (this.enabled) {
        this.scheduleIdleLoop();
      }
    }, delayMs);
  }

  private stopIdleLoop(): void {
    if (this.idleTimer) {
      this.clearTimeoutFn(this.idleTimer);
      this.idleTimer = null;
    }
  }
}
