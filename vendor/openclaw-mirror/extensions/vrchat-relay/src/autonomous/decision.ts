import type { OwnAvatarEmotion, OwnAvatarState } from "../own-avatar/config.js";
import { OC_ACTION_BY_NAME, type OwnAvatarActionName } from "../own-avatar/parameter-mapper.js";

export const AGENT_DECISION_STATES = [
  "idle",
  "listening",
  "thinking",
  "speaking",
  "tool_running",
  "reacting",
  "sleeping",
  "error",
] as const satisfies readonly OwnAvatarState[];

export const AGENT_DECISION_EMOTIONS = [
  "neutral",
  "happy",
  "sad",
  "angry",
  "surprised",
  "confused",
  "relaxed",
] as const satisfies readonly OwnAvatarEmotion[];

export interface AgentDecision {
  schemaVersion: 1;
  replyText: string;
  state: OwnAvatarState;
  emotion: OwnAvatarEmotion;
  action: OwnAvatarActionName | number | null;
  useVoice: boolean;
  emergencyStop: boolean;
  lookX?: number;
  lookY?: number;
  chatBoxText?: string | null;
}

export interface AgentDecisionValidationResult {
  ok: boolean;
  decision?: AgentDecision;
  errors: string[];
}

const STATE_SET = new Set<string>(AGENT_DECISION_STATES);
const EMOTION_SET = new Set<string>(AGENT_DECISION_EMOTIONS);
const ACTION_NAME_SET = new Set<string>(Object.keys(OC_ACTION_BY_NAME));
const ACTION_ID_SET = new Set<number>(Object.values(OC_ACTION_BY_NAME));

export const AGENT_DECISION_JSON_SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: [
    "schemaVersion",
    "replyText",
    "state",
    "emotion",
    "action",
    "useVoice",
    "emergencyStop",
  ],
  properties: {
    schemaVersion: { const: 1 },
    replyText: { type: "string", maxLength: 800 },
    state: { type: "string", enum: AGENT_DECISION_STATES },
    emotion: { type: "string", enum: AGENT_DECISION_EMOTIONS },
    action: {
      anyOf: [
        { type: "string", enum: Object.keys(OC_ACTION_BY_NAME) },
        { type: "integer", minimum: 0, maximum: 9 },
        { type: "null" },
      ],
    },
    useVoice: { type: "boolean" },
    emergencyStop: { type: "boolean" },
    lookX: { type: "number", minimum: -1, maximum: 1 },
    lookY: { type: "number", minimum: -1, maximum: 1 },
    chatBoxText: { anyOf: [{ type: "string", maxLength: 144 }, { type: "null" }] },
  },
} as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function validateLookAxis(value: unknown, key: string, errors: string[]): number | undefined {
  if (value === undefined) {
    return undefined;
  }
  if (!isFiniteNumber(value) || value < -1 || value > 1) {
    errors.push(`${key} must be a finite number from -1 to 1`);
    return undefined;
  }
  return value;
}

function validateAction(value: unknown, errors: string[]): AgentDecision["action"] {
  if (value === null) {
    return null;
  }
  if (typeof value === "string") {
    if (!ACTION_NAME_SET.has(value)) {
      errors.push(`action must be one of ${[...ACTION_NAME_SET].join(", ")}`);
      return null;
    }
    return value as OwnAvatarActionName;
  }
  if (typeof value === "number" && Number.isInteger(value)) {
    if (!ACTION_ID_SET.has(value)) {
      errors.push("action id must be in the configured allowlist");
      return null;
    }
    return value;
  }
  errors.push("action must be a known action name, allowed integer id, or null");
  return null;
}

export function parseAgentDecisionJson(content: string): AgentDecisionValidationResult {
  try {
    return validateAgentDecision(JSON.parse(content));
  } catch (error) {
    return {
      ok: false,
      errors: [error instanceof Error ? error.message : "invalid JSON"],
    };
  }
}

export function validateAgentDecision(value: unknown): AgentDecisionValidationResult {
  const errors: string[] = [];
  if (!isRecord(value)) {
    return { ok: false, errors: ["decision must be an object"] };
  }

  if (value.schemaVersion !== 1) {
    errors.push("schemaVersion must be 1");
  }
  if (typeof value.replyText !== "string") {
    errors.push("replyText must be a string");
  }
  if (typeof value.state !== "string" || !STATE_SET.has(value.state)) {
    errors.push(`state must be one of ${AGENT_DECISION_STATES.join(", ")}`);
  }
  if (typeof value.emotion !== "string" || !EMOTION_SET.has(value.emotion)) {
    errors.push(`emotion must be one of ${AGENT_DECISION_EMOTIONS.join(", ")}`);
  }
  if (typeof value.useVoice !== "boolean") {
    errors.push("useVoice must be a boolean");
  }
  if (typeof value.emergencyStop !== "boolean") {
    errors.push("emergencyStop must be a boolean");
  }

  const action = validateAction(value.action, errors);
  const lookX = validateLookAxis(value.lookX, "lookX", errors);
  const lookY = validateLookAxis(value.lookY, "lookY", errors);

  if (
    value.chatBoxText !== undefined &&
    value.chatBoxText !== null &&
    typeof value.chatBoxText !== "string"
  ) {
    errors.push("chatBoxText must be a string or null");
  }

  if (errors.length > 0) {
    return { ok: false, errors };
  }

  return {
    ok: true,
    errors: [],
    decision: {
      schemaVersion: 1,
      replyText: value.replyText as string,
      state: value.state as OwnAvatarState,
      emotion: value.emotion as OwnAvatarEmotion,
      action,
      useVoice: value.useVoice as boolean,
      emergencyStop: value.emergencyStop as boolean,
      ...(lookX !== undefined ? { lookX } : {}),
      ...(lookY !== undefined ? { lookY } : {}),
      ...(value.chatBoxText !== undefined
        ? { chatBoxText: value.chatBoxText as string | null }
        : {}),
    },
  };
}
