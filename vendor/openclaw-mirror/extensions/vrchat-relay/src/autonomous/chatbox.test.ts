import { describe, expect, it } from "vitest";
import { DEFAULT_OSC_PATHS } from "../osc/types.js";
import { normalizeChatBoxText, VRChatChatBoxSender } from "./chatbox.js";
import { DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG } from "./config.js";

describe("VRChatChatBoxSender", () => {
  it("is disabled by default", () => {
    const sent: Array<{ address: string; args: unknown[] }> = [];
    const sender = new VRChatChatBoxSender(DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.chatBox, {
      send(address, args) {
        sent.push({ address, args });
      },
    });

    expect(sender.send({ text: "hello" })).toEqual({
      success: false,
      error: "chatbox-disabled",
    });
    expect(sent).toEqual([]);
  });

  it("truncates ChatBox text to 144 characters and 9 lines", () => {
    const normalized = normalizeChatBoxText(
      Array.from({ length: 12 }, (_, index) => `line-${index}-${"x".repeat(30)}`).join("\n"),
      { maxChars: 144, maxLines: 9 },
    );

    expect(normalized.trimmed).toBe(true);
    expect(normalized.text.length).toBeLessThanOrEqual(144);
    expect(normalized.text.split("\n").length).toBeLessThanOrEqual(9);
  });

  it("sends /chatbox/input with text, submit, and notify args and rate limits spam", () => {
    let now = 1_000;
    const sent: Array<{ address: string; args: (string | number | boolean | null)[] }> = [];
    const sender = new VRChatChatBoxSender(
      {
        ...DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.chatBox,
        enabled: true,
        minIntervalMs: 3_000,
      },
      {
        send(address, args) {
          sent.push({ address, args });
        },
      },
      () => now,
    );

    expect(sender.send({ text: "hello", submit: true, notify: false })).toMatchObject({
      success: true,
      text: "hello",
    });
    expect(sent).toEqual([{ address: DEFAULT_OSC_PATHS.chatbox, args: ["hello", true, false] }]);

    expect(sender.send({ text: "again" })).toMatchObject({
      success: false,
      error: "rate-limited",
    });

    now = 4_100;
    expect(sender.send({ text: "again" })).toMatchObject({ success: true });
  });

  it("sends /chatbox/typing only when ChatBox is enabled", () => {
    const sent: Array<{ address: string; args: (string | number | boolean | null)[] }> = [];
    const sender = new VRChatChatBoxSender(
      {
        ...DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.chatBox,
        enabled: true,
      },
      {
        send(address, args) {
          sent.push({ address, args });
        },
      },
    );

    expect(sender.setTyping(true)).toEqual({ success: true });
    expect(sent).toEqual([{ address: DEFAULT_OSC_PATHS.chatboxTyping, args: [true] }]);
  });
});
