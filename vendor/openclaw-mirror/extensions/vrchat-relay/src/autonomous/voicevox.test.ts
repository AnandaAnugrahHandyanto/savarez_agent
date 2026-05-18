import { describe, expect, it } from "vitest";
import { DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG } from "./config.js";
import { VOICEVOXAdapter } from "./voicevox.js";

describe("VOICEVOXAdapter", () => {
  it("builds audio_query requests for the local VOICEVOX engine", () => {
    const adapter = new VOICEVOXAdapter(DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.voicevox);

    const request = adapter.buildAudioQueryRequest({ text: "hello voicevox", speaker: 3 });
    const url = new URL(request.url);

    expect(url.origin).toBe("http://127.0.0.1:50021");
    expect(url.pathname).toBe("/audio_query");
    expect(url.searchParams.get("text")).toBe("hello voicevox");
    expect(url.searchParams.get("speaker")).toBe("3");
    expect(request.init.method).toBe("POST");
  });

  it("builds synthesis requests with JSON audio_query bodies", () => {
    const adapter = new VOICEVOXAdapter(DEFAULT_AUTONOMOUS_VRCHAT_AI_CONFIG.voicevox);

    const request = adapter.buildSynthesisRequest({ accent_phrases: [] }, 2);
    const url = new URL(request.url);

    expect(url.pathname).toBe("/synthesis");
    expect(url.searchParams.get("speaker")).toBe("2");
    expect(request.init.method).toBe("POST");
    expect(request.init.headers).toMatchObject({ "content-type": "application/json" });
    expect(request.init.body).toBe(JSON.stringify({ accent_phrases: [] }));
  });
});
