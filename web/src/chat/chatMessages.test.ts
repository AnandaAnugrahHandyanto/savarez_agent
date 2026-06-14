import { describe, expect, it } from "vitest";

import {
  appendTextDelta,
  nextMessageId,
  upsertToolPart,
  STREAM_DELTA_FLUSH_MS,
} from "./chatMessages";

describe("chatMessages", () => {
  it("appendTextDelta concatenates", () => {
    expect(appendTextDelta("hello", " world")).toBe("hello world");
  });

  it("nextMessageId returns unique ids", () => {
    const a = nextMessageId("test");
    const b = nextMessageId("test");
    expect(a).not.toBe(b);
  });

  it("upsertToolPart adds then completes a tool", () => {
    const running = upsertToolPart([], { name: "read_file", tool_id: "t1" }, "running");
    expect(running).toHaveLength(1);
    expect(running[0].status).toBe("running");
    expect(running[0].name).toBe("read_file");

    const done = upsertToolPart(
      running,
      { name: "read_file", tool_id: "t1", summary: "ok" },
      "complete",
    );
    expect(done).toHaveLength(1);
    expect(done[0].status).toBe("done");
    expect(done[0].summary).toBe("ok");
  });

  it("STREAM_DELTA_FLUSH_MS matches desktop batching", () => {
    expect(STREAM_DELTA_FLUSH_MS).toBe(33);
  });
});
