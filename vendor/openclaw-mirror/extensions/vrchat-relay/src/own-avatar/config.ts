export type OwnAvatarState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "tool_running"
  | "reacting"
  | "sleeping"
  | "error";

export type OwnAvatarEmotion =
  | "neutral"
  | "happy"
  | "sad"
  | "angry"
  | "surprised"
  | "confused"
  | "relaxed";

export interface OwnAvatarOscConfig {
  enabled: boolean;
  host: string;
  sendPort: number;
  receivePort: number;
  allowRemoteOsc: boolean;
  autoDiscoverAvatarConfig: boolean;
  oscJsonRoot?: string;
}

export interface AvatarControlConfig {
  requiredPrefix: string;
  manualLockParam: string;
  autoEnabledParam: string;
  stateParam: string;
  emotionParam: string;
  actionParam: string;
  actionPulseParam: string;
  lookXParam: string;
  lookYParam: string;
  resetParam: string;
  autoEnabledOnStart: boolean;
}

export interface OwnAvatarBehaviorConfig {
  mode: "subtle" | "off";
  idleMinIntervalMs: number;
  idleMaxIntervalMs: number;
  actionCooldownMs: number;
  emotionCooldownMs: number;
  maxCommandsPerSecond: number;
  speakingHoldMs: number;
}

export interface OwnAvatarMovementConfig {
  enabled: boolean;
  allowInPublicInstances: boolean;
  maxInputDurationMs: number;
  alwaysResetToZero: boolean;
}

export interface OwnAvatarSafetyConfig {
  requireOscJsonParameterPresence: boolean;
  disableChatBoxByDefault: boolean;
  emergencyStopHotkey: string;
}

export interface OwnAvatarControllerConfig {
  vrchatOsc: OwnAvatarOscConfig;
  avatarControl: AvatarControlConfig;
  behavior: OwnAvatarBehaviorConfig;
  movement: OwnAvatarMovementConfig;
  safety: OwnAvatarSafetyConfig;
}

export const DEFAULT_OWN_AVATAR_REQUIRED_PARAMS = [
  "OC_AutoEnabled",
  "OC_State",
  "OC_Emotion",
  "OC_Action",
  "OC_ActionPulse",
  "OC_LookX",
  "OC_LookY",
  "OC_Reset",
  "OC_ManualLock",
] as const;

export const DEFAULT_OWN_AVATAR_CONFIG: OwnAvatarControllerConfig = {
  vrchatOsc: {
    enabled: true,
    host: "127.0.0.1",
    sendPort: 9000,
    receivePort: 9001,
    allowRemoteOsc: false,
    autoDiscoverAvatarConfig: true,
  },
  avatarControl: {
    requiredPrefix: "OC_",
    manualLockParam: "OC_ManualLock",
    autoEnabledParam: "OC_AutoEnabled",
    stateParam: "OC_State",
    emotionParam: "OC_Emotion",
    actionParam: "OC_Action",
    actionPulseParam: "OC_ActionPulse",
    lookXParam: "OC_LookX",
    lookYParam: "OC_LookY",
    resetParam: "OC_Reset",
    autoEnabledOnStart: false,
  },
  behavior: {
    mode: "subtle",
    idleMinIntervalMs: 30_000,
    idleMaxIntervalMs: 90_000,
    actionCooldownMs: 15_000,
    emotionCooldownMs: 3_000,
    maxCommandsPerSecond: 6,
    speakingHoldMs: 2_500,
  },
  movement: {
    enabled: false,
    allowInPublicInstances: false,
    maxInputDurationMs: 1_000,
    alwaysResetToZero: true,
  },
  safety: {
    requireOscJsonParameterPresence: true,
    disableChatBoxByDefault: true,
    emergencyStopHotkey: "Ctrl+Alt+O",
  },
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readString(record: Record<string, unknown>, key: string, fallback: string): string {
  const value = record[key];
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function readOptionalString(record: Record<string, unknown>, key: string): string | undefined {
  const value = record[key];
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function readBoolean(record: Record<string, unknown>, key: string, fallback: boolean): boolean {
  const value = record[key];
  return typeof value === "boolean" ? value : fallback;
}

function readNumber(
  record: Record<string, unknown>,
  key: string,
  fallback: number,
  limits?: { min?: number; max?: number },
): number {
  const value = record[key];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return fallback;
  }
  const min = limits?.min;
  const max = limits?.max;
  if (typeof min === "number" && value < min) {
    return fallback;
  }
  if (typeof max === "number" && value > max) {
    return fallback;
  }
  return value;
}

export function resolveOwnAvatarConfig(rawConfig: unknown): OwnAvatarControllerConfig {
  const root = isRecord(rawConfig) ? rawConfig : {};
  const vrchatOsc = isRecord(root.vrchatOsc) ? root.vrchatOsc : {};
  const legacyOsc = isRecord(root.osc) ? root.osc : {};
  const avatarControl = isRecord(root.avatarControl) ? root.avatarControl : {};
  const behavior = isRecord(root.behavior) ? root.behavior : {};
  const movement = isRecord(root.movement) ? root.movement : {};
  const safety = isRecord(root.safety) ? root.safety : {};
  const defaults = DEFAULT_OWN_AVATAR_CONFIG;

  const mode = behavior.mode === "off" ? "off" : defaults.behavior.mode;

  return {
    vrchatOsc: {
      enabled: readBoolean(vrchatOsc, "enabled", defaults.vrchatOsc.enabled),
      host: readString(vrchatOsc, "host", readString(legacyOsc, "host", defaults.vrchatOsc.host)),
      sendPort: readNumber(
        vrchatOsc,
        "sendPort",
        readNumber(legacyOsc, "outgoingPort", defaults.vrchatOsc.sendPort, {
          min: 1,
          max: 65_535,
        }),
        { min: 1, max: 65_535 },
      ),
      receivePort: readNumber(
        vrchatOsc,
        "receivePort",
        readNumber(legacyOsc, "incomingPort", defaults.vrchatOsc.receivePort, {
          min: 1,
          max: 65_535,
        }),
        { min: 1, max: 65_535 },
      ),
      allowRemoteOsc: readBoolean(vrchatOsc, "allowRemoteOsc", defaults.vrchatOsc.allowRemoteOsc),
      autoDiscoverAvatarConfig: readBoolean(
        vrchatOsc,
        "autoDiscoverAvatarConfig",
        defaults.vrchatOsc.autoDiscoverAvatarConfig,
      ),
      oscJsonRoot: readOptionalString(vrchatOsc, "oscJsonRoot"),
    },
    avatarControl: {
      requiredPrefix: readString(
        avatarControl,
        "requiredPrefix",
        defaults.avatarControl.requiredPrefix,
      ),
      manualLockParam: readString(
        avatarControl,
        "manualLockParam",
        defaults.avatarControl.manualLockParam,
      ),
      autoEnabledParam: readString(
        avatarControl,
        "autoEnabledParam",
        defaults.avatarControl.autoEnabledParam,
      ),
      stateParam: readString(avatarControl, "stateParam", defaults.avatarControl.stateParam),
      emotionParam: readString(avatarControl, "emotionParam", defaults.avatarControl.emotionParam),
      actionParam: readString(avatarControl, "actionParam", defaults.avatarControl.actionParam),
      actionPulseParam: readString(
        avatarControl,
        "actionPulseParam",
        defaults.avatarControl.actionPulseParam,
      ),
      lookXParam: readString(avatarControl, "lookXParam", defaults.avatarControl.lookXParam),
      lookYParam: readString(avatarControl, "lookYParam", defaults.avatarControl.lookYParam),
      resetParam: readString(avatarControl, "resetParam", defaults.avatarControl.resetParam),
      autoEnabledOnStart: readBoolean(
        avatarControl,
        "autoEnabledOnStart",
        defaults.avatarControl.autoEnabledOnStart,
      ),
    },
    behavior: {
      mode,
      idleMinIntervalMs: readNumber(
        behavior,
        "idleMinIntervalMs",
        defaults.behavior.idleMinIntervalMs,
        { min: 1_000 },
      ),
      idleMaxIntervalMs: readNumber(
        behavior,
        "idleMaxIntervalMs",
        defaults.behavior.idleMaxIntervalMs,
        { min: 1_000 },
      ),
      actionCooldownMs: readNumber(
        behavior,
        "actionCooldownMs",
        defaults.behavior.actionCooldownMs,
        { min: 0 },
      ),
      emotionCooldownMs: readNumber(
        behavior,
        "emotionCooldownMs",
        defaults.behavior.emotionCooldownMs,
        { min: 0 },
      ),
      maxCommandsPerSecond: readNumber(
        behavior,
        "maxCommandsPerSecond",
        defaults.behavior.maxCommandsPerSecond,
        { min: 1 },
      ),
      speakingHoldMs: readNumber(behavior, "speakingHoldMs", defaults.behavior.speakingHoldMs, {
        min: 0,
      }),
    },
    movement: {
      enabled: readBoolean(movement, "enabled", defaults.movement.enabled),
      allowInPublicInstances: readBoolean(
        movement,
        "allowInPublicInstances",
        defaults.movement.allowInPublicInstances,
      ),
      maxInputDurationMs: readNumber(
        movement,
        "maxInputDurationMs",
        defaults.movement.maxInputDurationMs,
        { min: 1, max: 10_000 },
      ),
      alwaysResetToZero: readBoolean(
        movement,
        "alwaysResetToZero",
        defaults.movement.alwaysResetToZero,
      ),
    },
    safety: {
      requireOscJsonParameterPresence: readBoolean(
        safety,
        "requireOscJsonParameterPresence",
        defaults.safety.requireOscJsonParameterPresence,
      ),
      disableChatBoxByDefault: readBoolean(
        safety,
        "disableChatBoxByDefault",
        defaults.safety.disableChatBoxByDefault,
      ),
      emergencyStopHotkey: readString(
        safety,
        "emergencyStopHotkey",
        defaults.safety.emergencyStopHotkey,
      ),
    },
  };
}
