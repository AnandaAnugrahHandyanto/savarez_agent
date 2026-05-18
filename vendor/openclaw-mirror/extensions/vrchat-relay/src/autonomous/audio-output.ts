import type { AudioOutputConfig, AudioOutputMode } from "./config.js";

export type AudioOutputTarget = "speaker" | "virtual_cable";
export type AudioOutputEventType = "speaking.start" | "speaking.end";

export interface AudioOutputEvent {
  type: AudioOutputEventType;
  text?: string;
  targets: AudioOutputTarget[];
}

export interface AudioOutputSink {
  play(audio: ArrayBuffer, target: AudioOutputTarget): Promise<void>;
}

export type AudioOutputEventHandler = (event: AudioOutputEvent) => void;

export interface AudioOutputRouterOptions {
  config: AudioOutputConfig;
  sink?: AudioOutputSink;
  onEvent?: AudioOutputEventHandler;
}

export class AudioOutputRouter {
  private readonly handlers = new Set<AudioOutputEventHandler>();

  constructor(private readonly options: AudioOutputRouterOptions) {
    if (options.onEvent) {
      this.handlers.add(options.onEvent);
    }
  }

  onEvent(handler: AudioOutputEventHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  getTargets(): AudioOutputTarget[] {
    return resolveAudioOutputTargets(this.options.config.mode);
  }

  async route(audio: ArrayBuffer, options: { text?: string } = {}): Promise<void> {
    const targets = this.getTargets();
    if (this.options.config.emitSpeakingEvents) {
      this.emit({ type: "speaking.start", text: options.text, targets });
    }
    try {
      if (this.options.sink) {
        await Promise.all(targets.map((target) => this.options.sink!.play(audio, target)));
      }
    } finally {
      if (this.options.config.emitSpeakingEvents) {
        this.emit({ type: "speaking.end", text: options.text, targets });
      }
    }
  }

  private emit(event: AudioOutputEvent): void {
    for (const handler of this.handlers) {
      handler(event);
    }
  }
}

export function resolveAudioOutputTargets(mode: AudioOutputMode): AudioOutputTarget[] {
  switch (mode) {
    case "speaker":
      return ["speaker"];
    case "virtual_cable":
      return ["virtual_cable"];
    case "both":
      return ["speaker", "virtual_cable"];
  }
}
