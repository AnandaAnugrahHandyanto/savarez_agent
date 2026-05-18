import type { OwnAvatarControllerConfig } from "./config.js";
import type { VRChatAvatarRegistry } from "./registry.js";

export interface SafetyDecision {
  allowed: boolean;
  reason?: string;
}

export interface OwnAvatarRateLimiterOptions {
  maxCommandsPerSecond: number;
  nowMs?: () => number;
}

export class OwnAvatarRateLimiter {
  private readonly timestamps: number[] = [];
  private readonly nowMs: () => number;

  constructor(private readonly options: OwnAvatarRateLimiterOptions) {
    this.nowMs = options.nowMs ?? Date.now;
  }

  allow(): SafetyDecision {
    const now = this.nowMs();
    const cutoff = now - 1_000;
    while (this.timestamps.length > 0 && this.timestamps[0] <= cutoff) {
      this.timestamps.shift();
    }
    if (this.timestamps.length >= this.options.maxCommandsPerSecond) {
      return { allowed: false, reason: "rate-limited" };
    }
    this.timestamps.push(now);
    return { allowed: true };
  }

  reset(): void {
    this.timestamps.length = 0;
  }
}

export interface ValidateParameterOptions {
  bypassManualLock?: boolean;
  bypassRateLimit?: boolean;
}

export class VRChatSafetyGate {
  private manualLock = false;
  private readonly rateLimiter: OwnAvatarRateLimiter;

  constructor(
    private readonly config: OwnAvatarControllerConfig,
    private readonly registry: VRChatAvatarRegistry,
    nowMs?: () => number,
  ) {
    this.rateLimiter = new OwnAvatarRateLimiter({
      maxCommandsPerSecond: config.behavior.maxCommandsPerSecond,
      nowMs,
    });
  }

  setManualLock(locked: boolean): void {
    this.manualLock = locked;
  }

  isManualLocked(): boolean {
    return this.manualLock;
  }

  validateOscHost(): SafetyDecision {
    if (this.config.vrchatOsc.allowRemoteOsc) {
      return { allowed: true };
    }
    const host = this.config.vrchatOsc.host;
    if (host === "127.0.0.1" || host === "localhost" || host === "::1") {
      return { allowed: true };
    }
    return { allowed: false, reason: "remote-osc-disabled" };
  }

  validateParameter(name: string, options: ValidateParameterOptions = {}): SafetyDecision {
    const hostDecision = this.validateOscHost();
    if (!hostDecision.allowed) {
      return hostDecision;
    }
    if (this.manualLock && !options.bypassManualLock) {
      return { allowed: false, reason: "manual-lock" };
    }
    if (!name.startsWith(this.config.avatarControl.requiredPrefix)) {
      return { allowed: false, reason: "invalid-prefix" };
    }
    if (
      this.config.safety.requireOscJsonParameterPresence &&
      !this.registry.hasWritableParameter(name)
    ) {
      return { allowed: false, reason: "parameter-not-registered" };
    }
    if (!options.bypassRateLimit) {
      return this.rateLimiter.allow();
    }
    return { allowed: true };
  }

  resetRateLimit(): void {
    this.rateLimiter.reset();
  }
}
