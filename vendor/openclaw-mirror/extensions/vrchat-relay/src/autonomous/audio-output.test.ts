import { describe, expect, it } from "vitest";
import { AudioOutputRouter, resolveAudioOutputTargets } from "./audio-output.js";

describe("AudioOutputRouter", () => {
  it("resolves speaker, virtual cable, and both targets", () => {
    expect(resolveAudioOutputTargets("speaker")).toEqual(["speaker"]);
    expect(resolveAudioOutputTargets("virtual_cable")).toEqual(["virtual_cable"]);
    expect(resolveAudioOutputTargets("both")).toEqual(["speaker", "virtual_cable"]);
  });

  it("emits speaking start and end events around sink playback", async () => {
    const events: string[] = [];
    const played: string[] = [];
    const router = new AudioOutputRouter({
      config: {
        mode: "both",
        emitSpeakingEvents: true,
      },
      sink: {
        async play(_audio, target) {
          played.push(target);
        },
      },
      onEvent(event) {
        events.push(event.type);
      },
    });

    await router.route(new ArrayBuffer(1), { text: "hello" });

    expect(played.toSorted()).toEqual(["speaker", "virtual_cable"]);
    expect(events).toEqual(["speaking.start", "speaking.end"]);
  });
});
