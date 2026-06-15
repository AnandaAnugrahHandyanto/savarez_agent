import { describe, expect, it } from "vitest";

import type { ChatMessage } from "@/chat/chatMessages";

import { buildBranchSeedMessages } from "./chatBranch";

const msgs: ChatMessage[] = [
  { id: "u1", role: "user", content: "hello" },
  { id: "a1", role: "assistant", content: "hi there" },
  { id: "u2", role: "user", content: "branch here?" },
  { id: "a2", role: "assistant", content: "sure" },
];

describe("buildBranchSeedMessages", () => {
  it("includes full transcript when no anchor id", () => {
    expect(buildBranchSeedMessages(msgs)).toEqual([
      { role: "user", content: "hello" },
      { role: "assistant", content: "hi there" },
      { role: "user", content: "branch here?" },
      { role: "assistant", content: "sure" },
    ]);
  });

  it("truncates through the anchor message inclusive", () => {
    expect(buildBranchSeedMessages(msgs, "a1")).toEqual([
      { role: "user", content: "hello" },
      { role: "assistant", content: "hi there" },
    ]);
  });

  it("skips system rows and empty content", () => {
    const mixed: ChatMessage[] = [
      { id: "s1", role: "system", content: "boot" },
      { id: "u1", role: "user", content: "go" },
      { id: "a1", role: "assistant", content: "   " },
      { id: "a2", role: "assistant", content: "done" },
    ];
    expect(buildBranchSeedMessages(mixed)).toEqual([
      { role: "user", content: "go" },
      { role: "assistant", content: "done" },
    ]);
  });
});
