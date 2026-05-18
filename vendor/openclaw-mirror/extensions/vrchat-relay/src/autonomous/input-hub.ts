import type { InputHubConfig, SpeechToTextConfig } from "./config.js";

export type InputHubSource = "textBox" | "speechToText" | "visionObservation" | "streamComment";

export interface InputHubEvent {
  source: InputHubSource;
  text: string;
  atMs?: number;
  metadata?: Record<string, unknown>;
}

export interface InputHubAcceptedEvent extends InputHubEvent {
  atMs: number;
}

export interface InputHubSnapshot {
  events: InputHubAcceptedEvent[];
  latestText?: string;
  latestVisionObservation?: string;
  latestStreamComment?: string;
  latestSpeechToText?: string;
}

export interface InputHubPushResult {
  accepted: boolean;
  reason?: "source-disabled" | "empty" | "tts-echo-suppressed";
}

export interface InputHubOptions {
  config: InputHubConfig;
  speechToText: SpeechToTextConfig;
  nowMs?: () => number;
}

export class InputHub {
  private readonly nowMs: () => number;
  private readonly events: InputHubAcceptedEvent[] = [];
  private ttsSpeaking = false;

  constructor(private readonly options: InputHubOptions) {
    this.nowMs = options.nowMs ?? Date.now;
  }

  setTtsSpeaking(speaking: boolean): void {
    this.ttsSpeaking = speaking;
  }

  isTtsSpeaking(): boolean {
    return this.ttsSpeaking;
  }

  push(event: InputHubEvent): InputHubPushResult {
    if (!this.isSourceEnabled(event.source)) {
      return { accepted: false, reason: "source-disabled" };
    }
    const text = event.text.trim();
    if (!text) {
      return { accepted: false, reason: "empty" };
    }
    if (
      event.source === "speechToText" &&
      this.options.speechToText.suppressDuringTts &&
      this.ttsSpeaking
    ) {
      return { accepted: false, reason: "tts-echo-suppressed" };
    }

    this.events.push({
      ...event,
      text,
      atMs: event.atMs ?? this.nowMs(),
    });
    const max = Math.max(1, this.options.config.maxBufferedEvents);
    while (this.events.length > max) {
      this.events.shift();
    }
    return { accepted: true };
  }

  pushTextBox(text: string, metadata?: Record<string, unknown>): InputHubPushResult {
    return this.push({ source: "textBox", text, metadata });
  }

  pushSpeechToText(text: string, metadata?: Record<string, unknown>): InputHubPushResult {
    return this.push({ source: "speechToText", text, metadata });
  }

  pushVisionObservation(text: string, metadata?: Record<string, unknown>): InputHubPushResult {
    return this.push({ source: "visionObservation", text, metadata });
  }

  pushStreamComment(text: string, metadata?: Record<string, unknown>): InputHubPushResult {
    return this.push({ source: "streamComment", text, metadata });
  }

  snapshot(): InputHubSnapshot {
    const events = [...this.events];
    return {
      events,
      latestText: this.latestFrom(events, "textBox"),
      latestVisionObservation: this.latestFrom(events, "visionObservation"),
      latestStreamComment: this.latestFrom(events, "streamComment"),
      latestSpeechToText: this.latestFrom(events, "speechToText"),
    };
  }

  flush(): InputHubSnapshot {
    const snapshot = this.snapshot();
    this.events.length = 0;
    return snapshot;
  }

  getStatus(): { bufferedEvents: number; ttsSpeaking: boolean } {
    return {
      bufferedEvents: this.events.length,
      ttsSpeaking: this.ttsSpeaking,
    };
  }

  private latestFrom(events: InputHubAcceptedEvent[], source: InputHubSource): string | undefined {
    for (let index = events.length - 1; index >= 0; index--) {
      if (events[index].source === source) {
        return events[index].text;
      }
    }
    return undefined;
  }

  private isSourceEnabled(source: InputHubSource): boolean {
    switch (source) {
      case "textBox":
        return this.options.config.textBox.enabled;
      case "speechToText":
        return this.options.config.speechToText.enabled && this.options.speechToText.enabled;
      case "visionObservation":
        return this.options.config.visionObservation.enabled;
      case "streamComment":
        return this.options.config.streamComment.enabled;
    }
  }
}
