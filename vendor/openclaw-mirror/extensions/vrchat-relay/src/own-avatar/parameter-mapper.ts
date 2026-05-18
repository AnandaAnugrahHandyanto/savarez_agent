import type { OwnAvatarEmotion, OwnAvatarState } from "./config.js";

export const OC_STATE_BY_OPENCLAW_STATE: Record<OwnAvatarState, number> = {
  idle: 0,
  listening: 1,
  thinking: 2,
  speaking: 3,
  tool_running: 4,
  reacting: 5,
  sleeping: 6,
  error: 7,
};

export const OC_EMOTION_BY_NAME: Record<OwnAvatarEmotion, number> = {
  neutral: 0,
  happy: 1,
  sad: 2,
  angry: 3,
  surprised: 4,
  confused: 5,
  relaxed: 6,
};

export const OC_ACTION_BY_NAME = {
  none: 0,
  small_nod: 1,
  wave: 2,
  think_pose: 3,
  tilt_head: 4,
  laugh_small: 5,
  surprised: 6,
  working: 7,
  stretch: 8,
  reset_pose: 9,
} as const;

export type OwnAvatarActionName = keyof typeof OC_ACTION_BY_NAME;

const ACTION_ALLOWLIST = new Set<number>(Object.values(OC_ACTION_BY_NAME));

export function mapOpenClawStateToOcState(state: OwnAvatarState): number {
  return OC_STATE_BY_OPENCLAW_STATE[state];
}

export function mapEmotionToOcEmotion(emotion: OwnAvatarEmotion): number {
  return OC_EMOTION_BY_NAME[emotion];
}

export function resolveActionId(action: OwnAvatarActionName | number): number | null {
  const id = typeof action === "number" ? action : OC_ACTION_BY_NAME[action];
  return Number.isInteger(id) && ACTION_ALLOWLIST.has(id) ? id : null;
}

export function inferEmotionFromText(text: string): OwnAvatarEmotion {
  const normalized = text.toLowerCase();
  if (!normalized.trim()) {
    return "neutral";
  }
  if (/\b(happy|great|nice|love|lol|haha|thanks|thank you)\b/.test(normalized)) {
    return "happy";
  }
  if (/\b(sad|sorry|lonely|unfortunately|regret)\b/.test(normalized)) {
    return "sad";
  }
  if (/\b(angry|annoyed|frustrated|furious)\b/.test(normalized)) {
    return "angry";
  }
  if (/\b(surprise|surprised|wow|unexpected|amazing)\b/.test(normalized)) {
    return "surprised";
  }
  if (/\b(confused|maybe|unclear|not sure|hmm)\b/.test(normalized)) {
    return "confused";
  }
  if (/\b(relaxed|calm|easy|rest)\b/.test(normalized)) {
    return "relaxed";
  }
  return "neutral";
}
