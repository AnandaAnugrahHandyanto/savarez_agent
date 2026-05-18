import { describe, expect, it } from "vitest";
import { decodeOSCMessage, encodeOSCMessage } from "./codec.js";

describe("OSC codec", () => {
  it("serializes and parses an own-avatar boolean parameter", () => {
    const encoded = encodeOSCMessage({
      address: "/avatar/parameters/OC_AutoEnabled",
      args: [{ type: "boolean", value: true }],
    });

    expect(decodeOSCMessage(encoded)).toEqual({
      address: "/avatar/parameters/OC_AutoEnabled",
      args: [true],
    });
  });

  it("serializes and parses own-avatar integer and float parameters", () => {
    const state = decodeOSCMessage(
      encodeOSCMessage({
        address: "/avatar/parameters/OC_State",
        args: [{ type: "integer", value: 3 }],
      }),
    );
    const look = decodeOSCMessage(
      encodeOSCMessage({
        address: "/avatar/parameters/OC_LookX",
        args: [{ type: "float", value: 0.25 }],
      }),
    );

    expect(state).toEqual({ address: "/avatar/parameters/OC_State", args: [3] });
    expect(look?.address).toBe("/avatar/parameters/OC_LookX");
    expect(look?.args[0]).toBeCloseTo(0.25);
  });

  it("serializes and parses VRChat /avatar/change events", () => {
    const decoded = decodeOSCMessage(
      encodeOSCMessage({
        address: "/avatar/change",
        args: [{ type: "string", value: "avtr_openclaw" }],
      }),
    );

    expect(decoded).toEqual({
      address: "/avatar/change",
      args: ["avtr_openclaw"],
    });
  });
});
