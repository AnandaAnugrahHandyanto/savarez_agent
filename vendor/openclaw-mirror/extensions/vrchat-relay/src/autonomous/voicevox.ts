import type { VoicevoxConfig } from "./config.js";

export interface VoicevoxRequest {
  url: string;
  init: RequestInit;
}

export interface VoicevoxSynthesisOptions {
  text: string;
  speaker?: number;
}

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export class VOICEVOXAdapter {
  private readonly fetchFn: FetchLike;

  constructor(
    private readonly config: VoicevoxConfig,
    fetchFn?: FetchLike,
  ) {
    this.fetchFn = fetchFn ?? fetch;
  }

  buildAudioQueryRequest(options: VoicevoxSynthesisOptions): VoicevoxRequest {
    const url = new URL("/audio_query", this.baseUrl());
    url.searchParams.set("text", options.text);
    url.searchParams.set("speaker", String(options.speaker ?? this.config.speaker));
    return {
      url: url.toString(),
      init: {
        method: "POST",
        headers: {
          accept: "application/json",
        },
      },
    };
  }

  buildSynthesisRequest(audioQuery: unknown, speaker = this.config.speaker): VoicevoxRequest {
    const url = new URL("/synthesis", this.baseUrl());
    url.searchParams.set("speaker", String(speaker));
    return {
      url: url.toString(),
      init: {
        method: "POST",
        headers: {
          accept: "audio/wav",
          "content-type": "application/json",
        },
        body: JSON.stringify(audioQuery),
      },
    };
  }

  async synthesize(options: VoicevoxSynthesisOptions): Promise<ArrayBuffer> {
    if (!this.config.enabled) {
      throw new Error("VOICEVOX is disabled");
    }
    const audioQueryRequest = this.buildAudioQueryRequest(options);
    const audioQuery = await this.fetchJson(audioQueryRequest);
    const synthesisRequest = this.buildSynthesisRequest(
      audioQuery,
      options.speaker ?? this.config.speaker,
    );
    const response = await this.fetchWithTimeout(synthesisRequest);
    if (!response.ok) {
      throw new Error(`VOICEVOX synthesis failed: ${response.status}`);
    }
    return response.arrayBuffer();
  }

  private async fetchJson(request: VoicevoxRequest): Promise<unknown> {
    const response = await this.fetchWithTimeout(request);
    if (!response.ok) {
      throw new Error(`VOICEVOX audio_query failed: ${response.status}`);
    }
    return response.json();
  }

  private async fetchWithTimeout(request: VoicevoxRequest): Promise<Response> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.config.timeoutMs);
    try {
      return await this.fetchFn(request.url, {
        ...request.init,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
    }
  }

  private baseUrl(): string {
    return this.config.baseUrl.endsWith("/") ? this.config.baseUrl : `${this.config.baseUrl}/`;
  }
}
