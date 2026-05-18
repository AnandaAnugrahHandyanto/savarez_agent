import { describe, expect, it } from "vitest";
import { DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG, type AutonomousVrchatAiConfig } from "./config.js";
import { InputHub } from "./input-hub.js";

function makeHub(config: AutonomousVrchatAiConfig = DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG): InputHub {
  return new InputHub({
    config: config.inputHub,
    speechToText: config.speechToText,
    nowMs: () => 123,
  });
}

describe("InputHub", () => {
  it("keeps movement and ChatBox disabled while suppressing STT during TTS by default", () => {
    expect(DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.movement.enabled).toBe(false);
    expect(DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.chatBox.enabled).toBe(false);
    expect(DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.speechToText.suppressDuringTts).toBe(true);
  });

  it("integrates text, STT, vision observations, and stream comments", () => {
    const config = {
      ...DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG,
      inputHub: {
        ...DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.inputHub,
        speechToText: { enabled: true },
      },
      speechToText: {
        ...DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.speechToText,
        enabled: true,
      },
    };
    const hub = makeHub(config);

    expect(hub.pushTextBox("manual hello").accepted).toBe(true);
    expect(hub.pushSpeechToText("mic hello").accepted).toBe(true);
    expect(hub.pushVisionObservation("avatar is waving").accepted).toBe(true);
    expect(hub.pushStreamComment("nice stream").accepted).toBe(true);

    expect(hub.snapshot()).toMatchObject({
      latestText: "manual hello",
      latestSpeechToText: "mic hello",
      latestVisionObservation: "avatar is waving",
      latestStreamComment: "nice stream",
    });
  });

  it("suppresses STT echo while TTS is speaking when configured", () => {
    const config = {
      ...DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG,
      inputHub: {
        ...DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.inputHub,
        speechToText: { enabled: true },
      },
      speechToText: {
        enabled: true,
        suppressDuringTts: true,
      },
    };
    const hub = makeHub(config);

    hub.setTtsSpeaking(true);

    expect(hub.pushSpeechToText("speaker echo")).toEqual({
      accepted: false,
      reason: "tts-echo-suppressed",
    });
    expect(hub.snapshot().events).toHaveLength(0);
  });
});
