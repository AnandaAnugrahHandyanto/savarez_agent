import { describe, expect, it } from "vitest";

import {
  relativeSessionAge,
  resumableHistory,
  sessionDisplayTitle,
  type SessionActiveItem,
  type SessionListItem,
} from "./sessionListCore";

describe("resumableHistory", () => {
  it("removes history rows that are also live", () => {
    const history: SessionListItem[] = [
      {
        id: "a",
        title: "A",
        preview: "",
        started_at: 1,
        message_count: 1,
      },
      {
        id: "b",
        title: "B",
        preview: "",
        started_at: 2,
        message_count: 1,
      },
    ];
    const live: SessionActiveItem[] = [
      { id: "a", status: "working", title: "A live" },
    ];
    expect(resumableHistory(history, live).map((s) => s.id)).toEqual(["b"]);
  });

  it("dedupes when live runtime id differs from stored history id", () => {
    const history: SessionListItem[] = [
      {
        id: "stored-key-1",
        title: "Hi",
        preview: "hi",
        started_at: 1,
        message_count: 1,
      },
    ];
    const live: SessionActiveItem[] = [
      {
        id: "runtime01",
        session_key: "stored-key-1",
        status: "idle",
        title: "Hi",
      },
    ];
    expect(resumableHistory(history, live)).toEqual([]);
  });
});

describe("sessionDisplayTitle", () => {
  it("prefers title over preview", () => {
    expect(sessionDisplayTitle("My title", "preview")).toBe("My title");
  });

  it("falls back to preview slice", () => {
    expect(sessionDisplayTitle("", "hello world")).toBe("hello world");
  });

  it("uses untitled label when empty", () => {
    expect(sessionDisplayTitle("", "", "Untitled")).toBe("Untitled");
  });
});

describe("relativeSessionAge", () => {
  it("returns today for recent timestamps", () => {
    const now = Math.floor(Date.now() / 1000);
    expect(relativeSessionAge(now)).toBe("today");
  });
});
