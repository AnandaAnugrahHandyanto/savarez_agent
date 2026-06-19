import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Markdown } from "./Markdown";

describe("Markdown", () => {
  it("renders pipe markdown tables as semantic HTML tables", () => {
    const html = renderToStaticMarkup(
      <Markdown
        content={[
          "| Artifact | Verdict | Notes |",
          "| --- | :---: | --- |",
          "| `manifest.toml` | **pass** | [open](https://example.test/manifest) |",
          "| validation report | fail | preserves table cells |",
        ].join("\n")}
      />,
    );

    expect(html).toContain("<table");
    expect(html).toContain("<thead");
    expect(html).toContain("<tbody");
    expect(html).toContain("<th");
    expect(html).toContain("<td");
    expect(html).toContain("manifest.toml");
    expect(html).toContain("<strong");
    expect(html).toContain("href=\"https://example.test/manifest\"");
    expect(html).not.toContain(":---:");
  });
});
