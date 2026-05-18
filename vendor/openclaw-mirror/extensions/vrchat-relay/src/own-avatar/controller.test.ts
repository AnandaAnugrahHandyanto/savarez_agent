import { describe, expect, it } from "vitest";
import { DEFAULT_OWN_AVATAR_CONFIG, DEFAULT_OWN_AVATAR_REQUIRED_PARAMS } from "./config.js";
import { VRChatOwnAvatarController } from "./controller.js";
import type { OwnAvatarOscSender } from "./osc.js";
import { inferEmotionFromText, mapOpenClawStateToOcState } from "./parameter-mapper.js";
import type { VRChatAvatarRegistry } from "./registry.js";

interface SentParameter {
  name: string;
  value: boolean | number;
}

function fakeSender(): { sender: OwnAvatarOscSender; sent: SentParameter[] } {
  const sent: SentParameter[] = [];
  return {
    sent,
    sender: {
      sendAvatarParameter(name, value) {
        sent.push({ name, value });
      },
    },
  };
}

function supportedRegistry(): VRChatAvatarRegistry {
  const parameterSet = new Set<string>(DEFAULT_OWN_AVATAR_REQUIRED_PARAMS);
  return {
    getCurrent() {
      return {
        avatarId: "avtr_ready",
        parameters: [],
        supported: true,
        missingRequiredParameters: [],
      };
    },
    hasWritableParameter(name: string) {
      return parameterSet.has(name);
    },
    async loadAvatar(avatarId: string) {
      return {
        avatarId,
        parameters: [],
        supported: true,
        missingRequiredParameters: [],
      };
    },
  } as VRChatAvatarRegistry;
}

function testController(options: { nowMs?: () => number } = {}) {
  const { sender, sent } = fakeSender();
  const controller = new VRChatOwnAvatarController({
    config: {
      ...DEFAULT_OWN_AVATAR_CONFIG,
      behavior: {
        ...DEFAULT_OWN_AVATAR_CONFIG.behavior,
        actionCooldownMs: 0,
        idleMinIntervalMs: 1_000_000,
        idleMaxIntervalMs: 1_000_000,
      },
    },
    sender,
    registry: supportedRegistry(),
    nowMs: options.nowMs,
    setTimeoutFn: (() => 0) as unknown as typeof setTimeout,
    clearTimeoutFn: (() => undefined) as typeof clearTimeout,
    random: () => 0,
  });
  return { controller, sent };
}

describe("VRChatOwnAvatarController", () => {
  it("maps OpenClaw states to OC_State values", () => {
    expect(mapOpenClawStateToOcState("idle")).toBe(0);
    expect(mapOpenClawStateToOcState("listening")).toBe(1);
    expect(mapOpenClawStateToOcState("thinking")).toBe(2);
    expect(mapOpenClawStateToOcState("speaking")).toBe(3);
    expect(mapOpenClawStateToOcState("tool_running")).toBe(4);
    expect(mapOpenClawStateToOcState("error")).toBe(7);
  });

  it("infers representative emotions from text", () => {
    expect(inferEmotionFromText("That is great, thank you")).toBe("happy");
    expect(inferEmotionFromText("I am not sure about that")).toBe("confused");
    expect(inferEmotionFromText("")).toBe("neutral");
  });

  it("toggles OC_ActionPulse when the same action is retriggered", () => {
    const { controller, sent } = testController();
    controller.setAutoEnabled(true);
    controller.triggerAction("wave");
    controller.triggerAction("wave");

    expect(sent).toContainEqual({ name: "OC_Action", value: 2 });
    expect(sent.filter((item) => item.name === "OC_ActionPulse").map((item) => item.value)).toEqual(
      [true, false],
    );
  });

  it("blocks autonomous sends while manual lock is active", () => {
    const { controller, sent } = testController();
    controller.setAutoEnabled(true);
    controller.handleOscMessage({
      address: "/avatar/parameters/OC_ManualLock",
      args: [true],
    });
    controller.applyState("thinking");

    expect(sent.some((item) => item.name === "OC_State" && item.value === 2)).toBe(false);
  });

  it("emergency stop sends reset and neutral parameters even under manual lock", () => {
    const { controller, sent } = testController();
    controller.setAutoEnabled(true);
    controller.handleOscMessage({
      address: "/avatar/parameters/OC_ManualLock",
      args: [true],
    });

    controller.emergencyStop();

    expect(sent).toEqual(
      expect.arrayContaining([
        { name: "OC_Reset", value: true },
        { name: "OC_Action", value: 0 },
        { name: "OC_State", value: 0 },
        { name: "OC_Emotion", value: 0 },
        { name: "OC_AutoEnabled", value: false },
      ]),
    );
    expect(controller.getStatus().enabled).toBe(false);
  });

  it("returns manual disable to neutral parameters", () => {
    const { controller, sent } = testController();
    controller.setAutoEnabled(true);
    controller.applyState("speaking");
    controller.applyEmotion("happy");

    const disabled = controller.setAutoEnabled(false);

    expect(disabled).toBe(true);
    expect(sent).toEqual(
      expect.arrayContaining([
        { name: "OC_Action", value: 0 },
        { name: "OC_State", value: 0 },
        { name: "OC_Emotion", value: 0 },
        { name: "OC_AutoEnabled", value: false },
      ]),
    );
    expect(controller.getStatus().currentState).toBe("idle");
    expect(controller.getStatus().currentEmotion).toBe("neutral");
  });

  it("rate-limits emotion changes separately from neutral resets", () => {
    let now = 10_000;
    const { controller, sent } = testController({ nowMs: () => now });

    expect(controller.applyEmotion("happy")).toBe(true);
    now += 500;
    expect(controller.applyEmotion("surprised")).toBe(false);
    expect(controller.applyEmotion("neutral", { bypassCooldown: true })).toBe(true);

    expect(sent.filter((item) => item.name === "OC_Emotion").map((item) => item.value)).toEqual([
      1, 0,
    ]);
  });

  it("clamps and sends OC_LookX and OC_LookY", () => {
    const { controller, sent } = testController();

    expect(controller.setLook(2, -2)).toBe(true);

    expect(sent).toEqual(
      expect.arrayContaining([
        { name: "OC_LookX", value: 1 },
        { name: "OC_LookY", value: -1 },
      ]),
    );
  });
});
