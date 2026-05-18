import {
  DEFAULT_OWN_AVATAR_CONFIG,
  resolveOwnAvatarConfig,
  type OwnAvatarControllerConfig,
} from "../own-avatar/config.js";

export type AudioOutputMode = "speaker" | "virtual_cable" | "both";
export type ReasoningEffort = "low" | "medium" | "high" | "xhigh";

export interface AutonomousVrchatAiToggleConfig {
  enabled: boolean;
}

export interface InputHubConfig {
  maxBufferedEvents: number;
  textBox: { enabled: boolean };
  speechToText: { enabled: boolean };
  visionObservation: { enabled: boolean };
  streamComment: { enabled: boolean };
}

export interface GPT55LowOrchestratorConfig {
  model: string;
  reasoning: {
    effort: ReasoningEffort;
  };
  maxOutputTokens: number;
}

export interface VoicevoxConfig {
  enabled: boolean;
  baseUrl: string;
  speaker: number;
  timeoutMs: number;
}

export interface AudioOutputConfig {
  mode: AudioOutputMode;
  virtualCableDeviceName?: string;
  emitSpeakingEvents: boolean;
}

export interface ChatBoxConfig {
  enabled: boolean;
  maxChars: number;
  maxLines: number;
  minIntervalMs: number;
  submit: boolean;
  notify: boolean;
  typing: boolean;
}

export interface SpeechToTextConfig {
  enabled: boolean;
  suppressDuringTts: boolean;
}

export interface AutonomousVrchatAiConfig extends OwnAvatarControllerConfig {
  autonomousVrchatAi: AutonomousVrchatAiToggleConfig;
  inputHub: InputHubConfig;
  orchestrator: GPT55LowOrchestratorConfig;
  voicevox: VoicevoxConfig;
  audioOutput: AudioOutputConfig;
  chatBox: ChatBoxConfig;
  speechToText: SpeechToTextConfig;
}

export const DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG: AutonomousVrchatAiConfig = {
  ...DEFAULT_OWN_AVATAR_CONFIG,
  autonomousVrchatAi: {
    enabled: false,
  },
  inputHub: {
    maxBufferedEvents: 64,
    textBox: { enabled: true },
    speechToText: { enabled: false },
    visionObservation: { enabled: true },
    streamComment: { enabled: true },
  },
  orchestrator: {
    model: "gpt-5.5",
    reasoning: {
      effort: "low",
    },
    maxOutputTokens: 700,
  },
  voicevox: {
    enabled: true,
    baseUrl: "http://127.0.0.1:50021",
    speaker: 8,
    timeoutMs: 30_000,
  },
  audioOutput: {
    mode: "speaker",
    emitSpeakingEvents: true,
  },
  chatBox: {
    enabled: false,
    maxChars: 144,
    maxLines: 9,
    minIntervalMs: 3_000,
    submit: true,
    notify: false,
    typing: true,
  },
  speechToText: {
    enabled: false,
    suppressDuringTts: true,
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

function readAudioOutputMode(
  record: Record<string, unknown>,
  key: string,
  fallback: AudioOutputMode,
): AudioOutputMode {
  const value = record[key];
  return value === "speaker" || value === "virtual_cable" || value === "both" ? value : fallback;
}

function readReasoningEffort(
  record: Record<string, unknown>,
  key: string,
  fallback: ReasoningEffort,
): ReasoningEffort {
  const value = record[key];
  return value === "low" || value === "medium" || value === "high" || value === "xhigh"
    ? value
    : fallback;
}

export function resolveAutonomousVrchatAiConfig(rawConfig: unknown): AutonomousVrchatAiConfig {
  const root = isRecord(rawConfig) ? rawConfig : {};
  const defaults = DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG;
  const ownAvatarConfig = resolveOwnAvatarConfig(root);
  const autonomousVrchatAi = isRecord(root.autonomousVrchatAi) ? root.autonomousVrchatAi : {};
  const inputHub = isRecord(root.inputHub) ? root.inputHub : {};
  const inputTextBox = isRecord(inputHub.textBox) ? inputHub.textBox : {};
  const inputSpeechToText = isRecord(inputHub.speechToText) ? inputHub.speechToText : {};
  const inputVision = isRecord(inputHub.visionObservation) ? inputHub.visionObservation : {};
  const inputStreamComment = isRecord(inputHub.streamComment) ? inputHub.streamComment : {};
  const orchestrator = isRecord(root.orchestrator) ? root.orchestrator : {};
  const reasoning = isRecord(orchestrator.reasoning) ? orchestrator.reasoning : {};
  const voicevox = isRecord(root.voicevox) ? root.voicevox : {};
  const audioOutput = isRecord(root.audioOutput) ? root.audioOutput : {};
  const chatBox = isRecord(root.chatBox) ? root.chatBox : {};
  const speechToText = isRecord(root.speechToText) ? root.speechToText : {};

  return {
    ...ownAvatarConfig,
    autonomousVrchatAi: {
      enabled: readBoolean(autonomousVrchatAi, "enabled", defaults.autonomousVrchatAi.enabled),
    },
    inputHub: {
      maxBufferedEvents: readNumber(
        inputHub,
        "maxBufferedEvents",
        defaults.inputHub.maxBufferedEvents,
        { min: 1, max: 1_000 },
      ),
      textBox: {
        enabled: readBoolean(inputTextBox, "enabled", defaults.inputHub.textBox.enabled),
      },
      speechToText: {
        enabled: readBoolean(inputSpeechToText, "enabled", defaults.inputHub.speechToText.enabled),
      },
      visionObservation: {
        enabled: readBoolean(inputVision, "enabled", defaults.inputHub.visionObservation.enabled),
      },
      streamComment: {
        enabled: readBoolean(
          inputStreamComment,
          "enabled",
          defaults.inputHub.streamComment.enabled,
        ),
      },
    },
    orchestrator: {
      model: readString(orchestrator, "model", defaults.orchestrator.model),
      reasoning: {
        effort: readReasoningEffort(reasoning, "effort", defaults.orchestrator.reasoning.effort),
      },
      maxOutputTokens: readNumber(
        orchestrator,
        "maxOutputTokens",
        defaults.orchestrator.maxOutputTokens,
        { min: 1, max: 10_000 },
      ),
    },
    voicevox: {
      enabled: readBoolean(voicevox, "enabled", defaults.voicevox.enabled),
      baseUrl: readString(voicevox, "baseUrl", defaults.voicevox.baseUrl),
      speaker: readNumber(voicevox, "speaker", defaults.voicevox.speaker, { min: 0 }),
      timeoutMs: readNumber(voicevox, "timeoutMs", defaults.voicevox.timeoutMs, { min: 1_000 }),
    },
    audioOutput: {
      mode: readAudioOutputMode(audioOutput, "mode", defaults.audioOutput.mode),
      virtualCableDeviceName: readOptionalString(audioOutput, "virtualCableDeviceName"),
      emitSpeakingEvents: readBoolean(
        audioOutput,
        "emitSpeakingEvents",
        defaults.audioOutput.emitSpeakingEvents,
      ),
    },
    chatBox: {
      enabled: readBoolean(chatBox, "enabled", defaults.chatBox.enabled),
      maxChars: readNumber(chatBox, "maxChars", defaults.chatBox.maxChars, {
        min: 1,
        max: 144,
      }),
      maxLines: readNumber(chatBox, "maxLines", defaults.chatBox.maxLines, { min: 1, max: 9 }),
      minIntervalMs: readNumber(chatBox, "minIntervalMs", defaults.chatBox.minIntervalMs, {
        min: 0,
      }),
      submit: readBoolean(chatBox, "submit", defaults.chatBox.submit),
      notify: readBoolean(chatBox, "notify", defaults.chatBox.notify),
      typing: readBoolean(chatBox, "typing", defaults.chatBox.typing),
    },
    speechToText: {
      enabled: readBoolean(speechToText, "enabled", defaults.speechToText.enabled),
      suppressDuringTts: readBoolean(
        speechToText,
        "suppressDuringTts",
        defaults.speechToText.suppressDuringTts,
      ),
    },
  };
}
