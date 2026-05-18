import type { OwnAvatarBehaviorConfig, OwnAvatarEmotion, OwnAvatarState } from "./config.js";
import type { OwnAvatarActionName } from "./parameter-mapper.js";

export interface BehaviorPlannerDecision {
  action?: OwnAvatarActionName;
  reason: string;
}

export interface BehaviorPlannerInput {
  state: OwnAvatarState;
  emotion: OwnAvatarEmotion;
  nowMs: number;
  manualLock: boolean;
  autoEnabled: boolean;
}

export class BehaviorPlanner {
  private lastActionAt = 0;
  private nextIdleAt = 0;

  constructor(
    private readonly config: OwnAvatarBehaviorConfig,
    private readonly random: () => number = Math.random,
  ) {
    this.scheduleNextIdle(Date.now());
  }

  plan(input: BehaviorPlannerInput): BehaviorPlannerDecision {
    if (this.config.mode === "off") {
      return { reason: "disabled" };
    }
    if (!input.autoEnabled) {
      return { reason: "auto-disabled" };
    }
    if (input.manualLock) {
      return { reason: "manual-lock" };
    }
    if (input.nowMs - this.lastActionAt < this.config.actionCooldownMs) {
      return { reason: "cooldown" };
    }

    const action = this.actionForState(input.state, input.emotion, input.nowMs);
    if (!action) {
      return { reason: "no-action" };
    }

    this.lastActionAt = input.nowMs;
    if (input.state === "idle") {
      this.scheduleNextIdle(input.nowMs);
    }
    return { action, reason: `state:${input.state}` };
  }

  private actionForState(
    state: OwnAvatarState,
    emotion: OwnAvatarEmotion,
    nowMs: number,
  ): OwnAvatarActionName | undefined {
    if (state === "listening") {
      return "small_nod";
    }
    if (state === "thinking") {
      return "think_pose";
    }
    if (state === "tool_running") {
      return "working";
    }
    if (state === "reacting") {
      return emotion === "surprised" ? "surprised" : "tilt_head";
    }
    if (state === "speaking") {
      return emotion === "happy" ? "laugh_small" : "small_nod";
    }
    if (state === "error") {
      return "reset_pose";
    }
    if (state !== "idle" || nowMs < this.nextIdleAt) {
      return undefined;
    }
    return this.random() < 0.7 ? "small_nod" : "stretch";
  }

  private scheduleNextIdle(nowMs: number): void {
    const min = Math.max(1_000, this.config.idleMinIntervalMs);
    const max = Math.max(min, this.config.idleMaxIntervalMs);
    this.nextIdleAt = nowMs + min + Math.floor(this.random() * (max - min + 1));
  }
}
