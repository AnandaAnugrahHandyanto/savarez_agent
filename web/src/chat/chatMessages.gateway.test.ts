import { describe, expect, it } from "vitest";

import {
  appendInflightToMessages,
  toChatMessagesFromGateway,
} from "./chatMessages";

describe("toChatMessagesFromGateway", () => {
  it("maps gateway text rows to chat messages", () => {
    const rows = [
      { role: "user", text: "hello" },
      { role: "assistant", text: "hi there" },
    ];
    expect(toChatMessagesFromGateway(rows).map((m) => [m.role, m.content])).toEqual([
      ["user", "hello"],
      ["assistant", "hi there"],
    ]);
  });

  it("attaches tool rows to the next assistant message", () => {
    const rows = [
      { role: "user", text: "run" },
      { role: "tool", name: "terminal", context: "ls" },
      { role: "assistant", text: "done" },
    ];
    const out = toChatMessagesFromGateway(rows);
    expect(out).toHaveLength(2);
    expect(out[1]?.toolCalls?.[0]?.name).toBe("terminal");
  });

  it("returns empty for non-arrays", () => {
    expect(toChatMessagesFromGateway(null)).toEqual([]);
  });
});

describe("appendInflightToMessages", () => {
  it("adds in-flight user and partial streaming assistant", () => {
    const base = [{ id: "u1", role: "user" as const, content: "older" }];
    const out = appendInflightToMessages(base, {
      user: "write a long answer",
      assistant: "partial answer",
      streaming: true,
    });
    expect(out).toHaveLength(3);
    expect(out[1]?.content).toBe("write a long answer");
    expect(out[2]).toMatchObject({
      role: "assistant",
      content: "partial answer",
      streaming: true,
    });
  });

  it("dedupes inflight user when already last committed user row", () => {
    const base = [{ id: "u1", role: "user" as const, content: "same prompt" }];
    const out = appendInflightToMessages(base, {
      user: "same prompt",
      assistant: "typing…",
      streaming: true,
    });
    expect(out).toHaveLength(2);
    expect(out[1]?.role).toBe("assistant");
  });

  it("merges inflight assistant into trailing streaming bubble", () => {
    const base = [
      { id: "u1", role: "user" as const, content: "go" },
      {
        id: "a1",
        role: "assistant" as const,
        content: "",
        streaming: true,
      },
    ];
    const out = appendInflightToMessages(base, {
      user: "go",
      assistant: "partial",
      streaming: true,
    });
    expect(out).toHaveLength(2);
    expect(out[1]).toMatchObject({
      id: "a1",
      content: "partial",
      streaming: true,
    });
  });
});
