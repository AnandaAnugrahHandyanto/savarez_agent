import { describe, it, expect } from "vitest";
import { escapeHtml } from "../src/render.js";

describe("escapeHtml", () => {
  it("escapes ampersand, lt, gt, quotes", () => {
    expect(escapeHtml(`<script>alert("xss")</script>&'`)).toBe(
      "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;&amp;&#39;"
    );
  });

  it("returns empty string for null/undefined", () => {
    expect(escapeHtml(null as unknown as string)).toBe("");
    expect(escapeHtml(undefined as unknown as string)).toBe("");
  });

  it("stringifies non-strings", () => {
    expect(escapeHtml(42 as unknown as string)).toBe("42");
  });
});
