import { describe, expect, it } from "vitest";
import { DEFAULT_OWN_AVATAR_CONFIG } from "./config.js";
import type { VRChatAvatarRegistry } from "./registry.js";
import { VRChatSafetyGate } from "./safety-gate.js";

function registryWith(parameters: readonly string[]): VRChatAvatarRegistry {
  return {
    hasWritableParameter(name: string) {
      return parameters.includes(name);
    },
  } as VRChatAvatarRegistry;
}

describe("VRChatSafetyGate", () => {
  it("defaults to localhost-only OSC, no movement, no chatbox mirror, and JSON allowlisting", () => {
    expect(DEFAULT_OWN_AVATAR_CONFIG.vrchatOsc.host).toBe("127.0.0.1");
    expect(DEFAULT_OWN_AVATAR_CONFIG.vrchatOsc.sendPort).toBe(9000);
    expect(DEFAULT_OWN_AVATAR_CONFIG.vrchatOsc.receivePort).toBe(9001);
    expect(DEFAULT_OWN_AVATAR_CONFIG.vrchatOsc.allowRemoteOsc).toBe(false);
    expect(DEFAULT_OWN_AVATAR_CONFIG.movement.enabled).toBe(false);
    expect(DEFAULT_OWN_AVATAR_CONFIG.safety.disableChatBoxByDefault).toBe(true);
    expect(DEFAULT_OWN_AVATAR_CONFIG.safety.requireOscJsonParameterPresence).toBe(true);
  });

  it("blocks remote OSC hosts unless explicitly allowed", () => {
    const gate = new VRChatSafetyGate(
      {
        ...DEFAULT_OWN_AVATAR_CONFIG,
        vrchatOsc: {
          ...DEFAULT_OWN_AVATAR_CONFIG.vrchatOsc,
          host: "192.0.2.10",
          allowRemoteOsc: false,
        },
      },
      registryWith(["OC_State"]),
    );

    expect(gate.validateParameter("OC_State")).toEqual({
      allowed: false,
      reason: "remote-osc-disabled",
    });
  });

  it("requires the OC prefix and the avatar OSC JSON allowlist", () => {
    const gate = new VRChatSafetyGate(DEFAULT_OWN_AVATAR_CONFIG, registryWith(["OC_State"]));

    expect(gate.validateParameter("FX_Smile")).toEqual({
      allowed: false,
      reason: "invalid-prefix",
    });
    expect(gate.validateParameter("OC_Unknown")).toEqual({
      allowed: false,
      reason: "parameter-not-registered",
    });
    expect(gate.validateParameter("OC_State")).toEqual({ allowed: true });
  });

  it("enforces manual lock and supports emergency bypass", () => {
    const gate = new VRChatSafetyGate(DEFAULT_OWN_AVATAR_CONFIG, registryWith(["OC_State"]));

    gate.setManualLock(true);

    expect(gate.validateParameter("OC_State")).toEqual({
      allowed: false,
      reason: "manual-lock",
    });
    expect(gate.validateParameter("OC_State", { bypassManualLock: true })).toEqual({
      allowed: true,
    });
  });

  it("rate-limits own-avatar commands", () => {
    let now = 1_000;
    const gate = new VRChatSafetyGate(
      {
        ...DEFAULT_OWN_AVATAR_CONFIG,
        behavior: {
          ...DEFAULT_OWN_AVATAR_CONFIG.behavior,
          maxCommandsPerSecond: 2,
        },
      },
      registryWith(["OC_State"]),
      () => now,
    );

    expect(gate.validateParameter("OC_State")).toEqual({ allowed: true });
    expect(gate.validateParameter("OC_State")).toEqual({ allowed: true });
    expect(gate.validateParameter("OC_State")).toEqual({
      allowed: false,
      reason: "rate-limited",
    });

    now = 2_100;
    expect(gate.validateParameter("OC_State")).toEqual({ allowed: true });
  });
});
